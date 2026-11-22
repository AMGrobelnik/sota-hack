"""Opt-in optimised emission: constant matrix-vector products implemented as common-subexpression shift-add
networks solved by alkaid's CMVM solver. Same top name, ports and packing as emit.verilog.emit, so every hardware and
verification tool works unchanged; the default emitter is untouched.

Per matvec node: rows with any non-zero weight go to alkaid (bias included in its trace), constant rows stay in
our logic. alkaid only solves the adder graph; the Verilog for that graph is written here (`graph_rtl`), one plain
`assign` per graph node, so the output word is decoded from the graph's own format (sign bit k, integer bits i,
fraction bits f, with f <= 0 meaning implied trailing zeros) and extended/truncated to the node's derived width.
Anything the graph can't express here (lookup tables, fractional or negated outputs, input widths that don't match,
operations other than shifted sums) falls back to the standard code for that node, recorded in
port_info["optimizer"]["nodes"].

Licence: alkaid (LGPL-3.0) is an optional pip dependency, called as a separate package. No alkaid source or Verilog
template is copied into the generated RTL: it contains only chiplab-written code.

Process isolation: alkaid's native CMVM solver and PyTorch each bring an OpenMP runtime, and on macOS a process that
loads both can abort. So alkaid never runs in the caller's process: emit_optimized runs it in a fresh worker
(`python -m chiplab.emit.alkaid_worker`), like the XGBoost converter. CHIPLAB_ALKAID_INPROCESS=1 runs it in-process.
The worker keeps a timeout: the solver can hang on some constants (alkaid issue 8).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import numpy as np

from chiplab.emit.verilog import _Lane, _ext, _lit, emit
from chiplab.ir.schema import top_name

# binary_lut=False: no lookup tables for 1-bit inputs (an ASIC build wants adders; tables fell back to standard code)
SOLVER_OPTIONS = {"binary_lut": False}


class Unsupported(Exception):
    """The adder graph uses something graph_rtl does not write; the node falls back to standard code."""


def available() -> bool:
    """alkaid is installed (checked without importing it: its native code stays out of this process)."""
    import importlib.util
    try:
        return importlib.util.find_spec("alkaid") is not None
    except (ImportError, ValueError):
        return False


def _trace(W: np.ndarray, b: np.ndarray, lanes: list[tuple[int, bool]]):
    from alkaid.trace import FVArrayInput, trace
    from alkaid.trace.passes import add_surrogate, dead_code_elimin, fuse_ternary_adders
    k = np.array([1 if s else 0 for _, s in lanes])
    i = np.array([w - 1 if s else w for w, s in lanes])
    x = FVArrayInput((len(lanes),), solver_options=dict(SOLVER_OPTIONS))
    xq = x.quantize(k=k, i=i, f=0)
    comb = trace(x, xq @ W.T + b)
    return add_surrogate(dead_code_elimin(fuse_ternary_adders(comb)), _skip_op8_cost=True)


def _terms(op) -> tuple[list[tuple[int, int, int]], tuple[int, int] | None]:
    """A graph node as a shifted sum: ([(source, +1|-1, shift)], (constant, constant fraction bits) or None).
    value = sum(sign * source * 2**shift) + constant * 2**-fraction."""
    c, a, d = op.opcode, list(op.addr), list(op.data)
    if c in (0, 1):                      # a +/- (b << shift)
        return [(a[0], 1, 0), (a[1], 1 if c == 0 else -1, int(d[0]))], None
    if c == 11:                          # signed shifted sum of several sources
        return [(a[j], 1 if d[2 * j] else -1, int(d[2 * j + 1])) for j in range(len(a))], None
    if c == -2:                          # negation
        return [(a[0], -1, 0)], None
    if c == 3:                           # requantised copy (floor, wrap): source << shift
        return [(a[0], 1, int(d[0]))], None
    if c == 4:                           # source + constant
        return [(a[0], 1, 0)], (int(d[0]), int(d[1]))
    raise Unsupported(f"graph operation {c}")


def graph_rtl(comb, mod: str) -> str:
    """Verilog-2005 for a solved adder graph: `module <mod> (model_inp, model_out)`, inputs and outputs packed lane
    by lane, lane 0 in the low bits. Every value is an integer n at its own fraction bits f (value = n * 2**-f);
    a node's value is the shifted sum of its sources, floored to its fraction bits and wrapped to its width (only the
    bits that reach the result are added: modular arithmetic)."""
    ops = comb.ops
    kif = [tuple(int(x) for x in op.qint.kif) for op in ops]
    width = [sum(k) for k in kif]
    used = [False] * len(ops)
    for o in comb.out_idxs:
        if int(o) >= 0:
            used[int(o)] = True
    for j in range(len(ops) - 1, -1, -1):          # sources come before their users
        if used[j] and ops[j].opcode not in (-1, 5):
            for s in (_terms(ops[j])[0]):
                used[s[0]] = True
    in_w = [int(w) for w in np.asarray(comb.inp_kifs).sum(axis=0)]
    in_off = np.concatenate([[0], np.cumsum(in_w)]).astype(int).tolist()
    out_w = [int(w) for w in np.atleast_1d(np.asarray(comb.out_kifs).sum(axis=0))]
    lines = []

    def fit(j: int, n: int) -> str:                 # the low n bits of source j, sign- or zero-extended
        w = width[j]
        if n <= w:
            return f"v{j}" if n == w else (f"v{j}[{n - 1}:0]" if n > 1 else f"v{j}[0]")
        fill = f"v{j}[{w - 1}]" if kif[j][0] else "1'b0"
        return f"{{{{{n - w}{{{fill}}}}}, v{j}}}"

    for i, op in enumerate(ops):
        bw = width[i]
        if not used[i] or bw <= 0:
            continue
        lines.append(f"  wire [{bw - 1}:0] v{i};")
        if op.opcode == -1:                         # input lane
            lane = int(op.data[0])
            if in_w[lane] != bw:
                raise Unsupported("input lane width differs from its graph node")
            lines.append(f"  assign v{i} = model_inp[{in_off[lane] + bw - 1}:{in_off[lane]}];")
            continue
        if op.opcode == 5:                          # constant at the node's own fraction bits
            lines.append(f"  assign v{i} = {bw}'d{int(op.data[0]) % (1 << bw)};")
            continue
        terms, const = _terms(op)
        terms = [(s, g, sh) for s, g, sh in terms if width[s] > 0]
        lsb = max([kif[s][2] - sh for s, _, sh in terms] + ([const[1]] if const else []) + [kif[i][2]])
        drop = lsb - kif[i][2]                      # low bits floored away (>= 0)
        ww = drop + bw                              # the kept bits depend only on the operands' low ww bits
        parts = []                                  # (sign, operand at the common lsb, ww bits)
        for s, g, sh in terms:
            e = lsb - kif[s][2] + sh
            if e < ww:
                parts.append((g, f"{{{fit(s, ww - e)}, {e}'b0}}" if e else fit(s, ww)))
        cval = (const[0] << (lsb - const[1])) % (1 << ww) if const else 0
        if cval:
            parts.append((1, f"{ww}'d{cval}"))
        parts.sort(key=lambda p: p[0] < 0)          # a positive term first: no subtraction from zero
        body = f"{ww}'d0"
        for n, (g, t) in enumerate(parts):
            body = t if n == 0 and g > 0 else f"{body} {'+' if g > 0 else '-'} {t}"
        lines.append(f"  wire [{ww - 1}:0] s{i} = {body};")
        lines.append(f"  assign v{i} = s{i}[{drop + bw - 1}:{drop}];")
    off = 0
    for o, idx in enumerate(comb.out_idxs):
        w, idx = out_w[o], int(idx)
        if w > 0:
            if idx < 0 or width[idx] != w:
                raise Unsupported("output width differs from its graph node")
            lines.append(f"  assign model_out[{off + w - 1}:{off}] = v{idx};")
        off += w
    head = ["// constant matvec as a shared shift-add graph (graph solved by alkaid's CMVM, Verilog by chiplab)",
            f"module {mod} (", f"  input wire [{sum(in_w) - 1}:0] model_inp,", f"  output wire [{off - 1}:0] model_out", ");"]
    return "\n".join(head + lines + ["endmodule", ""])


def _make_impl(top: str, report: list, modules: list):

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
        mod = f"{top}_mv_{nid}"
        if why is None:
            try:
                text = graph_rtl(comb, mod)
            except Unsupported as e:
                why = str(e)
        if why is not None:
            report.append({"node": nid, "impl": "standard", "reason": why})
            return None
        modules.append(text)
        win, wout = f"mvi_{nid}", f"mvo_{nid}"
        used = [j for j, w in enumerate(in_w) if w > 0]
        lines = [f"  // matvec {nid}: shared shift-add network ({len(rows)} of {len(W)} rows)"]
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


def emit_optimized(ir: dict, optimizer: str = "alkaid", top: str | None = None, timeout: int = 900) -> tuple[str, dict]:
    """Verilog with the same top/ports as emit(ir), constant matvecs implemented by `optimizer` (only 'alkaid').
    alkaid runs in a separate worker process (see the module docstring)."""
    if optimizer in (None, "", "none", "default"):
        return emit(ir, top)
    if optimizer != "alkaid":
        raise ValueError("optimizer must be 'alkaid' (or none)")
    if not available():
        raise RuntimeError("alkaid is not installed: uv sync --extra ingest")
    if os.environ.get("CHIPLAB_ALKAID_INPROCESS") == "1":
        return emit_optimized_local(ir, optimizer, top)
    p = subprocess.run([sys.executable, "-m", "chiplab.emit.alkaid_worker"], input=json.dumps({"ir": ir, "top": top}),
                       capture_output=True, text=True, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError(f"alkaid worker failed (rc {p.returncode}): {(p.stderr or p.stdout)[-600:]}")
    out = json.loads(p.stdout)
    return out["text"], out["info"]


def emit_optimized_local(ir: dict, optimizer: str = "alkaid", top: str | None = None) -> tuple[str, dict]:
    """emit_optimized in this process (the worker's body). Don't call it where PyTorch may be loaded."""
    top = top or top_name(ir)
    report, modules = [], []
    text, info = emit(ir, top, node_impl=_make_impl(top, report, modules))
    if modules:
        text = ("// optimizer: constant matvecs as shared shift-add graphs (solved by alkaid's CMVM); all Verilog "
                "here is written by chiplab\n" + text + "\n" + "\n".join(modules))
    import alkaid
    info["optimizer"] = {"name": "alkaid", "version": getattr(alkaid, "__version__", "?"), "nodes": report,
                         "solver_options": dict(SOLVER_OPTIONS)}
    return text, info
