"""The lab's public API. Every tool is a function taking and returning JSON-able dicts, also exposed as
`chiplab <tool-name>` (cli.py). Every call is logged (log.py). The AI scientist decides what to try; these make
it and measure it."""
from __future__ import annotations

import hashlib
import json
import os
import stat
import time
import traceback
from functools import wraps
from pathlib import Path

import numpy as np

from chiplab import config, log

TOOLS: dict[str, dict] = {}


class ToolError(RuntimeError):
    pass


CONTEXT_ARGS = {"run_id": "str — dashboard run to emit events into (optional)",
                "session_id": "str — calling agent session (optional; used for quotas and the leaderboard)",
                "round": "int — design round, copied onto dashboard events (optional)"}


def tool(summary: str, params: dict, lane: str = "cpu", cacheable: bool = False):
    """Register a tool. params: {name: "type — meaning (default)"} for docs and AGENT.md.

    lane: which job queue runs it asynchronously (cpu | gpu | docker | inline). cacheable: deterministic given its
    args (design ids are content hashes), so results are reused across agents. Every tool also accepts the
    CONTEXT_ARGS (run_id, session_id, round) and `force` to bypass the cache.
    """
    def deco(fn):
        name = fn.__name__

        @wraps(fn)
        def wrapper(**kw):
            from chiplab import cache, events
            ctx = {k: kw.pop(k) for k in list(kw) if k in CONTEXT_ARGS}
            force = bool(kw.pop("force", False))
            t0, c0 = time.time(), time.process_time()
            res = cache.get(name, kw) if cacheable and not force else None
            if res is not None:
                res = dict(res, cached=True)
            else:
                try:
                    res = fn(**kw)
                    res.setdefault("status", "ok")
                except Exception as e:  # every failure is a logged, structured answer
                    res = {"status": "error", "error": f"{type(e).__name__}: {e}"}
                    if os.environ.get("CHIPLAB_DEBUG"):
                        res["traceback"] = traceback.format_exc()
                res = _jsonable(res)
                res.setdefault("cost", {}).update({"wall_s": round(time.time() - t0, 3), "cpu_s_host": round(time.process_time() - c0, 3)})
                if cacheable:
                    cache.put(name, kw, res)
            log.log_call(name, {**kw, **ctx}, res, time.time() - t0)
            try:
                events.for_tool(name, {**kw, **ctx}, res)
            except Exception:  # events must never break a tool
                pass
            return res
        TOOLS[name] = {"fn": wrapper, "summary": summary, "params": {**params}, "lane": lane, "cacheable": cacheable}
        return wrapper
    return deco


def _h(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:12]


def _write_ro(path: Path, obj) -> None:
    if path.exists():
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    path.write_text(json.dumps(obj, indent=1, default=str))
    os.chmod(path, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)


def _jsonable(x):
    if isinstance(x, dict):
        return {k: _jsonable(v) for k, v in x.items() if k != "circuit"}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    if isinstance(x, np.generic):
        return x.item()
    if isinstance(x, np.ndarray):
        return x.tolist()
    return x


# ------------------------------------------------------------------------------------------------ tasks and data

def _task_dir(task_id: str) -> Path:
    d = config.HOME / "tasks" / task_id
    if not d.exists():
        raise ToolError(f"unknown task {task_id}")
    return d


def _load_task(task_id: str) -> tuple[dict, dict]:
    from chiplab.data.splits import split_hash
    d = _task_dir(task_id)
    task = json.loads((d / "task.json").read_text())
    sp = json.loads((d / "split.json").read_text())
    if split_hash(sp["assign"], sp["extra"]) != sp["hash"]:
        raise ToolError(f"task {task_id}: split.json was modified (hash mismatch); the locked split is refused")
    return task, sp


def _recordings(task: dict):
    from chiplab.plugins import registry
    if task.get("simulator"):
        sim, prov = registry.get("simulators", task["simulator"]["name"])
        s = task["simulator"]
        return list(sim.simulate(s.get("n_subjects", 40), s.get("params", {}), s.get("seed", 0))), prov, sim.assumptions(s.get("params", {}))
    ds, prov = registry.get("datasets", task["dataset"])
    root = config.DATA
    ds.fetch(root)
    return list(ds.recordings(root)), prov, []


