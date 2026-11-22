"""A second, deliberately naive Verilog rendering of chipir/1, used only as the formal-proof reference.

It shares nothing with emit/verilog.py beyond the IR: every lane is a 64-bit signed wire, constant
multiplications are written as `*`, shifts as `>>>`, comparisons directly. Proving the synthesised gate netlist
equal to this module therefore checks the production emitter AND synthesis against the IR semantics.
"""
from __future__ import annotations

from chiplab.ir.ranges import ranges as ir_ranges, width

_OPS = {"gt": ">", "ge": ">=", "lt": "<", "le": "<=", "eq": "==", "ne": "!="}


def _c(v: int) -> str:
    return f"(64'sd{v})" if v >= 0 else f"(-64'sd{-v})"


def emit_golden(ir: dict, module: str, port_info: dict, wide: int | None = None) -> str:
    """wide=None: one uniform width = widest derived signed width + 2 (modular arithmetic is exact there).
    wide=64: the fully naive rendering."""
    R = ir_ranges(ir)
    if wide is None:
        ws = [width(l, h) for v in R.values() for l, h in v]
        wide = max((w if s else w + 1) for w, s in ws) + 2
    body, L = [], {}
    ports = []
    for p in ir["inputs"]:
        b, nm = p["bits"], p["name"]
        ports.append(f"input wire [{p['lanes'] * b - 1}:0] {nm}")
        L[nm] = []
        for j in range(p["lanes"]):
            r = f"g_{nm}_{j}"
            sl = f"{nm}[{j * b + b - 1}:{j * b}]"
            body.append(f"  wire signed [63:0] {r} = " + (f"$signed({sl})" if p["signed"] else f"$signed({{1'b0, {sl}}})") + ";")
            L[nm].append(r)
    for nd in ir.get("nodes", []):
        i, op = nd["id"], nd["op"]
        out = []
        n = len(R[i])
        for j in range(n):
            r = f"g_{i}_{j}"
            if op == "const":
                e = _c(nd["values"][j])
            elif op == "matvec":
                b = (nd.get("b") or [0] * len(nd["W"]))[j]
                e = " + ".join([_c(b)] + [f"({_c(w)} * {x})" for w, x in zip(nd["W"][j], L[nd["src"]]) if w])
            elif op in ("add", "sub"):
                a, bb = L[nd["a"]], L[nd["b"]]
                e = f"{a[j] if len(a) > 1 else a[0]} {'+' if op == 'add' else '-'} {bb[j] if len(bb) > 1 else bb[0]}"
            elif op == "shift":
                e = f"({L[nd['src']][j]} >>> {nd['k']})"
            elif op == "clip":
                x = L[nd["src"]][j]
                e = f"(({x} < {_c(nd['lo'])}) ? {_c(nd['lo'])} : (({x} > {_c(nd['hi'])}) ? {_c(nd['hi'])} : {x}))"
            elif op == "abs":
                x = L[nd["src"]][j]; e = f"(({x} < 64'sd0) ? -{x} : {x})"
            elif op == "max":
                xs = [L[nd["src"]][g] for g in nd["groups"][j]]
                e = xs[0]
                for x in xs[1:]:
                    e = f"(({x} > {e}) ? {x} : {e})"
            elif op == "cmp":
                x = L[nd["src"]][j]
                if "other" in nd:
                    o = L[nd["other"]]; rhs = o[j] if len(o) > 1 else o[0]
                else:
                    t = nd["t"]; rhs = _c(t if isinstance(t, int) else (t[j] if len(t) > 1 else t[0]))
                e = f"(({x} {_OPS[nd['rel']]} {rhs}) ? 64'sd1 : 64'sd0)"
            elif op == "gather":
                e = L[nd["src"]][nd["idx"][j]]
            elif op == "concat":
                e = [x for s in nd["srcs"] for x in L[s]][j]
            elif op == "lut":
                sel, tab = nd["inputs"][j], nd["tables"][j]
                idx = " + ".join(f"({L[nd['src']][m]} * 64'sd{1 << k})" for k, m in enumerate(sel))
                ones = [str(v) for v, t in enumerate(tab) if t]
                e = "64'sd0" if not ones else "((" + " || ".join(f"(({idx}) == 64'sd{v})" for v in ones) + ") ? 64'sd1 : 64'sd0)"
            elif op == "argmax":
                xs = L[nd["src"]]
                bv, bi = xs[0], "64'sd0"
                for k in range(1, len(xs)):
                    body.append(f"  wire signed [63:0] {r}_v{k} = ({xs[k]} > {bv}) ? {xs[k]} : {bv};")
                    body.append(f"  wire signed [63:0] {r}_i{k} = ({xs[k]} > {bv}) ? 64'sd{k} : {bi};")
                    bv, bi = f"{r}_v{k}", f"{r}_i{k}"
                e = bi
            body.append(f"  wire signed [63:0] {r} = {e};")
            out.append(r)
        L[i] = out
    for o in port_info["outputs"]:
        wo = o["bits"]
        ports.append(f"output wire [{o['lanes'] * wo - 1}:0] {o['name']}")
        lanes = L[ir_src(ir, o["name"])]
        body.append(f"  assign {o['name']} = {{{', '.join(f'{x}[{wo - 1}:0]' for x in reversed(lanes))}}};")
    text = "\n".join([f"module {module} (", ",\n".join("  " + p for p in ports), ");"] + body + ["endmodule", ""])
    # only the internal lane wires are 64-bit placeholders; a port or slice that is really 64 bits wide must keep its width
    return text.replace("signed [63:0]", f"signed [{wide - 1}:0]").replace("64'sd", f"{wide}'sd")


def ir_src(ir: dict, out_name: str) -> str:
    return next(o["src"] for o in ir["outputs"] if o["name"] == out_name)
