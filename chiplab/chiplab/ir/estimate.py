"""Fast pre-synthesis gate estimate from chipir/1, always labelled as an estimate.

Features (full-adder / comparator / mux bit units at derived widths, over the live cone of the outputs only) are
counted from the IR; gates = features . coefficients. Coefficients, in order of precedence:
  1. CHIPLAB_HOME/estimator.json: a local refit (`refit(...)`) on this lab's own synthesis results;
  2. chiplab/ir/estimator_default.json: the fit shipped with the package (scripts/refit_estimator.py);
  3. DEFAULT below: built-in, unfitted.
The returned basis says which one was used and how well it fitted. A fit may carry per-family coefficients
("families": {family: {features, coef}}) and held-out errors per family; estimate() names the design's family
(intnn, composed, torchlogix, treelut, alkaid) and adds a one-line error note for it. The streaming wrapper's
flip-flops and sky130 area are separate fields (wrapper_ffs, wrapper_area_um2), never part of gates_est.
"""
from __future__ import annotations

import json

import numpy as np

from chiplab import config
from chiplab.ir.ranges import csd, ranges as ir_ranges, width

FEATURES = ("adder_bits", "cmp_bits", "mux_bits", "lut_entries", "const")
LEGACY_FEATURES = ("adder_bits", "cmp_bits", "mux_bits", "lut_entries")      # local refits made before "const"
# Finer features (added on top of FEATURES, whose values are unchanged): adder_bits split into multi-bit adders
# (wide_adder_bits) and sums of 1-bit terms such as popcounts and tree-leaf sums (sum1_bits: one full adder per
# 1-bit operand of a carry-save tree); for multi-bit matvec rows, the operand bits that enter the adder tree
# (term_bits) and the sign-extension bits of signed operands (signext_bits), which track large sums better than
# terms x output width; lut_gates, the two-input gates a LUT lane needs (lut_entries counts table rows, which
# grows as 2^k for TreeLUT leaves while the leaf itself is a k-input AND).
EXTRA_FEATURES = ("wide_adder_bits", "term_bits", "signext_bits", "sum1_bits", "lut_gates")
FIT_FEATURES = ("wide_adder_bits", "term_bits", "signext_bits", "sum1_bits", "cmp_bits", "mux_bits", "lut_gates", "const")
DEFAULT = {"coef": [2.2, 0.5, 0.5, 0.3, 0.0], "features": list(FEATURES),
           "basis": "estimate (built-in coefficients, not fitted)", "n": 0, "r2": None}
FAMILIES = ("intnn", "composed", "torchlogix", "treelut", "alkaid")
OPTIMIZED = ("alkaid",)


def family(ir: dict, optimizer: str | None = None) -> str:
    """Design family for the estimator's per-family error notes: alkaid (optimised emitter), torchlogix, treelut,
    composed (multi-head, with or without fusion), else intnn (integer networks and raw chipir)."""
    if optimizer and optimizer.lower()[:3] in {o[:3] for o in OPTIMIZED}:
        return "alkaid"
    fmt = (ir.get("meta") or {}).get("format")
    return fmt if fmt in ("torchlogix", "treelut", "composed") else "intnn"


def _lut_gates(table: list[int], k: int) -> int:
    """Two-input gates for one LUT lane: inputs the table ignores are dropped; 0 or 1 live input is a wire or an
    inverter; 2 live inputs is one gate (every 2-input function is one cell of the simple-gate library); more is a
    sum of products over the smaller of the on-set and off-set (a TreeLUT leaf, one minterm, is k-1 gates)."""
    live = [b for b in range(k) if any(table[v] != table[v ^ (1 << b)] for v in range(len(table)))]
    if len(live) <= 1:
        return 0
    if len(live) == 2:
        return 1
    seen = {}
    for v, t in enumerate(table):                       # project onto the live inputs
        seen[sum(((v >> b) & 1) << m for m, b in enumerate(live))] = t
    ones = sum(seen.values()); m = min(ones, len(seen) - ones)
    return m * (len(live) - 1) + max(0, m - 1)


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
    f = dict.fromkeys(FEATURES + EXTRA_FEATURES, 0)
    f["const"] = 1
    for nd in ir.get("nodes", []):
        op, i = nd["op"], nd["id"]
        lv = sorted(j for j in live[i] if R[i][j][0] != R[i][j][1])     # constant lanes cost nothing
        if not lv:
            continue
        if op == "matvec":
            b = nd.get("b") or [0] * len(nd["W"])
            src_w, src_s = W[nd["src"]], [width(l, h)[1] for l, h in R[nd["src"]]]
            onebit = all(src_w[k] <= 1 for k in range(len(src_w)))
            for j in lv:
                terms = [(k, p) for k, w in enumerate(nd["W"][j]) if w for _, p in csd(abs(w))]
                digits = len(terms)
                bits = max(0, digits - 1 + (1 if b[j] else 0)) * W[i][j]
                f["adder_bits"] += bits
                if onebit:
                    f["sum1_bits"] += digits
                    continue
                f["wide_adder_bits"] += bits
                if digits >= 2:            # operand bits into the adder tree, and the sign-extension bits of signed ones
                    f["term_bits"] += sum(src_w[k] + p for k, p in terms)
                    f["signext_bits"] += sum(max(0, W[i][j] - src_w[k] - p) for k, p in terms if src_s[k])
        elif op in ("add", "sub"):
            f["adder_bits"] += sum(W[i][j] for j in lv); f["wide_adder_bits"] += sum(W[i][j] for j in lv)
        elif op == "clip":
            f["cmp_bits"] += 2 * sum(W[nd["src"]][j] for j in lv); f["mux_bits"] += sum(W[i][j] for j in lv)
        elif op == "abs":
            f["adder_bits"] += sum(W[i][j] for j in lv); f["wide_adder_bits"] += sum(W[i][j] for j in lv)
            f["mux_bits"] += sum(W[i][j] for j in lv)
        elif op == "max":
            for j in lv:
                g = nd["groups"][j]
                f["cmp_bits"] += (len(g) - 1) * max(W[nd["src"]][k] for k in g)
                f["mux_bits"] += (len(g) - 1) * max(W[nd["src"]][k] for k in g)
        elif op == "cmp":
            f["cmp_bits"] += sum(W[nd["src"]][j] for j in lv)
        elif op == "lut":
            f["lut_entries"] += sum(len(nd["tables"][j]) for j in lv)
            f["lut_gates"] += sum(_lut_gates(nd["tables"][j], len(nd["inputs"][j])) for j in lv)
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


