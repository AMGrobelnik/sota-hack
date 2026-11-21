"""chipir/1: the canonical integer IR every model family and on-chip front-end lowers to.

One IR, so one interpreter (ir/interp.py = "the integer model"), one Verilog emitter (emit/verilog.py),
one netlist evaluator and one formal check serve every chip the lab can make.

Document:
    {"ir": "chipir/1", "name": str,
     "inputs":  [{"name": str, "lanes": int, "bits": int, "signed": bool}],
     "nodes":   [{"id": str, "op": str, ...op fields}],
     "outputs": [{"name": str, "src": node_or_input_id}],
     "meta":    {...free-form provenance: family, frontend, encoding, candidate...}}

Values: every node produces a vector of integer lanes. Integers are mathematically unbounded; bit widths are
NEVER declared on nodes, they are derived from input ranges by interval arithmetic (ir/ranges.py), so the
circuit cannot overflow by construction. Inputs: signed -> [-2^(b-1), 2^(b-1)-1], unsigned -> [0, 2^b-1].
Input lane i of port x sits at bits x[i*bits +: bits] (two's complement when signed).

Ops (closed set; adding one is a core change and must pass tests/test_ir_fuzz.py):
    const   {values: [int]}                                   -> the constants
    matvec  {src, W: [[int]] (out x in), b: [int] | absent}   -> y_o = sum_i W[o][i]*x_i + b_o
    add     {a, b}                                            -> a_i + b_i   (equal lanes, or one side 1 lane)
    sub     {a, b}                                            -> a_i - b_i   (same broadcasting)
    shift   {src, k >= 0}                                     -> floor(x_i / 2^k)  (arithmetic right shift)
    clip    {src, lo: int, hi: int}                           -> min(max(x_i, lo), hi)
    abs     {src}                                             -> |x_i|
    max     {src, groups: [[lane idx]]}                       -> y_g = max over group g
    cmp     {src, rel: gt|ge|lt|le|eq|ne, t: [int] | int}     -> 1 if x_i rel t_i else 0
    cmp     {src, rel, other: id}                             -> 1 if x_i rel other_i else 0
    gather  {src, idx: [lane idx]}                            -> y_j = x_{idx_j}  (repeats allowed)
    concat  {srcs: [id]}                                      -> lanes of each src in order
    lut     {src, inputs: [[lane idx]], tables: [[0|1]]}      -> y_j = tables[j][sum_m bit(x_{inputs[j][m]}) << m]
                                                                 (src lanes must be in {0,1}; len(table)=2^len(inputs))
    argmax  {src}                                             -> one lane: index of the max (lowest index on ties)
"""
from __future__ import annotations

import copy
import hashlib
import json

IR_VERSION = "chipir/1"
OPS = ("const", "matvec", "add", "sub", "shift", "clip", "abs", "max", "cmp", "gather", "concat", "lut", "argmax")
RELS = ("gt", "ge", "lt", "le", "eq", "ne")


class IRError(ValueError):
    pass


def _req(cond, msg):
    if not cond:
        raise IRError(msg)


def _ints(xs, what):
    _req(isinstance(xs, list) and all(isinstance(v, int) and not isinstance(v, bool) for v in xs), f"{what} must be a list of ints")