@tool("Define a chip-design task: dataset or simulator, classes, clinical floor, budgets. Locks a subject-level "
      "split (train/val/test) that nobody can change afterwards.",
      {"name": "str — short task name", "dataset": "str — dataset plugin (see `chiplab plugins`), or omit with simulator",
       "simulator": "dict — {name, n_subjects, params, seed} for simulated data", "classes": "dict — class name -> list of "
       "dataset labels, negative class first, e.g. {\"neg\":[\"N\"],\"pos\":[\"A\"]}",
       "split": "dict — {fractions:[.7,.15,.15], seed:0, algo:'stratified-v1'}", "clinical_floor": "dict — e.g. "
       "{worst_subject_sensitivity: .9, specificity: .9}", "budgets": "dict — {max_gates, max_luts, max_area_um2, ...}",
       "test_budget": "int — how many times the sealed test set may be scored (default 5)"}, lane="inline")
def define_task(name: str, classes: dict, dataset: str | None = None, simulator: dict | None = None,
                split: dict | None = None, clinical_floor: dict | None = None, budgets: dict | None = None,
                test_budget: int = 5, notes: str = "") -> dict:
    from chiplab.data.splits import make_split, split_hash
    split = {"fractions": [0.7, 0.15, 0.15], "seed": 0, "algo": "stratified-v1", **(split or {})}
    task = {"name": name, "dataset": dataset, "simulator": simulator, "classes": classes, "split": split,
            "clinical_floor": clinical_floor or {}, "budgets": budgets or {}, "test_budget": test_budget, "notes": notes}
    recs, prov, assumptions = _recordings(task)
    label_to_class = {lab: i for i, labs in enumerate(classes.values()) for lab in labs}
    kept = [r for r in recs if (r.label in label_to_class) or (r.label is None and r.events is not None)]
    subj_label: dict[str, int] = {}
    for r in kept:
        c = label_to_class.get(r.label, 1 if r.events else 0)
        subj_label[r.subject_id] = max(subj_label.get(r.subject_id, 0), c)
    subjects = list(dict.fromkeys(r.subject_id for r in kept))
    assign = make_split(subjects, [subj_label[s] for s in subjects], tuple(split["fractions"]), split["seed"], split["algo"])
    extra = json.dumps({"dataset": prov, "classes": classes, "split": split}, sort_keys=True)
    sh = split_hash(assign, extra)
    task["data_provenance"] = prov
    task["data_kind"] = "simulated" if simulator else "measured"
    task["assumptions"] = assumptions
    task_id = f"{name}-{_h([task, sh])[:8]}"
    d = config.home("tasks", task_id)
    _write_ro(d / "task.json", task)
    _write_ro(d / "split.json", {"assign": assign, "extra": extra, "hash": sh})
    counts = {p: sum(1 for s in subjects if assign[s] == i) for p, i in (("train", 0), ("val", 1), ("test", 2))}
    log.event("stage", stage="split", task_id=task_id, counts=counts)
    return {"task_id": task_id, "split_hash": sh, "recordings": len(kept), "subjects_per_part": counts,
            "data_kind": task["data_kind"], "assumptions": assumptions}


def _view_path(view_id: str) -> Path:
    p = config.HOME / "views" / view_id / "view.npz"
    if not p.exists():
        raise ToolError(f"unknown view {view_id}")
    return p


@tool("Turn a task's recordings into windows of frames with an off-chip front-end; returns a view_id. "
      "Window labels and the locked split come with it.",
      {"task_id": "str", "frontend": "dict — {name, params} front-end plugin, e.g. {name:'rr_intervals'}",
       "window": "dict — {L: frames per window, stride, max_per_rec}"}, lane="cpu")
