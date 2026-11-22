"""Opt-in optimised emission: constant matrix-vector products implemented by alkaid's common-subexpression
shift-add networks (CMVM). Same top name, ports and packing as emit.verilog.emit, so every hardware and
verification tool works unchanged; the default emitter is untouched.

Per matvec node: rows with any non-zero weight go to alkaid (bias included in its trace), constant rows stay in
our logic; alkaid's output word is decoded from its own format (sign bit k, integer bits i, fraction bits f, with
f <= 0 meaning implied trailing zeros) and extended/truncated to the node's derived width. Anything alkaid can't
express (fractional outputs, negated outputs, input widths that don't match) falls back to the standard code for
that node, recorded in port_info["optimizer"]["nodes"].

Licence: alkaid is LGPL-3.0 and used as a pip dependency. Designs emitted this way embed alkaid's small Verilog
helper modules (shift_adder, ternary_adder, ...), copied from the installed package at generation time.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np

from chiplab.emit.verilog import _Lane, _ext, _lit, emit
from chiplab.ir.schema import top_name

STATIC = ("binop", "multiplier", "mux", "negative", "shift_adder", "ternary_adder")
PREFIX = "chipin_alk_"


def available() -> bool:
    try:
        import alkaid  # noqa: F401
        return True
    except Exception:
        return False


def _static_sources() -> dict[str, str]:
    import alkaid
    d = Path(alkaid.__file__).parent / "codegen" / "rtl" / "verilog" / "source"
    return {n: (d / f"{n}.v").read_text() for n in STATIC if (d / f"{n}.v").exists()}


def _clean(text: str) -> str:
    """Drop `timescale (our design has none) and prefix alkaid's helper module names to avoid clashes."""
    text = re.sub(r"^\s*`timescale.*$", "", text, flags=re.M)
    for n in STATIC:
        text = re.sub(rf"\b{n}\b", PREFIX + n, text)
    return text


def _trace(W: np.ndarray, b: np.ndarray, lanes: list[tuple[int, bool]]):
    from alkaid.trace import FVArrayInput, trace
    from alkaid.trace.passes import add_surrogate, dead_code_elimin, fuse_ternary_adders
    k = np.array([1 if s else 0 for _, s in lanes])
    i = np.array([w - 1 if s else w for w, s in lanes])
    x = FVArrayInput((len(lanes),))
    xq = x.quantize(k=k, i=i, f=0)
    comb = trace(x, xq @ W.T + b)
    return add_surrogate(dead_code_elimin(fuse_ternary_adders(comb)), _skip_op8_cost=True)


