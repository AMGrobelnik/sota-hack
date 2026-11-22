"""Regenerate the shipped gate-estimator coefficients (chiplab/ir/estimator_default.json).

Builds a diverse, deterministic calibration set, synthesises every design with the lab's default flow (Yosys,
simple gates, ABC effort fast), fits non-negative least squares on the IR features, reports the fit on a held-out
20% split, then fits on all designs for the shipped coefficients.

    .venv/bin/python scripts/refit_estimator.py [--m3-designs path/to/designs.json] [--out chiplab/ir/estimator_default.json]

Design mix: intnn siblings of the spike fixture (H x bits x L grid, ternary; the M3 benchmark's generator, or its
designs.json if given), multi-layer and k-bit intnn, and composed multi-head chips. The random fuzz programs of
tests/test_ir_fuzz are left out on purpose: they are adversarial op soups that synthesis mostly collapses to a
handful of gates, not model-like designs, and they would bend the fit for the designs the estimator is used on.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "tests"))

from chiplab.emit.verilog import emit  # noqa: E402
from chiplab.hw.yosys import synth_generic, version  # noqa: E402
from chiplab.ingest.compose import compose  # noqa: E402
from chiplab.ingest.intnn import to_ir  # noqa: E402
from chiplab.ir.estimate import FEATURES, features  # noqa: E402
from chiplab.ir.schema import design_id  # noqa: E402


def sibling(fx, h, bits, lanes, seed):
    rng = random.Random(f"{h}-{bits}-{lanes}-{seed}")
    flat = [w for row in fx["W1"] for w in row]
    p0 = flat.count(0) / len(flat)
    t = lambda: 0 if rng.random() < p0 else rng.choice((-1, 1))
    return {"cfg": {**fx["cfg"], "L": lanes, "bits": bits, "H": h}, "W1": [[t() for _ in range(lanes)] for _ in range(h)],
            "b1": [rng.choice(fx["b1"]) for _ in range(h)], "shift": fx["shift"], "W2": [t() for _ in range(h)],
            "b2": fx["b2"], "amax": fx["amax"]}


def multilayer_ir(seed):
    """Random 2-3 layer integer network with k-bit weights, written directly in chipir/1."""
    r = np.random.default_rng(seed)
    L = int(r.integers(3, 13)); bits = int(r.choice([3, 4, 6, 8])); signed = bool(r.integers(0, 2))
    wmax = int(r.choice([1, 1, 3, 7]))                       # ternary or k-bit
    widths = [int(r.choice([4, 8, 12, 16])) for _ in range(int(r.integers(1, 3)))]
    nodes, src, n_in = [], "x", L
    for li, h in enumerate(widths):
        W = r.integers(-wmax, wmax + 1, size=(h, n_in)); W[r.random(W.shape) < 0.3] = 0
        nodes += [{"id": f"m{li}", "op": "matvec", "src": src, "W": W.tolist(), "b": r.integers(-8, 9, size=h).tolist()},
                  {"id": f"s{li}", "op": "shift", "src": f"m{li}", "k": int(r.integers(0, 3))},
                  {"id": f"c{li}", "op": "clip", "src": f"s{li}", "lo": 0, "hi": int(r.choice([7, 15]))}]
        src, n_in = f"c{li}", h
    ncls = int(r.choice([1, 1, 3]))
    W = r.integers(-wmax, wmax + 1, size=(ncls, n_in))
    nodes.append({"id": "o", "op": "matvec", "src": src, "W": W.tolist(), "b": r.integers(-4, 5, size=ncls).tolist()})
    nodes.append({"id": "y", "op": "cmp", "src": "o", "rel": "gt", "t": [0]} if ncls == 1 else {"id": "y", "op": "argmax", "src": "o"})
    return {"ir": "chipir/1", "name": f"ml{seed}", "inputs": [{"name": "x", "lanes": L, "bits": bits, "signed": signed}],
            "nodes": nodes, "outputs": [{"name": "y", "src": "y"}], "meta": {}}


def build_set(m3_designs: Path | None) -> list[tuple[str, dict]]:
    fx = json.loads((HERE / "fixtures" / "spike_best.json").read_text())
    out = [("fixture", to_ir(fx, name="fixture"))]
    if m3_designs and m3_designs.exists():
        for d in json.loads(m3_designs.read_text())["designs"]:
            if d["name"] != "fixture":
                out.append(("intnn_sibling", to_ir(d["model"], name=d["name"])))
    else:
        for h in (4, 8, 12, 16, 24, 32):
            for bits in (4, 6, 8):
                for L in (4, 8, 12):
                    for seed in range(2):
                        out.append(("intnn_sibling", to_ir(sibling(fx, h, bits, L, seed), name=f"s{h}_{bits}_{L}_{seed}")))
    out += [("multilayer", multilayer_ir(s)) for s in range(70)]
    for s in range(24):
        a, b = multilayer_ir(500 + s), multilayer_ir(600 + s)
        a["nodes"][-1] = {"id": "y", "op": "cmp", "src": "o", "rel": "gt", "t": [0]} if len(a["nodes"][-2]["W"]) == 1 else a["nodes"][-1]
        try:
            out.append(("composed", compose({"a": a, "b": b}, [], shared_inputs=False, name=f"cmp{s}")))
        except Exception:
            pass
    seen, uniq = set(), []
    for kind, ir in out:
        i = design_id(ir)
        if i not in seen:
            seen.add(i); uniq.append((kind, ir))
    return uniq


def synth_one(item):
    kind, ir = item
    with tempfile.TemporaryDirectory() as td:
        text, info = emit(ir)
        p = Path(td) / "d.v"; p.write_text(text)
        r = synth_generic(p, info["top"], Path(td) / "s", effort="fast", timeout=600)
    return kind, ir, r["gates"]


def nnls_fit(X, y, weighting="none"):
    from scipy.optimize import nnls
    w = 1 / np.sqrt(y) if weighting == "sqrt" else np.ones_like(y)
    coef, _ = nnls(X * w[:, None], y * w)
    pred = X @ coef
    r2 = 1 - ((y - pred) ** 2).sum() / max(((y - y.mean()) ** 2).sum(), 1e-9)
    return coef, pred, float(r2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--m3-designs", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=HERE / "chiplab" / "ir" / "estimator_default.json")
    a = ap.parse_args()
    t0 = time.time()
    items = build_set(a.m3_designs)
    with ThreadPoolExecutor(max_workers=max(1, (os.cpu_count() or 2) - 1)) as ex:
        rows = list(ex.map(synth_one, items))
    rows = [r for r in rows if r[2] > 0]                    # constant-output designs synthesise to nothing
    X = np.array([[features(ir)[k] for k in FEATURES] for _, ir, _ in rows], float)
    y = np.array([g for _, _, g in rows], float)
    kinds = [k for k, _, _ in rows]
    rng = np.random.default_rng(0)
    held = rng.random(len(rows)) < 0.2
    trials = {}
    for weighting in ("none", "sqrt"):   # absolute vs balanced (sqrt) weighting; keep the lower held-out error
        c, _, r2t = nnls_fit(X[~held], y[~held], weighting)
        ph = X[held] @ c
        r2h = 1 - ((y[held] - ph) ** 2).sum() / max(((y[held] - y[held].mean()) ** 2).sum(), 1e-9)
        trials[weighting] = (c, r2t, float(r2h), float(np.median(np.abs(ph - y[held]) / y[held]) * 100))
    weighting = min(trials, key=lambda k: trials[k][3])
    coef_tr, r2_tr, r2_h, mape_h = trials[weighting]
    per_kind = {}
    for k in sorted(set(kinds)):
        m = np.array([kk == k for kk in kinds]) & held
        if m.sum():
            per_kind[k] = {"n_heldout": int(m.sum()), "median_abs_pct_err": round(float(np.median(np.abs(X[m] @ coef_tr - y[m]) / y[m]) * 100), 1)}
    coef, _, r2_all = nnls_fit(X, y, weighting)
    out = {"features": list(FEATURES), "coef": [round(float(c), 5) for c in coef], "n": len(rows),
           "weighting": weighting, "trials": {k: {"r2_heldout": round(v[2], 4), "median_abs_pct_err_heldout": round(v[3], 1)} for k, v in trials.items()},
           "r2_train": round(r2_tr, 4), "r2_heldout": round(float(r2_h), 4), "r2_all": round(r2_all, 4),
           "median_abs_pct_err_heldout": round(mape_h, 1), "heldout_fraction": 0.2, "per_kind_heldout": per_kind,
           "mix": {k: kinds.count(k) for k in sorted(set(kinds))}, "gates_range": [int(y.min()), int(y.max())],
           "flow": f"yosys {version()} simple gates, ABC effort fast", "date": time.strftime("%Y-%m-%d"),
           "basis": (f"estimate (shipped fit on {len(rows)} synthesised designs, held-out r²={r2_h:.2f}, "
                     f"median error {mape_h:.0f}% on a 20% held-out split)")}
    a.out.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({k: out[k] for k in ("n", "coef", "r2_train", "r2_heldout", "median_abs_pct_err_heldout", "mix", "per_kind_heldout")}, indent=1))
    print(f"wrote {a.out} in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