def load_data(task_id: str, frontend: dict, window: dict) -> dict:
    from chiplab.data.windows import build_view
    from chiplab.plugins import registry
    task, sp = _load_task(task_id)
    view_id = f"v-{_h([task_id, frontend, window, sp['hash']])}"
    path = config.HOME / "views" / view_id / "view.npz"
    if not path.exists():
        fe, prov = registry.get("frontends", frontend["name"])
        recs, _, _ = _recordings(task)
        label_to_class = {lab for labs in task["classes"].values() for lab in labs}
        recs = [r for r in recs if r.subject_id in sp["assign"] and (r.label in label_to_class or r.label is None)]
        frames = durations = None
        if hasattr(fe, "frames_many"):  # cached, multi-process front-end
            frames, durations, fail = fe.frames_many(recs, frontend.get("params", {}), cache_key=json.dumps(prov, sort_keys=True))
        view = build_view(recs, fe, frontend.get("params", {}), window, task["classes"], sp["assign"],
                          frames=frames, durations=durations)
        view.meta.update({"task_id": task_id, "split_hash": sp["hash"], "frontend": frontend, "frontend_prov": prov,
                          "window": window, "data_kind": task["data_kind"]})
        path.parent.mkdir(parents=True, exist_ok=True)
        view.save(path)
    from chiplab.data.contract import View
    v = View.load(path)
    per = {p: int((v.part == i).sum()) for p, i in (("train", 0), ("val", 1), ("test", 2))}
    pos = {p: int(((v.part == i) & (v.y == 1)).sum()) for p, i in (("train", 0), ("val", 1), ("test", 2))}
    return {"view_id": view_id, "task_id": task_id, "split_hash": sp["hash"], "windows_per_part": per,
            "class1_windows_per_part": pos, "frames_per_window": int(v.X.shape[1]), "features": v.frame_names,
            "data_kind": v.meta.get("data_kind")}


# ------------------------------------------------------------------------------------------------ search

@tool("Propose a batch of candidate designs (family settings + input encoding) by explicit list, random or grid "
      "sampling of a design space. Returns a proposal_id to train.",
      {"view_id": "str", "family": "str — model family plugin, e.g. 'intnn'", "sampler": "str — explicit|random|grid",
       "n": "int — number of candidates (random)", "seed": "int", "space": "dict — setting -> list of values "
       "(family settings and encoding: L, encoder, bits, lo, hi, features)", "candidates": "list — explicit designs"}, lane="inline")
def propose_designs(view_id: str, family: str, sampler: str = "random", n: int = 64, seed: int = 0,
                    space: dict | None = None, candidates: list | None = None) -> dict:
    from chiplab.plugins import registry
    from chiplab.train.propose import propose
    _view_path(view_id)
    fam, prov = registry.get("families", family)
    if sampler == "explicit":
        cands = [{"family": family, "cfg": fam.validate_cfg(c.get("cfg", {})), "encoding": c["encoding"]} for c in candidates or []]
    else:
        cands = propose(fam, sampler, n, seed, space or {})
    pid = f"p-{_h([view_id, cands])}"
    d = config.home("proposals", pid)
    (d / "proposal.json").write_text(json.dumps({"view_id": view_id, "family": family, "family_prov": prov,
                                                 "candidates": cands}, indent=1))
    log.event("stage", stage="propose", proposal_id=pid, n=len(cands))
    return {"proposal_id": pid, "n": len(cands), "family": family, "example": cands[:2]}


@tool("Train every candidate of a proposal at once on the GPU (population training). Scores on train/val only; "
      "the sealed test set is never touched. Returns per-candidate validation metrics and timing.",
      {"proposal_id": "str", "epochs": "int (family default)", "seed": "int", "device": "str — cuda|cpu|mps (auto)",
       "teacher": "str — design or reference to distil from (optional)"}, lane="gpu")