def lanes_of(ir: dict) -> dict:
    """Validate the document and return {id: lane count} for every input and node."""
    _req(isinstance(ir, dict) and ir.get("ir") == IR_VERSION, f"not a {IR_VERSION} document")
    n: dict[str, int] = {}
    _req(ir.get("inputs"), "at least one input required")
    for p in ir["inputs"]:
        _req(isinstance(p.get("name"), str) and p["name"].isidentifier(), f"bad input name {p.get('name')!r}")
        _req(isinstance(p.get("lanes"), int) and p["lanes"] >= 1, f"input {p['name']}: lanes >= 1")
        _req(isinstance(p.get("bits"), int) and 1 <= p["bits"] <= 32, f"input {p['name']}: 1 <= bits <= 32")
        _req(isinstance(p.get("signed"), bool), f"input {p['name']}: signed must be bool")
        _req(p["name"] not in n, f"duplicate id {p['name']}")
        n[p["name"]] = p["lanes"]

    def src(node, key="src"):
        s = node.get(key)
        _req(s in n, f"node {node.get('id')}: unknown {key} {s!r}")
        return s

    for node in ir.get("nodes", []):
        i, op = node.get("id"), node.get("op")
        _req(isinstance(i, str) and i.isidentifier(), f"bad node id {i!r}")
        _req(i not in n, f"duplicate id {i}")
        _req(op in OPS, f"node {i}: unknown op {op!r}")
        if op == "const":
            _ints(node.get("values"), f"{i}.values"); _req(node["values"], f"{i}: empty const")
            n[i] = len(node["values"])
        elif op == "matvec":
            s = src(node); W = node.get("W")
            _req(isinstance(W, list) and W, f"{i}: W must be a non-empty list of rows")
            for r in W:
                _ints(r, f"{i}.W row"); _req(len(r) == n[s], f"{i}: W rows must have {n[s]} columns")
            if node.get("b") is not None:
                _ints(node["b"], f"{i}.b"); _req(len(node["b"]) == len(W), f"{i}: len(b) must equal rows of W")
            n[i] = len(W)
        elif op in ("add", "sub"):
            a, b = src(node, "a"), src(node, "b")
            _req(n[a] == n[b] or 1 in (n[a], n[b]), f"{i}: lane mismatch {n[a]} vs {n[b]}")
            n[i] = max(n[a], n[b])
        elif op == "shift":
            s = src(node); _req(isinstance(node.get("k"), int) and node["k"] >= 0, f"{i}: k >= 0")
            n[i] = n[s]
        elif op == "clip":
            s = src(node)
            _req(isinstance(node.get("lo"), int) and isinstance(node.get("hi"), int) and node["lo"] <= node["hi"], f"{i}: lo <= hi ints")
            n[i] = n[s]
        elif op == "abs":
            n[i] = n[src(node)]
        elif op == "max":
            s = src(node); g = node.get("groups")
            _req(isinstance(g, list) and g, f"{i}: groups required")
            for grp in g:
                _ints(grp, f"{i}.groups"); _req(grp and all(0 <= j < n[s] for j in grp), f"{i}: bad group {grp}")
            n[i] = len(g)
        elif op == "cmp":
            s = src(node); _req(node.get("rel") in RELS, f"{i}: rel must be one of {RELS}")
            if "other" in node:
                o = src(node, "other"); _req(n[o] == n[s] or n[o] == 1, f"{i}: other lanes")
            else:
                t = node.get("t")
                if isinstance(t, int) and not isinstance(t, bool):
                    pass
                else:
                    _ints(t, f"{i}.t"); _req(len(t) in (1, n[s]), f"{i}: t must have 1 or {n[s]} values")
            n[i] = n[s]
        elif op == "gather":
            s = src(node); idx = node.get("idx")
            _ints(idx, f"{i}.idx"); _req(idx and all(0 <= j < n[s] for j in idx), f"{i}: idx out of range")
            n[i] = len(idx)
        elif op == "concat":
            ss = node.get("srcs"); _req(isinstance(ss, list) and ss, f"{i}: srcs required")
            for s in ss:
                _req(s in n, f"{i}: unknown src {s!r}")
            n[i] = sum(n[s] for s in ss)
        elif op == "lut":
            s = src(node); ins, tabs = node.get("inputs"), node.get("tables")
            _req(isinstance(ins, list) and isinstance(tabs, list) and ins and len(ins) == len(tabs), f"{i}: inputs/tables")
            for sel, tab in zip(ins, tabs):
                _ints(sel, f"{i}.inputs"); _ints(tab, f"{i}.tables")
                _req(1 <= len(sel) <= 12 and all(0 <= j < n[s] for j in sel), f"{i}: lut select {sel}")
                _req(len(tab) == 2 ** len(sel) and all(v in (0, 1) for v in tab), f"{i}: table must be 2^k bits")
            n[i] = len(ins)
        elif op == "argmax":
            n[i] = 1 if n[src(node)] >= 1 else 0
    _req(ir.get("outputs"), "at least one output required")
    names = set()
    for o in ir["outputs"]:
        _req(isinstance(o.get("name"), str) and o["name"].isidentifier(), f"bad output name {o.get('name')!r}")
        # ports share a namespace (inputs + outputs); node ids are internal and may reuse a port name
        _req(o["name"] not in names and o["name"] not in {p["name"] for p in ir["inputs"]}, f"output name {o['name']} clashes")
        _req(o.get("src") in n, f"output {o['name']}: unknown src {o.get('src')!r}")
        names.add(o["name"])
    return n


def validate(ir: dict) -> dict:
    lanes_of(ir)
    return ir


def canonical(ir: dict) -> str:
    """Canonical JSON of the computation (meta excluded, so provenance does not change the design id)."""
    core = {k: ir[k] for k in ("ir", "inputs", "nodes", "outputs")}
    return json.dumps(core, sort_keys=True, separators=(",", ":"))


def design_id(ir: dict) -> str:
    return hashlib.sha256(canonical(ir).encode()).hexdigest()[:12]


def clone(ir: dict) -> dict:
    return copy.deepcopy(ir)


def top_name(ir: dict) -> str:
    """Verilog module name for this design."""
    return "chip_" + design_id(ir)
