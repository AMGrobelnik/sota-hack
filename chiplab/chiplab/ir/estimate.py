"""Fast pre-synthesis gate estimate from chipir/1, always labelled as an estimate.

Features (in full-adder / comparator / mux bit units) are counted from the IR with derived widths; gates =
features . coefficients. Coefficients are refit by least squares from the lab's own synthesis results
(`refit(...)`, stored in CHIPLAB_HOME/estimator.json); defaults come from a small calibration set.
"""
from __future__ import annotations

import json

import numpy as np

from chiplab import config
from chiplab.ir.ranges import csd, ranges as ir_ranges, width

FEATURES = ("adder_bits", "cmp_bits", "mux_bits", "lut_entries")
DEFAULT = {"coef": [4.2, 2.0, 1.0, 0.6], "basis": "estimate (default coefficients, not yet refit)", "n": 0, "r2": None}


def features(ir: dict) -> dict:
    R = ir_ranges(ir)
    W = {k: [width(l, h)[0] for l, h in v] for k, v in R.items()}
    f = dict.fromkeys(FEATURES, 0)
    for nd in ir.get("nodes", []):
        op, i = nd["op"], nd["id"]
        if op == "matvec":
            for j, row in enumerate(nd["W"]):
                digits = sum(len(csd(abs(w))) for w in row if w)
                f["adder_bits"] += max(0, digits - 1 + (1 if (nd.get("b") or [0] * len(nd["W"]))[j] else 0)) * W[i][j]
        elif op in ("add", "sub"):
            f["adder_bits"] += sum(W[i])
        elif op == "clip":
            f["cmp_bits"] += 2 * sum(W[nd["src"]]); f["mux_bits"] += sum(W[i])
        elif op == "abs":
            f["adder_bits"] += sum(W[i]); f["mux_bits"] += sum(W[i])
        elif op == "max":
            for g in nd["groups"]:
                f["cmp_bits"] += (len(g) - 1) * max(W[nd["src"]][k] for k in g)
                f["mux_bits"] += (len(g) - 1) * max(W[nd["src"]][k] for k in g)
        elif op == "cmp":
            f["cmp_bits"] += sum(W[nd["src"]])
        elif op == "lut":
            f["lut_entries"] += sum(len(t) for t in nd["tables"])
        elif op == "argmax":
            n = len(W[nd["src"]]); f["cmp_bits"] += (n - 1) * max(W[nd["src"]]); f["mux_bits"] += (n - 1) * (max(W[nd["src"]]) + W[i][0])
    return f


def _coef() -> dict:
    p = config.HOME / "estimator.json"
    return json.loads(p.read_text()) if p.exists() else DEFAULT


def estimate(ir: dict) -> dict:
    f = features(ir)
    c = _coef()
    g = float(np.dot(c["coef"], [f[k] for k in FEATURES]))
    return {"gates_est": int(round(max(g, 1))), **f, "basis": c["basis"], "fit_n": c.get("n"), "fit_r2": c.get("r2")}


def refit(pairs: list[tuple[dict, int]]) -> dict:
    """pairs: (ir, synthesised gate count). Non-negative least squares on the features; saves estimator.json."""
    from scipy.optimize import nnls
    X = np.array([[features(ir)[k] for k in FEATURES] for ir, _ in pairs], float)
    y = np.array([g for _, g in pairs], float)
    coef, _ = nnls(X, y)
    pred = X @ coef
    r2 = 1 - ((y - pred) ** 2).sum() / max(((y - y.mean()) ** 2).sum(), 1e-9)
    out = {"coef": coef.round(4).tolist(), "basis": f"estimate (refit on {len(y)} synthesised designs, r2={r2:.3f})",
           "n": len(y), "r2": round(float(r2), 4)}
    (config.home() / "estimator.json").write_text(json.dumps(out))
    return out
