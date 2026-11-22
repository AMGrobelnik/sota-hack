"""Regenerate the shipped gate-estimator coefficients (chiplab/ir/estimator_default.json).

Builds a diverse, deterministic calibration set, synthesises every design with the lab's default flow (Yosys,
simple gates, ABC effort fast), fits non-negative least squares on the IR features, reports the fit on a held-out
20% split (per design family and per size band, with the previous shipped fit scored on the same designs), then
fits on all designs for the shipped coefficients.

    .venv/bin/python scripts/refit_estimator.py [--m3-designs designs.json] [--scale-results results.json]
        [--rows runs/estimator_rows.jsonl] [--out chiplab/ir/estimator_default.json] [--timeout 900] [--wrapper]

Design mix (family in brackets):
  * intnn siblings of the spike fixture (H x bits x L grid, ternary; the M3 benchmark's generator, or its
    designs.json if given), random multi-layer k-bit intnn, and large intnn of about 1k to 30k weights [intnn];
  * multi-head chips, with and without and / or / k-of-n fusion [composed];
  * logic-gate networks shaped like torchlogix exports: layers of 2-input LUT lanes and a GroupSum popcount and
    argmax [torchlogix];
  * XGBoost ensembles quantised by TreeLUT (trained in a worker process, as the lab's own ingest does) [treelut];
  * intnn and composed designs emitted with the alkaid optimiser [alkaid];
  * measured designs from the scale package's results.json, when given (each row's IR and gate count).
The random fuzz programs of tests/test_ir_fuzz are left out on purpose: they are adversarial op soups that
synthesis mostly collapses to a handful of gates, not model-like designs.

--rows caches every synthesis result (design id, optimiser, gates, seconds or the timeout) so a refit after a
feature change re-synthesises nothing. A design that times out is recorded and left out of the fit.
--wrapper also calibrates the streaming wrapper's sky130 area per flip-flop (core and wrapper mapped separately).
CPU workers: CHIPLAB_CPU_WORKERS (config.lanes()).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import signal
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent.parent

from chiplab import config  # noqa: E402
from chiplab.emit.verilog import emit  # noqa: E402
from chiplab.hw.yosys import SynthError, synth_generic, version  # noqa: E402
from chiplab.ingest.compose import compose  # noqa: E402
from chiplab.ingest.intnn import to_ir  # noqa: E402
from chiplab.ir.estimate import FIT_FEATURES, family, features, stream_wrapper_ffs  # noqa: E402
from chiplab.ir.schema import design_id, validate  # noqa: E402

SIZE_BANDS = ((0, 500), (500, 5000), (5000, 50000), (50000, 10 ** 9))


def sibling(fx, h, bits, lanes, seed):
    rng = random.Random(f"{h}-{bits}-{lanes}-{seed}")
    flat = [w for row in fx["W1"] for w in row]
    p0 = flat.count(0) / len(flat)
    t = lambda: 0 if rng.random() < p0 else rng.choice((-1, 1))
    return {"cfg": {**fx["cfg"], "L": lanes, "bits": bits, "H": h}, "W1": [[t() for _ in range(lanes)] for _ in range(h)],
            "b1": [rng.choice(fx["b1"]) for _ in range(h)], "shift": fx["shift"], "W2": [t() for _ in range(h)],
            "b2": fx["b2"], "amax": fx["amax"]}


def _mlp(name, r, L, bits, signed, widths, wmax, ncls):
    nodes, src, n_in = [], "x", L
    for li, h in enumerate(widths):
        W = r.integers(-wmax, wmax + 1, size=(h, n_in)); W[r.random(W.shape) < 0.3] = 0
        nodes += [{"id": f"m{li}", "op": "matvec", "src": src, "W": W.tolist(), "b": r.integers(-8, 9, size=h).tolist()},
                  {"id": f"s{li}", "op": "shift", "src": f"m{li}", "k": int(r.integers(0, 3))},
                  {"id": f"c{li}", "op": "clip", "src": f"s{li}", "lo": 0, "hi": int(r.choice([7, 15]))}]
        src, n_in = f"c{li}", h
    if ncls is None:
        ncls = int(r.choice([1, 1, 3]))                       # drawn after the layers (keeps old seeds' designs)
    W = r.integers(-wmax, wmax + 1, size=(ncls, n_in))
    nodes.append({"id": "o", "op": "matvec", "src": src, "W": W.tolist(), "b": r.integers(-4, 5, size=ncls).tolist()})
    nodes.append({"id": "y", "op": "cmp", "src": "o", "rel": "gt", "t": [0]} if ncls == 1 else {"id": "y", "op": "argmax", "src": "o"})
    return {"ir": "chipir/1", "name": name, "inputs": [{"name": "x", "lanes": L, "bits": bits, "signed": signed}],
            "nodes": nodes, "outputs": [{"name": "y", "src": "y"}], "meta": {}}


def multilayer_ir(seed):
    """Random 2-3 layer integer network with k-bit weights, written directly in chipir/1."""
    r = np.random.default_rng(seed)
    L = int(r.integers(3, 13)); bits = int(r.choice([3, 4, 6, 8])); signed = bool(r.integers(0, 2))
    wmax = int(r.choice([1, 1, 3, 7]))                       # ternary or k-bit
    widths = [int(r.choice([4, 8, 12, 16])) for _ in range(int(r.integers(1, 3)))]
    return _mlp(f"ml{seed}", r, L, bits, signed, widths, wmax, None)


# (inputs, hidden widths, input bits, weight magnitude): about 1k to 30k weights; k-bit weights only up to ~8k
LARGE_INTNN = [(32, [32], 6, 1), (32, [64], 8, 1), (64, [64], 4, 1), (64, [64], 6, 3), (48, [96], 8, 1),
               (64, [128], 6, 1), (64, [96, 32], 4, 1), (96, [96], 4, 3), (128, [128], 4, 1), (64, [192], 6, 1),
               (96, [160, 32], 4, 1), (128, [192], 4, 1), (128, [232], 4, 1), (160, [160, 24], 3, 1)]


def large_intnn_ir(i):
    L, widths, bits, wmax = LARGE_INTNN[i]
    r = np.random.default_rng(7000 + i)
    return _mlp(f"big{i}", r, L, bits, False, widths, wmax, int(r.choice([1, 4])))


def fused_ir(seed):
    """2-3 single-decision heads on one chip, fused by and / or / k-of-n."""
    r = np.random.default_rng(800 + seed)
    nh = int(r.integers(2, 4))
    heads = {}
    for h in range(nh):
        rr = np.random.default_rng(810 + 7 * seed + h)
        heads[f"h{h}"] = _mlp("h", rr, int(rr.integers(3, 10)), int(rr.choice([4, 6, 8])), False,
                              [int(rr.choice([4, 8, 12]))], int(rr.choice([1, 3])), 1)
    op = ["and", "or", "kofn"][seed % 3]
    fusion = [{"name": "f", "op": op, "inputs": [f"h{h}_y" for h in range(nh)], **({"k": 2} if op == "kofn" else {})}]
    return compose(heads, fusion, shared_inputs=False, name=f"fz{seed}")


def torchlogix_ir(seed):
    """A logic-gate network as torchlogix exports it (chiplab.ingest.torchlogix.to_ir): LogicDense layers of
    2-input LUT lanes with random connections and gates, then GroupSum (popcount per class) and argmax (every
    fifth seed: no GroupSum). Gate choice: uniform over the 16 two-input functions, or a trained-like mix with
    many pass-through gates. Measured: next to a popcount, synthesis folds most LUT gates into the adder tree, so
    the popcount dominates; without one each LUT costs about one gate."""
    r = np.random.default_rng(3000 + seed)
    in_dim = int(r.choice([32, 64, 128, 256, 512]))
    depth = int(r.integers(1, 5))
    k = int(r.choice([2, 4, 10]))
    width = int(r.choice([32, 64, 128, 256, 512, 1024, 2048])) // k * k
    width = min(width, 512 * k, 4 * in_dim // k * k)   # Yosys 0.71's reader crashes on a 1024-term popcount line;
    passthrough = 0.4 if seed % 2 else 0.0             # wide layers on few inputs are mostly duplicate functions
    nodes, prev, n_prev = [], "x", in_dim
    for li in range(depth):
        sel = [[int(a), int(b)] for a, b in r.integers(0, n_prev, size=(width, 2))]
        tabs = []
        for _ in range(width):
            g = int(r.choice([3, 5])) if r.random() < passthrough else int(r.integers(1, 15))   # 3 = a, 5 = b; no constants
            tabs.append([(g >> i) & 1 for i in range(4)])
        nodes.append({"id": f"g{li}", "op": "lut", "src": prev, "inputs": sel, "tables": tabs})
        prev, n_prev = f"g{li}", width
    if seed % 5 == 4:                    # no GroupSum: the last layer's bits are the outputs (to_ir without GroupSum)
        return validate({"ir": "chipir/1", "name": f"tlx{seed}", "inputs": [{"name": "x", "lanes": in_dim, "bits": 1, "signed": False}],
                         "nodes": nodes, "outputs": [{"name": "y", "src": prev}], "meta": {"format": "torchlogix", "generator": "refit_estimator"}})
    g = width // k
    nodes.append({"id": "scores", "op": "matvec", "src": prev, "W": [[1 if j // g == c else 0 for j in range(width)] for c in range(k)]})
    nodes.append({"id": "cls", "op": "argmax", "src": "scores"})
    return validate({"ir": "chipir/1", "name": f"tlx{seed}", "inputs": [{"name": "x", "lanes": in_dim, "bits": 1, "signed": False}],
                     "nodes": nodes, "outputs": [{"name": "y", "src": "cls"}, {"name": "scores", "src": "scores"}],
                     "meta": {"format": "torchlogix", "generator": "refit_estimator"}})


TREELUT_SPECS = [{"seed": s, "n_feat": [4, 6, 8, 12, 16, 24, 32][s % 7], "w_feature": [3, 4, 5, 6, 8][s % 5],
                  "w_tree": [2, 3, 4][s % 3], "n_est": [4, 8, 12, 20, 30, 45, 60][(s * 3) % 7],
                  "depth": [2, 3, 4, 5][(s * 5) % 4], "ncls": [2, 2, 3, 5][(s * 7) % 4]} for s in range(64)]


def _treelut_worker(spec_path: str) -> None:
    """In a fresh process (xgboost next to torch can abort on macOS): train each spec, quantise with TreeLUT, print
    the chipir/1 documents as JSON."""
    import xgboost as xgb
    from chiplab.ingest.treelut import from_treelut, treelut_classifier
    out = []
    for sp in json.loads(Path(spec_path).read_text()):
        r = np.random.default_rng(sp["seed"])
        hi = 2 ** sp["w_feature"]
        X = r.integers(0, hi, size=(3000, sp["n_feat"]))
        w = r.normal(size=sp["n_feat"])
        z = (X / hi - 0.5) @ w + 0.5 * np.sin(6 * X[:, 0] / hi)
        qs = np.quantile(z, np.linspace(0, 1, sp["ncls"] + 1)[1:-1])
        y = np.searchsorted(qs, z)
        kw = {"objective": "binary:logistic"} if sp["ncls"] == 2 else {"objective": "multi:softmax", "num_class": sp["ncls"]}
        m = xgb.XGBClassifier(n_estimators=sp["n_est"], max_depth=sp["depth"], learning_rate=0.3, **kw).fit(X, y)
        tl = treelut_classifier(m, w_feature=sp["w_feature"], w_tree=sp["w_tree"])
        out.append(from_treelut(tl, name=f"tl{sp['seed']}"))
    sys.stdout.write(json.dumps(out))


def treelut_irs(specs, timeout=900) -> list[dict]:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(specs, f)
    try:
        p = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--treelut-worker", f.name],
                           capture_output=True, text=True, timeout=timeout)
    finally:
        os.unlink(f.name)
    if p.returncode != 0:
        print(f"treelut worker failed (rc {p.returncode}), no treelut designs: {(p.stderr or p.stdout)[-400:]}", file=sys.stderr)
        return []
    return json.loads(p.stdout)


def _n_weights(ir) -> int:
    return sum(sum(1 for w in row if w) for nd in ir["nodes"] if nd["op"] == "matvec" for row in nd["W"])


def build_set(m3_designs: Path | None, families: set[str] | None = None) -> list[tuple[str, dict, str | None]]:
    """(kind, ir, optimizer) triples; kind is the generator, family(ir, optimizer) the estimator's family."""
    want = lambda f: families is None or f in families
    fx = json.loads((HERE / "fixtures" / "spike_best.json").read_text())
    out = []
    if want("intnn"):
        out.append(("fixture", to_ir(fx, name="fixture"), None))
        if m3_designs and m3_designs.exists():
            for d in json.loads(m3_designs.read_text())["designs"]:
                if d["name"] != "fixture":
                    out.append(("intnn_sibling", to_ir(d["model"], name=d["name"]), None))
        else:
            for h in (4, 8, 12, 16, 24, 32):
                for bits in (4, 6, 8):
                    for L in (4, 8, 12):
                        for seed in range(2):
                            out.append(("intnn_sibling", to_ir(sibling(fx, h, bits, L, seed), name=f"s{h}_{bits}_{L}_{seed}"), None))
        out += [("multilayer", multilayer_ir(s), None) for s in range(70)]
        out += [("intnn_large", large_intnn_ir(i), None) for i in range(len(LARGE_INTNN))]
    if want("composed"):
        for s in range(24):
            a, b = multilayer_ir(500 + s), multilayer_ir(600 + s)
            try:
                out.append(("composed", compose({"a": a, "b": b}, [], shared_inputs=False, name=f"cmp{s}"), None))
            except Exception:
                pass
        out += [("fused", fused_ir(s), None) for s in range(18)]
    if want("torchlogix"):
        out += [("torchlogix", torchlogix_ir(s), None) for s in range(50)]
    if want("treelut"):
        out += [("treelut", ir, None) for ir in treelut_irs(TREELUT_SPECS)]
    if want("alkaid"):
        base = [k for k in out if k[0] in ("intnn_sibling", "multilayer", "composed", "fused")]
        pick = base[::3] + [("intnn_large", large_intnn_ir(i), None) for i in range(len(LARGE_INTNN))
                            if _n_weights(large_intnn_ir(i)) <= 9000]
        out += [("alkaid_" + k, ir, "alkaid") for k, ir, _ in pick]
    seen, uniq = set(), []
    for kind, ir, opt in out:
        i = (design_id(ir), opt)
        if i not in seen:
            seen.add(i); uniq.append((kind, ir, opt))
    return uniq


