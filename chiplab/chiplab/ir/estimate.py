"""Fast pre-synthesis gate estimate from chipir/1, always labelled as an estimate.

Features (full-adder / comparator / mux bit units at derived widths, over the live cone of the outputs only) are
counted from the IR; gates = features . coefficients. Coefficients, in order of precedence:
  1. CHIPLAB_HOME/estimator.json: a local refit (`refit(...)`) on this lab's own synthesis results;
  2. chiplab/ir/estimator_default.json: the fit shipped with the package (scripts/refit_estimator.py);
  3. DEFAULT below: built-in, unfitted.
The returned basis says which one was used and how well it fitted.
"""
from __future__ import annotations

import json

import numpy as np

from chiplab import config
from chiplab.ir.ranges import csd, ranges as ir_ranges, width

FEATURES = ("adder_bits", "cmp_bits", "mux_bits", "lut_entries", "const")
LEGACY_FEATURES = ("adder_bits", "cmp_bits", "mux_bits", "lut_entries")      # local refits made before "const"
DEFAULT = {"coef": [2.2, 0.5, 0.5, 0.3, 0.0], "features": list(FEATURES),
           "basis": "estimate (built-in coefficients, not fitted)", "n": 0, "r2": None}


def live_lanes(ir: dict) -> dict[str, set[int]]:
    """Lanes each node must compute for the outputs (backward cone). Synthesis deletes everything else, e.g. a
    hidden unit whose output weight is zero, or a node no output uses, so the estimate must not count it."""
    from chiplab.ir.schema import lanes_of
    n = lanes_of(ir)
    live: dict[str, set[int]] = {k: set() for k in n}
    for o in ir["outputs"]:
        live[o["src"]] |= set(range(n[o["src"]]))
    for nd in reversed(ir.get("nodes", [])):
        i, op, need = nd["id"], nd["op"], live[nd["id"]]
        if not need:
            continue
        def use(src, j):
            live[src].add(j if n[src] > 1 else 0)
        if op == "matvec":
            for j in need:
                for k, w in enumerate(nd["W"][j]):
                    if w:
                        live[nd["src"]].add(k)
        elif op in ("add", "sub"):
            for j in need:
                use(nd["a"], j); use(nd["b"], j)
        elif op in ("shift", "clip", "abs"):
            for j in need:
                live[nd["src"]].add(j)
        elif op == "cmp":
            for j in need:
                live[nd["src"]].add(j)
                if "other" in nd:
                    use(nd["other"], j)
        elif op == "max":
            for j in need:
                live[nd["src"]] |= set(nd["groups"][j])
        elif op == "gather":
            for j in need:
                live[nd["src"]].add(nd["idx"][j])
        elif op == "concat":
            flat = [(s_, k) for s_ in nd["srcs"] for k in range(n[s_])]
            for j in need:
                live[flat[j][0]].add(flat[j][1])
        elif op == "lut":
            for j in need:
                live[nd["src"]] |= set(nd["inputs"][j])
        elif op == "argmax":
            live[nd["src"]] |= set(range(n[nd["src"]]))
    return live


def features(ir: dict) -> dict:
    """Cost features over the live cone only, in full-adder / comparator / mux bit units at derived widths."""
    R = ir_ranges(ir)
    W = {k: [width(l, h)[0] for l, h in v] for k, v in R.items()}
    live = live_lanes(ir)
    f = dict.fromkeys(FEATURES, 0)
    f["const"] = 1
    for nd in ir.get("nodes", []):
        op, i = nd["op"], nd["id"]
        lv = sorted(j for j in live[i] if R[i][j][0] != R[i][j][1])     # constant lanes cost nothing
        if not lv:
            continue
        if op == "matvec":
            b = nd.get("b") or [0] * len(nd["W"])
            for j in lv:
                digits = sum(len(csd(abs(w))) for w in nd["W"][j] if w)
                f["adder_bits"] += max(0, digits - 1 + (1 if b[j] else 0)) * W[i][j]
        elif op in ("add", "sub"):
            f["adder_bits"] += sum(W[i][j] for j in lv)
        elif op == "clip":
            f["cmp_bits"] += 2 * sum(W[nd["src"]][j] for j in lv); f["mux_bits"] += sum(W[i][j] for j in lv)
        elif op == "abs":
            f["adder_bits"] += sum(W[i][j] for j in lv); f["mux_bits"] += sum(W[i][j] for j in lv)
        elif op == "max":
            for j in lv:
                g = nd["groups"][j]
                f["cmp_bits"] += (len(g) - 1) * max(W[nd["src"]][k] for k in g)
                f["mux_bits"] += (len(g) - 1) * max(W[nd["src"]][k] for k in g)
        elif op == "cmp":
            f["cmp_bits"] += sum(W[nd["src"]][j] for j in lv)
        elif op == "lut":
            f["lut_entries"] += sum(len(nd["tables"][j]) for j in lv)
        elif op == "argmax":
            n = len(W[nd["src"]]); f["cmp_bits"] += (n - 1) * max(W[nd["src"]]); f["mux_bits"] += (n - 1) * (max(W[nd["src"]]) + W[i][0])
    return f


PACKAGED = config.PKG_DIR / "ir" / "estimator_default.json"


def _coef() -> dict:
    for p in (config.HOME / "estimator.json", PACKAGED):
        if p.exists():
            try:
                c = json.loads(p.read_text())
                c.setdefault("features", list(LEGACY_FEATURES))
                c.setdefault("source", "local refit" if p != PACKAGED else "shipped fit")
                return c
            except Exception:
                continue
    return {**DEFAULT, "source": "built-in"}


def estimate(ir: dict) -> dict:
    f = features(ir)
    c = _coef()
    g = float(np.dot(c["coef"], [f[k] for k in c["features"]]))
    return {"gates_est": int(round(max(g, 1))), **f, "basis": c["basis"], "fit_source": c["source"], "fit_n": c.get("n"),
            "fit_r2": c.get("r2_heldout", c.get("r2"))}


def refit(pairs: list[tuple[dict, int]]) -> dict:
    """pairs: (ir, synthesised gate count). Non-negative least squares on the features; saves a local override
    (CHIPLAB_HOME/estimator.json) that takes precedence over the shipped fit."""
    from scipy.optimize import nnls
    X = np.array([[features(ir)[k] for k in FEATURES] for ir, _ in pairs], float)
    y = np.array([g for _, g in pairs], float)
    coef, _ = nnls(X, y)
    pred = X @ coef
    r2 = 1 - ((y - pred) ** 2).sum() / max(((y - y.mean()) ** 2).sum(), 1e-9)
    out = {"features": list(FEATURES), "coef": coef.round(4).tolist(),
           "basis": f"estimate (local refit on {len(y)} synthesised designs, in-sample r2={r2:.3f})",
           "n": len(y), "r2": round(float(r2), 4)}
    (config.home() / "estimator.json").write_text(json.dumps(out))
    return out