def train_batch(proposal_id: str, epochs: int | None = None, seed: int = 0, device: str | None = None,
                teacher: str | None = None, force: bool = False) -> dict:
    from chiplab.data.contract import View
    from chiplab.train.engine import run_batch
    pr = json.loads((config.HOME / "proposals" / proposal_id / "proposal.json").read_text())
    opts = {"epochs": epochs, "seed": seed, "device": device, "teacher": teacher}
    batch_id = f"b-{_h([proposal_id, opts])}"
    bd = config.home("batches", batch_id)
    if (bd / "result.json").exists() and not force:
        res = json.loads((bd / "result.json").read_text()); res["cached"] = True
        return res
    view = View.load(_view_path(pr["view_id"]))
    out = run_batch(view, pr["candidates"], {k: v for k, v in opts.items() if v is not None}, bd)
    res = {"batch_id": batch_id, "proposal_id": proposal_id, "view_id": pr["view_id"], "timing": out["timing"],
           "rows": out["rows"], "data_kind": view.meta.get("data_kind"), "cost": {"gpu_s": out["timing"].get("seconds")}}
    (bd / "result.json").write_text(json.dumps(_jsonable(res), indent=1))
    (bd / "meta.json").write_text(json.dumps({"proposal_id": proposal_id, "view_id": pr["view_id"]}))
    for r in out["rows"]:
        log.event("candidate", batch_id=batch_id, **{k: r.get(k) for k in r if not isinstance(r.get(k), (list, dict))})
    return _jsonable(res)


# ------------------------------------------------------------------------------------------------ hardware

def _design_dir(design_id: str) -> Path:
    d = config.HOME / "designs" / design_id
    if not d.exists():
        raise ToolError(f"unknown design {design_id}")
    return d


@tool("Compile one trained candidate (or a raw chipir/1 document) to Verilog-2005 with its weights wired in. "
      "Returns a design_id used by every hardware and verification tool.",
      {"batch_id": "str", "k": "int — candidate index in the batch", "ir": "dict — a chipir/1 document instead"}, lane="cpu", cacheable=True)
def compile_verilog(batch_id: str | None = None, k: int | None = None, ir: dict | None = None) -> dict:
    from chiplab.emit.verilog import emit
    from chiplab.ir.schema import design_id as did, validate
    meta = {}
    if ir is None:
        from chiplab.train.engine import lower_candidate
        bd = config.HOME / "batches" / batch_id
        ir = lower_candidate(bd, k)
        meta = {"batch_id": batch_id, "k": k, **json.loads((bd / "meta.json").read_text())}
    validate(ir)
    d_id = did(ir)
    d = config.home("designs", d_id)
    text, info = emit(ir)
    (d / "ir.json").write_text(json.dumps(ir))
    (d / "design.v").write_text(text)
    (d / "port.json").write_text(json.dumps(info))
    (d / "meta.json").write_text(json.dumps(meta))
    lint = _verilator_lint(d / "design.v", info["top"])
    log.event("stage", stage="compile", design_id=d_id)
    return {"design_id": d_id, "top": info["top"], "ports": info, "verilog": str(d / "design.v"),
            "lines": text.count("\n"), "lint": lint, "files": [str(d / "design.v"), str(d / "ir.json")]}


def _verilator_lint(path: Path, top: str) -> dict:
    import subprocess
    try:
        p = subprocess.run([config.oss_bin("verilator"), "--lint-only", "-Wall", "-Wno-DECLFILENAME", "-Wno-UNUSEDSIGNAL",
                            "--top-module", top, str(path)], capture_output=True, text=True, timeout=300)
        warn = [l for l in p.stderr.splitlines() if l.startswith("%")]
        return {"ok": p.returncode == 0, "messages": warn[:20]}
    except Exception as e:
        return {"ok": None, "messages": [f"verilator not run: {e}"]}


@tool("Synthesise a design. target=generic: gate count by type, logic depth, transistor estimate, gate netlist. "
      "target=xc7|ice40: lookup-table counts (same as count_luts).",
      {"design_id": "str", "target": "str — generic|xc7|ice40", "abc": "str — extra ABC flags, e.g. '-fast'",
       "timeout": "int seconds (900)"}, lane="cpu", cacheable=True)
