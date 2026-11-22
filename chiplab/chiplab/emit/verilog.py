"""chipir/1 -> combinational Verilog-2005, weights wired in as constants.

Correct by construction:
  * every lane gets a plain unsigned vector of the width derived by ir/ranges.py (signedness tracked here);
  * arithmetic (matvec/add/sub) is done modulo 2^W at the destination width W, with every operand explicitly
    sign- or zero-extended (or truncated) to W. Modular arithmetic is exact because the true result fits W;
  * comparisons (clip, max, cmp, argmax, abs) are done in an explicitly wider signed context;
  * constant multiplications become canonical-signed-digit shift-adds (no multipliers).
Ports: input `x` lane i = x[i*bits +: bits]; output lanes packed at a uniform width, two's complement if any
lane can be negative.
"""
from __future__ import annotations

from chiplab.ir.ranges import csd, ranges as ir_ranges, width
from chiplab.ir.schema import IRError, top_name

VERILOG_KEYWORDS = {
    "always", "and", "assign", "begin", "buf", "case", "default", "else", "end", "endcase", "endmodule", "for",
    "function", "if", "initial", "inout", "input", "integer", "module", "nand", "negedge", "nor", "not", "or",
    "output", "parameter", "posedge", "reg", "signed", "wire", "xnor", "xor", "localparam", "generate", "genvar",
}
_OPS = {"gt": ">", "ge": ">=", "lt": "<", "le": "<=", "eq": "==", "ne": "!="}


def _lit(v: int, w: int) -> str:
    return f"{w}'d{v % (1 << w)}"


class _Lane:
    __slots__ = ("ref", "w", "s")

    def __init__(self, ref: str, w: int, s: bool):
        self.ref, self.w, self.s = ref, w, s


def _ext(x: _Lane, w: int) -> str:
    """Expression of exactly w bits holding x (sign/zero extended, or truncated for modular arithmetic)."""
    if w == x.w:
        return x.ref
    if w < x.w:
        return f"{x.ref}[{w - 1}:0]" if w > 1 else f"{x.ref}[0]"
    pad = w - x.w
    fill = f"{x.ref}[{x.w - 1}]" if x.s else "1'b0"
    return f"{{{{{pad}{{{fill}}}}}, {x.ref}}}"


def _sw(lo: int, hi: int) -> int:
    """Signed width covering [lo, hi] (always has a sign bit)."""
    w, s = width(lo, hi)
    return w if s else w + 1