def scale_rows(path: Path) -> list[tuple[str, dict, str | None, int]]:
    """Measured designs from the scale package: a list (or {"designs"/"results": [...]}) of rows that carry a
    chipir/1 document (ir, or ir_path relative to the file) and a measured generic gate count (gates)."""
    doc = json.loads(path.read_text())
    rows = doc if isinstance(doc, list) else doc.get("designs") or doc.get("results") or []
    out = []
    for r in rows:
        ir = r.get("ir")
        if ir is None and r.get("ir_path"):
            p = (path.parent / r["ir_path"]).resolve()
            ir = json.loads(p.read_text()) if p.exists() else None
        g = r.get("gates") or (r.get("metrics") or {}).get("gates")
        if isinstance(ir, dict) and isinstance(g, (int, float)) and g > 0:
            out.append(("scale", ir, r.get("optimizer"), int(g)))
    return out


def _reap_orphans():
    """Kill yosys / yosys-abc processes of this process group whose parent died: subprocess's timeout kills yosys
    but not the ABC child it started, and orphaned solvers otherwise run for hours."""
    try:
        ps = subprocess.run(["ps", "-axo", "pid=,ppid=,pgid=,comm="], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return
    me = os.getpgrp()
    for line in ps.splitlines():
        parts = line.split(None, 3)
        if len(parts) == 4 and parts[1] == "1" and parts[2] == str(me) and "yosys" in parts[3]:
            try:
                os.kill(int(parts[0]), signal.SIGKILL)
            except OSError:
                pass


def _key(ir, opt) -> str:
    return f"{design_id(ir)}|{opt or ''}"


def synth_one(item, timeout=900):
    kind, ir, opt = item
    t0 = time.time()
    try:
        with tempfile.TemporaryDirectory() as td:
            if opt:
                from chiplab.emit.optimized import emit_optimized
                text, info = emit_optimized(ir, optimizer=opt, timeout=timeout)
            else:
                text, info = emit(ir)
            p = Path(td) / "d.v"; p.write_text(text)
            r = synth_generic(p, info["top"], Path(td) / "s", effort="fast", timeout=timeout)
        return {"key": _key(ir, opt), "kind": kind, "gates": r["gates"], "seconds": round(time.time() - t0, 1)}
    except (SynthError, RuntimeError, subprocess.TimeoutExpired) as e:
        _reap_orphans()
        why = "timeout" if "timed out" in str(e) or isinstance(e, subprocess.TimeoutExpired) else "error"
        return {"key": _key(ir, opt), "kind": kind, "gates": None, "error": why, "detail": str(e)[-300:],
                "seconds": round(time.time() - t0, 1)}


def synth_all(items, rows_path: Path | None, timeout: int) -> dict[str, dict]:
    done = {}
    if rows_path and rows_path.exists():
        for line in rows_path.read_text().splitlines():
            if line.strip():
                r = json.loads(line); done[r["key"]] = r
    todo = [it for it in items if _key(it[1], it[2]) not in done]
    todo.sort(key=lambda it: _n_weights(it[1]))           # small first: a slow giant never holds up the rest
    workers = config.lanes()["cpu"]
    print(f"{len(items)} designs, {len(items) - len(todo)} cached, {len(todo)} to synthesise on {workers} workers", flush=True)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for r in ex.map(lambda it: synth_one(it, timeout), todo):
            done[r["key"]] = r
            if rows_path:
                with open(rows_path, "a") as f:
                    f.write(json.dumps(r) + "\n")
            if r.get("error") or r["seconds"] > 60:
                print(f"  {r['kind']} {r['key'][:40]}: {r.get('error') or r['gates']} in {r['seconds']}s", flush=True)
    return done


def nnls_fit(X, y, weighting="none"):
    from scipy.optimize import nnls
    w = {"none": np.ones_like(y), "sqrt": 1 / np.sqrt(y), "rel": 1 / y}[weighting]
    coef, _ = nnls(X * w[:, None], y * w)
    pred = X @ coef
    return coef, pred, _r2(y, pred)


def _r2(y, p):
    return float(1 - ((y - p) ** 2).sum() / max(((y - y.mean()) ** 2).sum(), 1e-9))


def _err(y, p):
    return np.abs(p - y) / y


def _heldout(key: str) -> bool:
    return int(hashlib.sha256(key.encode()).hexdigest(), 16) % 5 == 0       # 20%, stable across reruns


def _stats(y, p) -> dict:
    e = _err(y, p) * 100
    return {"n_heldout": int(len(y)), "median_abs_pct_err": round(float(np.median(e)), 1),
            "p90_abs_pct_err": round(float(np.percentile(e, 90)), 1), "r2": round(_r2(y, p), 3) if len(y) > 2 else None}


def _predict(coefs: dict, fams: list[str], F: list[dict]) -> np.ndarray:
    out = []
    for fam, f in zip(fams, F):
        c = (coefs.get("families") or {}).get(fam) or coefs
        out.append(max(1.0, float(np.dot(c["coef"], [f.get(k, 0) for k in c["features"]]))))
    return np.array(out)


def _band(g) -> str:
    for lo, hi in SIZE_BANDS:
        if lo <= g < hi:
            return f"{lo}-{hi}" if hi < 10 ** 9 else f"{lo}+"
    return "?"


def fit(rows, F, fams, keys):
    """Global NNLS (weighting chosen on the held-out split) plus a per-family override where the family's own
    fit is clearly better on its held-out designs. Returns the shipped dict without metadata."""
    X = np.array([[f[k] for k in FIT_FEATURES] for f in F], float)
    y = np.array([r["gates"] for r in rows], float)
    held = np.array([_heldout(k) for k in keys])
    fams = np.array(fams)
    trials = {}
    for weighting in ("none", "sqrt", "rel"):
        c, _, r2t = nnls_fit(X[~held], y[~held], weighting)
        ph = np.maximum(X[held] @ c, 1)
        trials[weighting] = (c, r2t, _r2(y[held], ph), float(np.median(_err(y[held], ph)) * 100))
    weighting = min(trials, key=lambda k: trials[k][3])
    coef_tr = trials[weighting][0]
    overrides_tr = {}
    for fam in sorted(set(fams)):
        tr, ho = (fams == fam) & ~held, (fams == fam) & held
        if tr.sum() < 12 or ho.sum() < 3:
            continue
        cf, _, _ = nnls_fit(X[tr], y[tr], weighting)
        e_own = np.median(_err(y[ho], np.maximum(X[ho] @ cf, 1)))
        e_glob = np.median(_err(y[ho], np.maximum(X[ho] @ coef_tr, 1)))
        if e_own < 0.8 * e_glob:
            overrides_tr[fam] = cf
    trained = {"features": list(FIT_FEATURES), "coef": coef_tr.tolist(),
               "families": {k: {"features": list(FIT_FEATURES), "coef": v.tolist()} for k, v in overrides_tr.items()}}
    # shipped: same choices, refitted on every design
    coef_all, _, r2_all = nnls_fit(X, y, weighting)
    fam_all = {}
    for fam in overrides_tr:
        m = fams == fam
        fam_all[fam] = {"features": list(FIT_FEATURES), "coef": [round(float(v), 5) for v in nnls_fit(X[m], y[m], weighting)[0]],
                        "n": int(m.sum())}
    return {"weighting": weighting, "trials": trials, "trained": trained, "held": held, "y": y,
            "coef": [round(float(v), 5) for v in coef_all], "families": fam_all, "r2_all": r2_all}


def report(coefs: dict, fams, F, y, held, sizes) -> dict:
    p = _predict(coefs, list(fams), F)
    out = {"all": _stats(y[held], p[held]), "per_family": {}, "per_size": {}}
    for fam in sorted(set(fams)):
        m = held & (np.array(fams) == fam)
        if m.sum():
            out["per_family"][fam] = _stats(y[m], p[m])
    for b in sorted(set(sizes), key=lambda s: int(s.split("-")[0].rstrip("+"))):
        m = held & (np.array(sizes) == b)
        if m.sum():
            out["per_size"][b] = _stats(y[m], p[m])
    return out


def calibrate_wrapper(items, n=14, timeout=900) -> dict:
    """sky130 area of the streaming wrapper = mapped area of stream_tt.v minus mapped area of the bare core, over
    a spread of designs; least squares area = a * wrapper_ffs + b. Also checks the structural flip-flop count
    against the mapped netlist's flip-flop cells."""
    from chiplab.emit.stream import emit_stream
    from chiplab.hw.pdk import map_to_process
    pick = [it for it in items if it[2] is None]
    pick = sorted(pick, key=lambda it: _n_weights(it[1]))
    pick = pick[:: max(1, len(pick) // n)][:n]
    rows = []
    for kind, ir, _ in pick:
        try:
            with tempfile.TemporaryDirectory() as td:
                text, info = emit(ir)
                (Path(td) / "c.v").write_text(text)
                core = map_to_process(Path(td) / "c.v", info["top"], Path(td) / "c", "sky130", timeout=timeout)
                st, sinfo = emit_stream(ir, info, tt=True)
                (Path(td) / "s.v").write_text(st)
                wrap = map_to_process(Path(td) / "s.v", sinfo["top"], Path(td) / "s", "sky130", timeout=timeout)
        except (SynthError, OSError) as e:
            _reap_orphans()
            print(f"  wrapper calibration skipped {kind}: {str(e)[:120]}", flush=True)
            continue
        if wrap["area_um2"] is None or core["area_um2"] is None:          # no area line (e.g. an empty core)
            continue
        ff_cells = sum(v for k, v in wrap["cells_by_type"].items() if "__df" in k or "__edf" in k or "__sdf" in k)
        rows.append({"kind": kind, "ffs": stream_wrapper_ffs(ir), "ff_cells": ff_cells,
                     "area": wrap["area_um2"] - core["area_um2"]})
    if len(rows) < 3:
        return {}
    A = np.array([[r["ffs"], 1.0] for r in rows]); b = np.array([r["area"] for r in rows])
    (a, c), *_ = np.linalg.lstsq(A, b, rcond=None)
    pred = A @ np.array([a, c])
    return {"area_um2_per_ff": round(float(a), 3), "area_um2_const": round(float(c), 1), "n": len(rows),
            "median_abs_pct_err": round(float(np.median(np.abs(pred - b) / np.maximum(b, 1)) * 100), 1),
            "ffs_formula_vs_cells": [[r["ffs"], r["ff_cells"]] for r in rows],
            "basis": "sky130_fd_sc_hd synthesis area of stream_tt.v minus the bare core, before layout"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--m3-designs", type=Path, default=None)
    ap.add_argument("--scale-results", type=Path, default=None, help="the scale package's results.json")
    ap.add_argument("--rows", type=Path, default=None, help="jsonl cache of synthesis results")
    ap.add_argument("--families", default=None, help="comma list: only build these families (debugging)")
    ap.add_argument("--timeout", type=int, default=900, help="seconds per design (synthesis or optimiser)")
    ap.add_argument("--wrapper", action="store_true", help="also calibrate the stream wrapper's sky130 area")
    ap.add_argument("--synth-only", action="store_true", help="synthesise into --rows, fit nothing")
    ap.add_argument("--out", type=Path, default=HERE / "chiplab" / "ir" / "estimator_default.json")
    ap.add_argument("--treelut-worker", default=None, help=argparse.SUPPRESS)
    a = ap.parse_args()
    if a.treelut_worker:
        return _treelut_worker(a.treelut_worker)
    t0 = time.time()
    items = build_set(a.m3_designs, set(a.families.split(",")) if a.families else None)
    done = synth_all(items, a.rows, a.timeout)
    if a.synth_only:
        return
    triples = [(kind, ir, opt, done[_key(ir, opt)]) for kind, ir, opt in items]
    failed = [{"kind": k, "key": r["key"], "error": r.get("error"), "seconds": r["seconds"]} for k, _, _, r in triples if r["gates"] is None]
    used = [(k, ir, opt, r) for k, ir, opt, r in triples if r["gates"]]       # constant-output designs synthesise to 0
    if a.scale_results and a.scale_results.exists():
        used += [(k, ir, opt, {"key": _key(ir, opt), "gates": g}) for k, ir, opt, g in scale_rows(a.scale_results)]
    rows = [r for *_, r in used]
    F = [features(ir) for _, ir, _, _ in used]
    fams = [family(ir, opt) for _, ir, opt, _ in used]
    keys = [r["key"] for r in rows]
    kinds = [k for k, *_ in used]
    res = fit(rows, F, fams, keys)
    y, held = res["y"], res["held"]
    sizes = [_band(g) for g in y]
    after = report(res["trained"], fams, F, y, held, sizes)
    before = None
    if a.out.exists():                                            # the fit being replaced, on the same designs
        old = json.loads(a.out.read_text())
        old.setdefault("features", ["adder_bits", "cmp_bits", "mux_bits", "lut_entries"])
        before = report({k: old[k] for k in ("features", "coef")}, fams, F, y, held, sizes)
    per_kind = {}
    for k in sorted(set(kinds)):
        m = np.array([kk == k for kk in kinds]) & held
        if m.sum():
            per_kind[k] = _stats(y[m], _predict(res["trained"], [f for f, mm in zip(fams, m) if mm], [f for f, mm in zip(F, m) if mm]))
    tr = res["trials"][res["weighting"]]
    out = {"features": list(FIT_FEATURES), "coef": res["coef"], "families": res["families"], "n": len(rows),
           "weighting": res["weighting"],
           "trials": {k: {"r2_heldout": round(v[2], 4), "median_abs_pct_err_heldout": round(v[3], 1)} for k, v in res["trials"].items()},
           "r2_train": round(tr[1], 4), "r2_heldout": round(after["all"]["r2"], 4), "r2_all": round(res["r2_all"], 4),
           "median_abs_pct_err_heldout": after["all"]["median_abs_pct_err"], "heldout_fraction": 0.2,
           "per_family_heldout": after["per_family"], "per_size_heldout": after["per_size"], "per_kind_heldout": per_kind,
           "before": ({"note": "the previous shipped fit scored on the same held-out designs", **before} if before else None),
           "mix": {k: kinds.count(k) for k in sorted(set(kinds))},
           "family_mix": {k: fams.count(k) for k in sorted(set(fams))},
           "gates_range": [int(y.min()), int(y.max())], "not_fitted": failed,
           "flow": f"yosys {version()} simple gates, ABC effort fast", "date": time.strftime("%Y-%m-%d"),
           "data": ("generated designs synthesised by scripts/refit_estimator.py" +
                    (f" plus {sum(1 for k in kinds if k == 'scale')} measured designs from the scale package" if "scale" in kinds else "")),
           "basis": (f"estimate (shipped fit on {len(rows)} synthesised designs in {len(set(fams))} families, held-out "
                     f"r²={after['all']['r2']:.2f}, median error {after['all']['median_abs_pct_err']:.0f}% on a 20% held-out split)")}
    if a.wrapper:
        out["wrapper"] = calibrate_wrapper(items, timeout=a.timeout)
    elif a.out.exists() and json.loads(a.out.read_text()).get("wrapper"):
        out["wrapper"] = json.loads(a.out.read_text())["wrapper"]
    a.out.write_text(json.dumps(out, indent=1) + "\n")
    show = ("n", "coef", "families", "weighting", "r2_heldout", "median_abs_pct_err_heldout", "family_mix",
            "per_family_heldout", "per_size_heldout", "before", "not_fitted", "wrapper")
    print(json.dumps({k: out.get(k) for k in show}, indent=1))
    print(f"wrote {a.out} in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