def stream_wrapper_ffs(ir: dict, tt: bool = True) -> int:
    """Flip-flops the streaming wrapper (emit/stream.py) keeps after synthesis: the input shift register bits that
    reach a live core input (a bit stays if it, or the same bit of a later-shifted word, is used), the word
    counter, the strobe synchroniser and edge detect (3), done and valid (2) and the output register."""
    from chiplab.emit.stream import WORD, _clog2
    live = live_lanes(ir)
    first: dict[int, int] = {}                       # bit position -> first word index that uses it
    t = 0
    for p in ir["inputs"]:
        n = -(-p["bits"] // WORD)
        for lane in range(p["lanes"]):
            for c in range(n):
                if lane in live.get(p["name"], ()):
                    for b in range(min(WORD, p["bits"] - c * WORD)):
                        first.setdefault(b, t)
                t += 1
    sreg = sum(t - f0 for f0 in first.values())
    R = ir_ranges(ir)
    ob = 0
    for o in ir["outputs"]:
        rr = R[o["src"]]
        signed = any(lo < 0 for lo, _ in rr)
        ob += len(rr) * max(width(lo, hi)[0] + (1 if signed and not width(lo, hi)[1] else 0) for lo, hi in rr)
    return sreg + (_clog2(t) if t > 1 else 0) + 5 + (min(ob, 7) if tt else ob)


def stream_wrapper(ir: dict, coef: dict | None = None, tt: bool = True) -> dict:
    """wrapper_ffs (structural count) and wrapper_area_um2 (sky130 synthesis area, estimate from the shipped
    per-flip-flop fit; None when the fit has no wrapper calibration). The core's gate estimate excludes both."""
    ffs = stream_wrapper_ffs(ir, tt=tt)
    w = (coef or _coef()).get("wrapper") or {}
    area = round(w["area_um2_per_ff"] * ffs + w.get("area_um2_const", 0.0), 1) if "area_um2_per_ff" in w else None
    return {"wrapper_ffs": ffs, "wrapper_area_um2": area}


def error_note(c: dict, fam: str) -> str:
    """One line on how far to trust an estimate for this design family, from the fit's held-out errors."""
    h = (c.get("per_family_heldout") or {}).get(fam)
    if not h:
        return (f"{fam}: no held-out calibration data for this family in the {c.get('source', 'fit')}; treat the "
                f"estimate as rough and synthesise before deciding")
    r2 = f", r2 {h['r2']:.2f}" if h.get("r2") is not None else ""
    p90 = f", 90th percentile {h['p90_abs_pct_err']:.0f}%" if h.get("p90_abs_pct_err") is not None else ""
    return f"{fam}: median error {h['median_abs_pct_err']:.0f}%{p90} on {h['n_heldout']} held-out designs{r2}"


def estimate(ir: dict, optimizer: str | None = None) -> dict:
    f = features(ir)
    c = _coef()
    fam = family(ir, optimizer)
    fc = (c.get("families") or {}).get(fam) or c
    g = float(np.dot(fc["coef"], [f[k] for k in fc["features"]]))
    out = {"gates_est": int(round(max(g, 1))), **f, "basis": c["basis"], "fit_source": c["source"], "fit_n": c.get("n"),
           "fit_r2": c.get("r2_heldout", c.get("r2")), "family": fam, "est_error_note": error_note(c, fam)}
    try:
        out.update(stream_wrapper(ir, c))
    except (KeyError, ValueError, TypeError):           # a document the wrapper cannot stream: leave the fields out
        pass
    return out


def refit(pairs: list[tuple[dict, int]]) -> dict:
    """pairs: (ir, synthesised gate count). Non-negative least squares on the features; saves a local override
    (CHIPLAB_HOME/estimator.json) that takes precedence over the shipped fit."""
    from scipy.optimize import nnls
    X = np.array([[features(ir)[k] for k in FIT_FEATURES] for ir, _ in pairs], float)
    y = np.array([g for _, g in pairs], float)
    coef, _ = nnls(X, y)
    pred = X @ coef
    r2 = 1 - ((y - pred) ** 2).sum() / max(((y - y.mean()) ** 2).sum(), 1e-9)
    out = {"features": list(FIT_FEATURES), "coef": coef.round(4).tolist(),
           "basis": f"estimate (local refit on {len(y)} synthesised designs, in-sample r2={r2:.3f})",
           "n": len(y), "r2": round(float(r2), 4)}
    (config.home() / "estimator.json").write_text(json.dumps(out))
    return out