def synthesize(design_id: str, target: str = "generic", effort: str = "fast", timeout: int = 900) -> dict:
    from chiplab.hw.yosys import count_luts as _luts, synth_generic
    d = _design_dir(design_id)
    info = json.loads((d / "port.json").read_text())
    if target == "generic":
        r = synth_generic(d / "design.v", info["top"], d / "synth", effort=effort, timeout=timeout)
        (d / "synth.json").write_text(json.dumps(r))
        log.event("stage", stage="synthesize", design_id=design_id, gates=r["gates"], depth=r["depth"])
        return {"design_id": design_id, "hw_kind": "synthesized", "metrics": {k: r[k] for k in ("gates", "depth", "transistors_est")},
                "cells_by_type": r["cells_by_type"], "seconds": r["seconds"], "tool": r["tool"],
                "files": [r["netlist_json"], r["gate_verilog"]]}
    r = _luts(d / "design.v", info["top"], d / f"luts_{target}", target, timeout)
    (d / f"luts_{target}.json").write_text(json.dumps(r))
    return {"design_id": design_id, "hw_kind": "synthesized", "metrics": r}


@tool("Lookup-table count for an FPGA family: xc7 (6-input, Spartan-7 class, for comparison with published FPGA "
      "designs) or ice40 (4-input, iCE40UP5K).", {"design_id": "str", "family": "str — xc7|ice40"}, lane="cpu", cacheable=True)
def count_luts(design_id: str, family: str = "xc7") -> dict:
    return synthesize.__wrapped__(design_id=design_id, target=family)


def _ensure_synth(design_id: str) -> dict:
    d = _design_dir(design_id)
    if not (d / "synth.json").exists():
        synthesize.__wrapped__(design_id=design_id, target="generic")
    return json.loads((d / "synth.json").read_text())


def _design_inputs(design_id: str, part: str):
    """Encoded integer inputs of a design on a data part, plus the training framework's decisions."""
    from chiplab.data.contract import PARTS, View
    from chiplab.train.engine import encoded_inputs, predict_candidate
    d = _design_dir(design_id)
    meta = json.loads((d / "meta.json").read_text())
    if not meta.get("batch_id"):
        raise ToolError("design was compiled from a raw IR; use inputs='random'")
    ir = json.loads((d / "ir.json").read_text())
    view = View.load(_view_path(meta["view_id"]))
    pi = PARTS[part]
    X = encoded_inputs(view, ir["meta"]["encoding"], pi)
    ref = predict_candidate(config.HOME / "batches" / meta["batch_id"], meta["k"], view, pi)
    return X, ref, view.select(pi), meta


def _test_access(design_id: str, why: str) -> int:
    from chiplab.data.contract import View
    d = _design_dir(design_id)
    meta = json.loads((d / "meta.json").read_text())
    task_id = View.load(_view_path(meta["view_id"])).meta["task_id"]
    task, _ = _load_task(task_id)
    p = config.home() / "test_access.jsonl"
    used = sum(1 for l in p.read_text().splitlines() if json.loads(l)["task_id"] == task_id and json.loads(l)["why"] == "evaluate") if p.exists() else 0
    if why == "evaluate" and used >= task.get("test_budget", 5):
        raise ToolError(f"test budget of task {task_id} used up ({used}); choose designs on val")
    with open(p, "a") as f:
        f.write(json.dumps({"ts": time.time(), "task_id": task_id, "design_id": design_id, "why": why}) + "\n")
    return used + (why == "evaluate")


@tool("Verification level 1: run inputs through the gate netlist and compare with the integer model (and with the "
      "training framework's own decisions). inputs=val|test use real windows; test returns match counts only.",
      {"design_id": "str", "inputs": "str — val|test|random", "n": "int — random vectors (100000)",
       "device": "str — numpy|cuda", "seed": "int"}, lane="gpu", cacheable=True)