def emit(ir: dict, top: str | None = None, node_impl=None) -> tuple[str, dict]:
    """Return (verilog text, port info). Port info lists inputs/outputs with lanes, bits, signed.

    node_impl (optional, default None = the standard emitter, output unchanged): a callable
    node_impl(node, lanes, widths, ranges) returning None (use the standard code for this node) or
    (lines, [(ref, width, signed) per lane]) to implement the node another way (see emit/optimized.py)."""
    R = ir_ranges(ir)
    top = top or top_name(ir)
    for p in list(ir["inputs"]) + list(ir["outputs"]):
        if p["name"] in VERILOG_KEYWORDS:
            raise IRError(f"port name {p['name']!r} is a Verilog keyword")
    L: dict[str, list[_Lane]] = {}
    body: list[str] = []
    tmp = [0]

    def decl(name: str, w: int, expr: str):
        body.append(f"  wire [{w - 1}:0] {name} = {expr};")

    def fresh(prefix: str) -> str:
        tmp[0] += 1
        return f"{prefix}_t{tmp[0]}"

    def node_lanes(i: str) -> list[tuple[int, bool]]:
        return [width(l, h) for l, h in R[i]]

    ports_in, ports_out = [], []
    for p in ir["inputs"]:
        b, nm = p["bits"], p["name"]
        ports_in.append(f"input wire [{p['lanes'] * b - 1}:0] {nm}")
        L[nm] = []
        for j in range(p["lanes"]):
            ref = f"i_{nm}_{j}"
            decl(ref, b, f"{nm}[{j * b + b - 1}:{j * b}]")
            L[nm].append(_Lane(ref, b, p["signed"]))

    for nd in ir.get("nodes", []):
        i, op = nd["id"], nd["op"]
        ws = node_lanes(i)
        if node_impl is not None:
            got = node_impl(nd, L, ws, R)
            if got is not None:
                lines, lanes = got
                body.extend(lines)
                L[i] = [_Lane(r, w, sg) for r, w, sg in lanes]
                continue
        out: list[_Lane] = []
        for j, (w, s) in enumerate(ws):
            ref = f"n_{i}_{j}"
            lo, hi = R[i][j]
            if op == "const":
                decl(ref, w, _lit(nd["values"][j], w))
            elif op == "matvec":
                x = L[nd["src"]]
                bias = (nd.get("b") or [0] * len(nd["W"]))[j]
                terms = []
                for xi, wt in zip(x, nd["W"][j]):
                    if wt == 0:
                        continue
                    e = _ext(xi, w)
                    for d, pw in csd(abs(wt)):
                        sign = d if wt > 0 else -d
                        t = e if pw == 0 else f"({e} << {pw})"
                        terms.append(("+" if sign > 0 else "-", t))
                if not terms:
                    expr = _lit(bias, w)
                else:
                    parts = [] if bias == 0 else [_lit(bias, w)]
                    for k, (sg, t) in enumerate(terms):
                        if not parts and sg == "+":
                            parts.append(t)
                        elif not parts:
                            parts.append(f"{_lit(0, w)} - {t}")
                        else:
                            parts.append(f"{sg} {t}")
                    expr = " ".join(parts)
                decl(ref, w, expr)
            elif op in ("add", "sub"):
                a, b = L[nd["a"]], L[nd["b"]]
                xa = a[j] if len(a) > 1 else a[0]
                xb = b[j] if len(b) > 1 else b[0]
                decl(ref, w, f"{_ext(xa, w)} {'+' if op == 'add' else '-'} {_ext(xb, w)}")
            elif op == "shift":
                x, k = L[nd["src"]][j], nd["k"]
                if k == 0:
                    decl(ref, w, _ext(x, w))
                elif k >= x.w:
                    decl(ref, w, f"{{{w}{{{x.ref}[{x.w - 1}]}}}}" if x.s else _lit(0, w))
                else:
                    sw = x.w - k
                    expr = f"{x.ref}[{x.w - 1}:{k}]" if sw > 1 else f"{x.ref}[{x.w - 1}]"
                    if w == sw:
                        decl(ref, w, expr)
                    else:  # name the slice first so further indexing/extension is valid Verilog
                        tn = fresh(ref); decl(tn, sw, expr)
                        decl(ref, w, _ext(_Lane(tn, sw, x.s), w))
            elif op == "clip":
                x = L[nd["src"]][j]
                sl, sh = R[nd["src"]][j]
                wc = max(_sw(sl, sh), _sw(nd["lo"], nd["lo"]), _sw(nd["hi"], nd["hi"])) + 1
                xs = f"$signed({_ext(x, wc)})"
                decl(ref, w, f"({xs} < $signed({_lit(nd['lo'], wc)})) ? {_lit(nd['lo'], w)} : "
                             f"({xs} > $signed({_lit(nd['hi'], wc)})) ? {_lit(nd['hi'], w)} : {_ext(x, w)}")
            elif op == "abs":
                x = L[nd["src"]][j]
                if not x.s:
                    decl(ref, w, _ext(x, w))
                else:
                    wc = x.w + 1
                    tn = fresh(ref)
                    decl(tn, wc, f"{x.ref}[{x.w - 1}] ? ({_lit(0, wc)} - {_ext(x, wc)}) : {_ext(x, wc)}")
                    decl(ref, w, _ext(_Lane(tn, wc, False), w))
            elif op == "max":
                xs = [L[nd["src"]][g] for g in nd["groups"][j]]
                rs = [R[nd["src"]][g] for g in nd["groups"][j]]
                wc = max(_sw(l, h) for l, h in rs) + 1
                cur = _Lane(fresh(ref), wc, True); decl(cur.ref, wc, _ext(xs[0], wc))
                for xn in xs[1:]:
                    nx = fresh(ref); en = _ext(xn, wc)
                    decl(nx, wc, f"($signed({en}) > $signed({cur.ref})) ? {en} : {cur.ref}")
                    cur = _Lane(nx, wc, True)
                decl(ref, w, _ext(cur, w))
            elif op == "cmp":
                x = L[nd["src"]][j]; sl, sh = R[nd["src"]][j]
                if "other" in nd:
                    ol = L[nd["other"]]; o = ol[j] if len(ol) > 1 else ol[0]
                    orr = R[nd["other"]][j if len(ol) > 1 else 0]
                    wc = max(_sw(sl, sh), _sw(*orr)) + 1
                    rhs = f"$signed({_ext(o, wc)})"
                else:
                    t = nd["t"]; tv = t if isinstance(t, int) else (t[j] if len(t) > 1 else t[0])
                    wc = max(_sw(sl, sh), _sw(tv, tv)) + 1
                    rhs = f"$signed({_lit(tv, wc)})"
                decl(ref, w, f"($signed({_ext(x, wc)}) {_OPS[nd['rel']]} {rhs}) ? 1'b1 : 1'b0")
            elif op == "gather":
                x = L[nd["src"]][nd["idx"][j]]
                decl(ref, w, _ext(x, w))
            elif op == "concat":
                flat = [ln for s in nd["srcs"] for ln in L[s]]
                decl(ref, w, _ext(flat[j], w))
            elif op == "lut":
                x = L[nd["src"]]; sel, tab = nd["inputs"][j], nd["tables"][j]
                tn = fresh(ref); n = len(tab)
                bits = "".join(str(tab[k]) for k in reversed(range(n)))
                decl(tn, n, f"{n}'b{bits}")
                idx = ", ".join(f"{x[m].ref}[0]" if x[m].w > 1 else x[m].ref for m in reversed(sel))
                decl(ref, w, f"{tn}[{{{idx}}}]" if len(sel) > 1 else f"{tn}[{idx}]")
            elif op == "argmax":
                xs, rs = L[nd["src"]], R[nd["src"]]
                wc = max(_sw(l, h) for l, h in rs) + 1
                bv = fresh(ref); decl(bv, wc, _ext(xs[0], wc))
                bi = fresh(ref); decl(bi, w, _lit(0, w))
                for k in range(1, len(xs)):
                    en = _ext(xs[k], wc); c = fresh(ref)
                    decl(c, 1, f"($signed({en}) > $signed({bv})) ? 1'b1 : 1'b0")
                    nv, ni = fresh(ref), fresh(ref)
                    decl(nv, wc, f"{c} ? {en} : {bv}"); decl(ni, w, f"{c} ? {_lit(k, w)} : {bi}")
                    bv, bi = nv, ni
                decl(ref, w, bi)
            else:  # pragma: no cover
                raise IRError(f"unknown op {op}")
            out.append(_Lane(ref, w, s))
        L[i] = out

    info_out = []
    for o in ir["outputs"]:
        lanes, rr = L[o["src"]], R[o["src"]]
        signed = any(l < 0 for l, _ in rr)
        wo = max(_sw(l, h) if signed else width(l, h)[0] for l, h in rr)
        ports_out.append(f"output wire [{len(lanes) * wo - 1}:0] {o['name']}")
        parts = [_ext(ln, wo) for ln in reversed(lanes)]
        body.append(f"  assign {o['name']} = {{{', '.join(parts)}}};" if len(parts) > 1 else f"  assign {o['name']} = {parts[0]};")
        info_out.append({"name": o["name"], "lanes": len(lanes), "bits": wo, "signed": signed})

    head = [f"// chipin.space chip lab: generated from {ir['ir']} design {top}. Do not edit; regenerate.",
            f"module {top} (", ",\n".join("  " + p for p in ports_in + ports_out), ");"]
    text = "\n".join(head + body + ["endmodule", ""])
    info = {"top": top, "inputs": [dict(p) for p in ir["inputs"]], "outputs": info_out}
    return text, info