def _make_impl(top: str, report: list, modules: list):
    from alkaid.codegen.rtl.verilog.comb import comb_logic_gen

    def impl(nd: dict, L: dict, ws: list, R: dict):
        if nd["op"] != "matvec":
            return None
        nid, src = nd["id"], L[nd["src"]]
        W = np.asarray(nd["W"], dtype=np.int64)
        b = np.asarray(nd.get("b") or [0] * len(W), dtype=np.int64)
        rows = [j for j in range(len(W)) if (W[j] != 0).any()]
        why = None
        if not rows:
            why = "all rows constant"
        else:
            try:
                comb = _trace(W[rows], b[rows], [(x.w, x.s) for x in src])
            except Exception as e:  # pragma: no cover - alkaid limitation
                comb, why = None, f"alkaid trace failed: {type(e).__name__}: {e}"
        if why is None:
            ok_kifs = np.asarray(comb.out_kifs)
            in_kifs = np.asarray(comb.inp_kifs)
            out_w = ok_kifs.sum(axis=0).astype(int).tolist()
            in_w = in_kifs.sum(axis=0).astype(int).tolist()
            if getattr(comb, "lookup_tables", None):
                why = "alkaid chose lookup tables (not emitted standalone)"
            elif any(comb.out_negs):
                why = "negated outputs"
            elif any(int(ix) < 0 for ix in comb.out_idxs) or any(w <= 0 for w in out_w):
                why = "degenerate output"
            elif any(int(f) > 0 for f in ok_kifs[2]):
                why = "fractional output"
            elif any(w > 0 and (w != x.w or int(in_kifs[2][j]) != 0) for j, (w, x) in enumerate(zip(in_w, src))):
                why = "input width mismatch"
        if why is not None:
            report.append({"node": nid, "impl": "standard", "reason": why})
            return None
        mod = f"{top}_mv_{nid}"
        text = comb_logic_gen(comb, mod)
        if re.search(r"\btable_[0-9a-f_]+\b", text):  # safety net: any table module reference -> standard code
            report.append({"node": nid, "impl": "standard", "reason": "alkaid emitted a lookup table"})
            return None
        modules.append(text)
        win, wout = f"mvi_{nid}", f"mvo_{nid}"
        used = [j for j, w in enumerate(in_w) if w > 0]
        lines = [f"  // matvec {nid}: alkaid CSE shift-add network ({len(rows)} of {len(W)} rows)"]
        lines.append(f"  wire [{sum(in_w) - 1}:0] {win} = {{{', '.join(src[j].ref for j in reversed(used))}}};")
        lines.append(f"  wire [{sum(out_w) - 1}:0] {wout};")
        lines.append(f"  {mod} u_{mod} (.model_inp({win}), .model_out({wout}));")
        lanes, off = [], 0
        for j in range(len(W)):
            ref = f"n_{nid}_{j}"
            w, s = ws[j]
            if j in rows:
                o = rows.index(j)
                bw, k, f = out_w[o], int(ok_kifs[0][o]), int(ok_kifs[2][o])
                tn = f"mvs_{nid}_{j}"
                lines.append(f"  wire [{bw - 1}:0] {tn} = {wout}[{off + bw - 1}:{off}];" if bw > 1 else
                             f"  wire [0:0] {tn} = {wout}[{off}];")
                off += bw
                lane = _Lane(tn, bw, k == 1)
                if f < 0:  # implied trailing zeros: value = stored << -f
                    tz = f"mvz_{nid}_{j}"
                    lines.append(f"  wire [{bw - f - 1}:0] {tz} = {{{tn}, {-f}'b0}};")
                    lane = _Lane(tz, bw - f, k == 1)
                lines.append(f"  wire [{w - 1}:0] {ref} = {_ext(lane, w)};")
            else:
                lines.append(f"  wire [{w - 1}:0] {ref} = {_lit(int(b[j]), w)};")
            lanes.append((ref, w, s))
        report.append({"node": nid, "impl": "alkaid", "rows": len(rows), "constant_rows": len(W) - len(rows),
                       "alkaid_cost": float(getattr(comb, "cost", 0.0))})
        return lines, lanes

    return impl


def emit_optimized(ir: dict, optimizer: str = "alkaid", top: str | None = None) -> tuple[str, dict]:
    """Verilog with the same top/ports as emit(ir), constant matvecs implemented by `optimizer` (only 'alkaid')."""
    if optimizer in (None, "", "none", "default"):
        return emit(ir, top)
    if optimizer != "alkaid":
        raise ValueError("optimizer must be 'alkaid' (or none)")
    if not available():
        raise RuntimeError("alkaid is not installed: uv sync --extra ingest")
    top = top or top_name(ir)
    report, modules = [], []
    text, info = emit(ir, top, node_impl=_make_impl(top, report, modules))
    if modules:
        body = "\n".join(_clean(m) for m in modules)
        used = [n for n in STATIC if re.search(rf"\b{PREFIX}{n}\b", body)]
        statics = _static_sources()
        text = (f"// optimizer: alkaid CSE for constant matvecs; the modules after `{top}` come from alkaid (LGPL-3.0)\n"
                + text + "\n" + body + "\n" + "\n".join(_clean(statics[n]) for n in used) + "\n")
    import alkaid
    info["optimizer"] = {"name": "alkaid", "version": getattr(alkaid, "__version__", "?"), "nodes": report}
    return text, info
