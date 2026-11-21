"""Take every gallery example model -> chip through the lab's CLI only, all examples together, and record what the
CLI printed.

    export CHIPLAB_USER_DIR=... CHIPLAB_CONFIG=...
    chiplab/.venv/bin/chiplab workers &                  # the lab's job workers (cpu, gpu, docker lanes)
    chiplab/.venv/bin/python m3/examples/run_gallery.py [name ...]

Every stage goes through the lab's batch tools, all examples at once, never one design at a time:
  1. ingest-model for every example and every fusion head, all at once in parallel CLI processes (not the job
     worker: see parallel() below; a failed xgboost_json ingest is retried as format chipir from chipir.json, the
     lab's own TreeLUT conversion, and both answers are kept);
  2. submit-batch compose-chip for the fusion examples (heads -> one chip with and / or / k-of-n logic);
  3. synthesize-batch for every chip;
  4. one wave of submit-batch jobs: count-luts (xc7, ice40), map-to-process (sky130), simulate on the example's
     vectors with its expected first output (level 1), simulate on 100,000 random vectors, prove-equivalence
     (level 2), rtl-simulate of the Tiny Tapeout streaming wrapper on the vectors with every expected output
     and of the generic FPGA wrapper, which shows every output bit (level 3), tt-package without harden (Tiny Tapeout tiles);
  5. verification-level for every chip.
Each answer goes to <name>/cli/<step>.json with the home path replaced by ~; the summary goes to <name>/result.json
and RESULTS.md is written from all of them by make_results.py.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent
REPO = OUT.parents[1]
CLI = REPO / "chiplab" / ".venv" / "bin" / "chiplab"
SCRATCH = REPO / "chiplab" / "runs" / "gallery-args"
HOME = str(Path.home())
POOL = ThreadPoolExecutor(16)


def scrub(x):
    if isinstance(x, str):
        return x.replace(HOME, "~")
    if isinstance(x, dict):
        return {k: scrub(v) for k, v in x.items()}
    if isinstance(x, list):
        return [scrub(v) for v in x]
    return x


def cli(tool: str, args: dict, tag: str, timeout: int = 600) -> dict:
    """One synchronous CLI call; returns its JSON with exit_code and wall_s."""
    SCRATCH.mkdir(parents=True, exist_ok=True)
    f = SCRATCH / f"{tag}.json"
    f.write_text(json.dumps(args))
    t0 = time.time()
    try:
        p = subprocess.run([str(CLI), tool, "--json-file", str(f)], capture_output=True, text=True, timeout=timeout,
                           cwd=REPO / "chiplab")
        try:
            res = json.loads(p.stdout)
        except json.JSONDecodeError:
            res = {"status": "error", "error": "no JSON on stdout", "stdout_tail": p.stdout[-2000:]}
        res = {"exit_code": p.returncode, **res}
        if p.returncode != 0:
            res["stderr_tail"] = p.stderr[-2000:]
    except subprocess.TimeoutExpired:
        res = {"exit_code": None, "status": "error", "error": f"runner timeout after {timeout} s"}
    res["wall_s"] = round(time.time() - t0, 2)
    return res


def save(name: str, step: str, res: dict) -> dict:
    res = scrub(res)
    d = OUT / name / "cli"
    d.mkdir(exist_ok=True)
    (d / f"{step}.json").write_text(json.dumps(res, indent=1, default=str) + "\n")
    return res


def batch(tool: str, items: list[tuple[str, str, dict]], *, timeout: int = 3600) -> dict:
    """items: (example, step, args). One submit-batch (synthesize-batch for synthesize) call, then poll job-result
    until every job is done or failed. Returns {(example, step): tool answer}."""
    if not items:
        return {}
    t0 = time.time()
    if tool == "synthesize":
        sub = cli("synthesize-batch", {"design_ids": [a["design_id"] for _, _, a in items]}, f"batch_{tool}")
    else:
        sub = cli("submit-batch", {"tool": tool, "args_list": [a for _, _, a in items]}, f"batch_{tool}")
    ids = sub.get("job_ids")
    if not ids:
        err = {"exit_code": sub.get("exit_code"), "status": "error", "error": f"{tool} batch submit failed: {sub}"}
        return {(n, s): err for n, s, _ in items}
    print(f"[{time.strftime('%H:%M:%S')}] {tool}: {len(ids)} jobs submitted", flush=True)
    pending = dict(zip(ids, ((n, s) for n, s, _ in items)))
    out = {}
    while pending and time.time() - t0 < timeout:
        res = list(POOL.map(lambda j: (j, cli("job-result", {"job_id": j}, f"jr_{j}", 60)), list(pending)))
        for j, r in res:
            if r.get("ready"):
                inner = r.get("result")
                inner = inner if isinstance(inner, dict) else {"status": "error", "error": str(inner)}
                ok = r.get("state") == "done" and inner.get("status", "ok") == "ok"
                out[pending.pop(j)] = {"exit_code": 0 if ok else 1, "job_id": j, "job_state": r.get("state"), **inner}
        if pending:
            time.sleep(2)
    for j, key in pending.items():
        out[key] = {"exit_code": None, "status": "error", "job_id": j, "error": f"job not finished after {timeout} s"}
    print(f"[{time.strftime('%H:%M:%S')}] {tool}: {len(items)} done in {time.time() - t0:.1f} s wall", flush=True)
    return out


def parallel(tool: str, items: list[tuple[str, str, dict]]) -> dict:
    """All items at once, each in its own `chiplab <tool>` process. Used for ingest-model: in the shared job worker
    an xgboost_json ingest next to a torchlogix ingest crashed the CPU lane (two libomp runtimes in one process,
    SIGSEGV in libomp; see RESULTS.md and proposed/ingest-in-subprocess.patch)."""
    t0 = time.time()
    res = list(POOL.map(lambda it: (it, cli(tool, it[2], f"{it[0]}__{it[1]}")), items))
    print(f"[{time.strftime('%H:%M:%S')}] {tool}: {len(items)} parallel CLI calls in {time.time() - t0:.1f} s wall",
          flush=True)
    return {(n, s): {**r, "via": "parallel CLI processes"} for (n, s, _), r in res}


def ok(r: dict) -> bool:
    return r.get("exit_code") == 0


def err(r: dict) -> str:
    return str(r.get("error") or r.get("stderr_tail") or r.get("stdout_tail") or "")[-600:]


def ingest_args(d: Path, fmt: str, model, args: dict, file: str | None = None) -> dict:
    a = {"format": fmt, **args}
    if fmt == "torchlogix":
        a["path"] = str(d / a["path"])
    else:
        a["model"] = json.loads((d / file).read_text()) if file else model
    return a


def main(names: list[str]) -> None:
    t_all = time.time()
    names = names or sorted(p.name for p in OUT.iterdir() if (p / "chip.json").exists())
    E = {}
    for n in names:
        d = OUT / n
        V = np.load(d / "vectors.npz")
        E[n] = {"d": d, "chip": json.loads((d / "chip.json").read_text()),
                "model": json.loads((d / "model.json").read_text()),
                "ins": {k[3:]: V[k].tolist() for k in V.files if k.startswith("in_")},
                "outs": {k[4:]: V[k].tolist() for k in V.files if k.startswith("out_")},
                "steps": {}, "failure": None}

    # 1. ingest (direct examples and fusion heads), with the chipir fallback for a failed xgboost_json
    items, fb = [], {}
    for n, e in E.items():
        c = e["chip"]
        if c["kind"] == "ingest":
            items.append((n, "ingest", ingest_args(e["d"], c["format"], e["model"], c["args"])))
            if "fallback" in c:
                f = c["fallback"]
                fb[(n, "ingest")] = ingest_args(e["d"], f["format"], f.get("model"), f["args"], f.get("file"))
        else:
            for h, spec in e["model"]["heads"].items():
                items.append((n, f"ingest_{h}", ingest_args(e["d"], spec["format"], spec["model"], spec["args"])))
                if "fallback" in spec:
                    f = spec["fallback"]
                    fb[(n, f"ingest_{h}")] = ingest_args(e["d"], f["format"], f.get("model"), f["args"], f.get("file"))
    res = parallel("ingest-model", items)
    retry = [(n, s + "_chipir", fb[(n, s)]) for (n, s), r in res.items() if not ok(r) and (n, s) in fb]
    res.update(parallel("ingest-model", retry))
    for (n, s), r in res.items():
        E[n]["steps"][s] = save(n, s, r)

    def final_ingest(n, s):
        st = E[n]["steps"]
        return st.get(s + "_chipir") if not ok(st[s]) and s + "_chipir" in st else st[s]

    # 2. compose the fusion chips
    items = []
    for n, e in E.items():
        if e["chip"]["kind"] == "ingest":
            r = final_ingest(n, "ingest")
            if ok(r):
                e["design_id"], e["ingest"] = r["design_id"], r
            else:
                e["failure"] = f"ingest failed: {err(r)}"
            continue
        heads = {}
        for h in e["model"]["heads"]:
            r = final_ingest(n, f"ingest_{h}")
            if not ok(r):
                e["failure"] = f"ingest of head {h} failed: {err(r)}"
                break
            heads[h] = r["design_id"]
        else:
            items.append((n, "compose", {"heads": heads, "fusion": e["chip"]["fusion"],
                                         "shared_inputs": e["chip"]["shared_inputs"], "name": n}))
    for (n, s), r in batch("compose_chip", items).items():
        E[n]["steps"][s] = save(n, s, r)
        if ok(r):
            E[n]["design_id"], E[n]["ingest"] = r["design_id"], r
        else:
            E[n]["failure"] = f"compose failed: {err(r)}"
    live = {n: e for n, e in E.items() if e.get("design_id")}

    # 3. synthesize every chip in one batch
    for (n, s), r in batch("synthesize", [(n, "synthesize", {"design_id": e["design_id"]})
                                          for n, e in live.items()]).items():
        E[n]["steps"][s] = save(n, s, r)

    # 4. everything else in one wave of batches, all submitted before any is polled
    wave: dict[str, list] = {}
    for n, e in live.items():
        did = e["design_id"]
        ports = e["ingest"].get("ports", {})
        port_outs = [o["name"] for o in ports.get("outputs", [])] if isinstance(ports, dict) else []
        e["chip_outputs"] = port_outs
        outs = e["outs"]
        first = port_outs[0] if port_outs else next(iter(outs))
        exp_all = {o: outs[o] for o in (port_outs or outs) if o in outs}
        wave.setdefault("count_luts", []).extend([(n, "luts_xc7", {"design_id": did, "family": "xc7"}),
                                                  (n, "luts_ice40", {"design_id": did, "family": "ice40"})])
        wave.setdefault("map_to_process", []).append((n, "map_sky130", {"design_id": did, "pdk": "sky130"}))
        wave.setdefault("simulate", []).extend([
            (n, "simulate_vectors", {"design_id": did, "inputs": "vectors", "vectors": e["ins"],
                                     "expected": outs[first], "device": "auto"}),
            (n, "simulate_random", {"design_id": did, "inputs": "random", "n": 100000, "device": "auto"})])
        wave.setdefault("prove_equivalence", []).append((n, "prove", {"design_id": did, "timeout": 600}))
        wave.setdefault("rtl_simulate", []).append((n, "rtlsim_tt", {"design_id": did, "vectors": e["ins"],
                                                                     "expected": exp_all, "tt": True}))
        # the generic (FPGA) wrapper exposes every output bit; the TT one only the low 7 (see `truncated`)
        wave["rtl_simulate"].append((n, "rtlsim_generic", {"design_id": did, "vectors": e["ins"],
                                                           "expected": exp_all, "tt": False}))
        wave.setdefault("tt_package", []).append((n, "tt_package", {"design_id": did, "harden": False}))
    for fut in [POOL.submit(batch, tool, items) for tool, items in wave.items()]:
        for (n, s), r in fut.result().items():
            E[n]["steps"][s] = save(n, s, r)

    # 5. verification level (inline tool, read after all evidence exists)
    lv = list(POOL.map(lambda n: (n, cli("verification-level", {"design_id": live[n]["design_id"]}, f"lv_{n}")), live))
    for n, r in lv:
        E[n]["steps"]["level"] = save(n, "level", r)

    for n, e in E.items():
        finish(n, e)
    (OUT / "run_meta.json").write_text(json.dumps({"examples": len(E), "wall_s_all_stages": round(time.time() - t_all, 1),
                                                   "finished": time.strftime("%Y-%m-%d %H:%M:%S %Z")}, indent=1) + "\n")
    print(f"ALL DONE {len(E)} examples in {time.time() - t_all:.1f} s", flush=True)


def finish(name: str, e: dict) -> None:
    st = e["steps"]
    g = lambda s, *ks: _dig(st.get(s, {}), ks)
    ing = "compose" if "compose" in st else ("ingest_chipir" if "ingest_chipir" in st and not ok(st["ingest"])
                                             else "ingest")
    S = {
        "design_id": e.get("design_id"), "failure": e["failure"], "chip_outputs": e.get("chip_outputs"),
        "ingested_via": ing if ing != "compose" else "compose-chip",
        "gates": g("synthesize", "metrics", "gates"), "depth": g("synthesize", "metrics", "depth"),
        "ge_sky130": g("map_sky130", "metrics", "gate_equivalents"), "area_um2_sky130": g("map_sky130", "metrics", "area_um2"),
        "tt_tiles_est_sky130": g("map_sky130", "metrics", "tt_tiles_est"),
        "luts_xc7": g("luts_xc7", "metrics", "luts"), "luts_ice40": g("luts_ice40", "metrics", "luts"),
        "sim_vectors_bit_exact": g("simulate_vectors", "bit_exact"), "sim_vectors_n": g("simulate_vectors", "n"),
        "sim_vectors_pairs": g("simulate_vectors", "pairs"),
        "sim_device": g("simulate_vectors", "device"),
        "sim_random_bit_exact": g("simulate_random", "bit_exact"), "sim_random_n": g("simulate_random", "n"),
        "prove": {k: g("prove", k) for k in ("proved", "against", "method", "verification_level", "seconds")},
        "rtlsim_tt": {k: g("rtlsim_tt", k) for k in ("passed", "vectors", "mismatches", "transfers_per_frame",
                                                     "visible_output_bits", "truncated", "verification_level")},
        "rtlsim_generic": ({k: g("rtlsim_generic", k) for k in ("passed", "vectors", "mismatches", "transfers_per_frame", "truncated")}
                           if "rtlsim_generic" in st else None),
        "tt_package_tiles": g("tt_package", "tiles"), "tt_user_config_ok": g("tt_package", "user_config_ok"),
        "tt_rtl_test_passed": g("tt_package", "rtl_test_passed"),
        "level": g("level", "verification_level"), "level_meaning": g("level", "meaning"),
        "tt_package_error": (g("tt_package", "error") or "").strip()[:160] or None,
        "errors": {s: err(r) for s, r in st.items() if not ok(r)},
    }
    (OUT / name / "result.json").write_text(json.dumps(S, indent=1, default=str) + "\n")
    print(name, json.dumps(S, default=str)[:300], flush=True)


def _dig(d, ks):
    for k in ks:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def summarize_saved() -> None:
    """Rebuild every result.json from the saved <name>/cli/*.json answers, without calling the lab again."""
    for d in sorted(p for p in OUT.iterdir() if (p / "cli").is_dir()):
        st = {f.stem: json.loads(f.read_text()) for f in (d / "cli").glob("*.json")}
        r = st.get("compose") or (st.get("ingest_chipir") if not ok(st.get("ingest", {})) else st.get("ingest")) or {}
        ports = r.get("ports", {})
        outs = [o["name"] for o in ports.get("outputs", [])] if isinstance(ports, dict) else []
        failure = None if ok(r) else f"ingest/compose failed: {err(r)}"
        finish(d.name, {"steps": st, "design_id": r.get("design_id"), "chip_outputs": outs, "failure": failure})


if __name__ == "__main__":
    if sys.argv[1:] == ["--summarize"]:
        summarize_saved()
    else:
        main(sys.argv[1:])