def simulate(design_id: str, inputs: str = "val", n: int = 100000, device: str = "numpy", seed: int = 0) -> dict:
    from chiplab.verify.bitexact import check
    d = _design_dir(design_id)
    syn = _ensure_synth(design_id)
    ir = json.loads((d / "ir.json").read_text()); info = json.loads((d / "port.json").read_text())
    if inputs == "random":
        rng = np.random.default_rng(seed)
        X = {}
        for p in info["inputs"]:
            lo, hi = (-(1 << (p["bits"] - 1)), 1 << (p["bits"] - 1)) if p["signed"] else (0, 1 << p["bits"])
            X[p["name"]] = rng.integers(lo, hi, size=(n, p["lanes"]))
        res = check(ir, syn["netlist_json"], info, X, device=device)
    else:
        X, ref, _, _ = _design_inputs(design_id, inputs)
        if inputs == "test":
            _test_access(design_id, "simulate")
        res = check(ir, syn["netlist_json"], info, X, reference=ref, device=device)
    out = {"design_id": design_id, "inputs": inputs, "n": res["n"], "pairs": res["pairs"], "bit_exact": res["bit_exact"],
           "verification_level": 1 if res["bit_exact"] else 0}
    (d / f"simulate_{inputs}.json").write_text(json.dumps(out))
    log.event("check", design_id=design_id, inputs=inputs, bit_exact=res["bit_exact"], n=res["n"])
    return out


@tool("Clinical referee: the chip's own decisions (gate netlist outputs) scored per window, per recording and per "
      "subject, with the worst subject. split=val is free; split=test spends the task's test budget.",
      {"design_id": "str", "split": "str — val|test"}, lane="cpu")
def evaluate_clinical(design_id: str, split: str = "val") -> dict:
    from chiplab.referee.metrics import summary
    from chiplab.verify.bitexact import circuit_outputs
    d = _design_dir(design_id)
    syn = _ensure_synth(design_id)
    info = json.loads((d / "port.json").read_text())
    X, _, part_view, meta = _design_inputs(design_id, split)
    used = _test_access(design_id, "evaluate") if split == "test" else None
    p = circuit_outputs(syn["netlist_json"], info, X)[info["outputs"][0]["name"]][:, 0]
    m = summary(part_view, p)
    out = {"design_id": design_id, "split": split, "metrics": _jsonable(m), "decisions_from": "gate netlist",
           "data_kind": part_view.meta.get("data_kind")}
    if used is not None:
        out["test_scorings_used"] = used
    (d / f"clinical_{split}.json").write_text(json.dumps(out))
    return out


# ------------------------------------------------------------------------------------------------ overview

@tool("Leaderboard of compiled designs: gates, depth, bit-exact status and validation metrics.", {"task_id": "str (optional)"}, lane="inline")
def leaderboard(task_id: str | None = None) -> dict:
    rows = []
    base = config.HOME / "designs"
    for d in sorted(base.glob("*")) if base.exists() else []:
        r = {"design_id": d.name}
        for f, keys in (("synth.json", ("gates", "depth", "transistors_est")),):
            if (d / f).exists():
                s = json.loads((d / f).read_text()); r.update({k: s.get(k) for k in keys})
        if (d / "simulate_val.json").exists():
            r["bit_exact_val"] = json.loads((d / "simulate_val.json").read_text())["bit_exact"]
        if (d / "clinical_val.json").exists():
            r["val"] = json.loads((d / "clinical_val.json").read_text())["metrics"]
        rows.append(r)
    rows.sort(key=lambda r: (r.get("gates") is None, r.get("gates") or 0))
    p = config.HOME / "test_access.jsonl"
    tests = len([1 for l in p.read_text().splitlines() if '"evaluate"' in l]) if p.exists() else 0
    return {"designs": rows, "test_scorings_total": tests}


@tool("Events for the front end since a time (stage changes, candidate dots, check results).", {"since": "float — unix time (0)"}, lane="inline")
def events(since: float = 0.0) -> dict:
    return {"events": log.read("events.jsonl", since=since)}


@tool("List available plugins of every kind (datasets, frontends, families, simulators, targets).", {}, lane="inline")
def plugins() -> dict:
    from chiplab.plugins import registry
    return {k: registry.available(k) for k in registry.KINDS}
