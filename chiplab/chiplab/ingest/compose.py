"""Several models -> one multi-output chip, with fusion logic between their decisions.

compose(heads, fusion, shared_inputs) returns one chipir/1 document:
  * every head keeps its own nodes (ids prefixed "<head>__") and its outputs become chip outputs named
    "<head>_<output>";
  * input ports with the same name and identical spec are shared when shared_inputs=True (one sensor feeding
    several heads); otherwise each head's ports are renamed "<head>_<port>" (one sensor per head);
  * fusion outputs combine 1-bit head decisions: and (all), or (any), kofn (at least k of n). Built from
    existing ops only: concat -> matvec of ones -> cmp ge k.
  * score-level fusion combines multi-bit head scores (e.g. the same per-channel model on several channel
    ports, shared_inputs=False): max (largest score) or sum (total score) over every lane of the inputs,
    then cmp <rel> t gives a 1-bit decision. Spec {name, op: max|sum, t, rel? (ge), score? (false),
    inputs}; score=true also exposes the fused score as output "<name>_score". Built from existing ops:
    concat -> max over one group (max) or matvec of ones (sum) -> cmp.

IO_SPEC documents a chip's interface for the AI scientist:
  {"inputs":  [{"name", "lanes", "bits", "signed"}],
   "outputs": [{"name", "lanes", "lo", "hi"}],          (value range per output, from interval analysis)
   "mode":    "one-shot" | "streaming"}                  (streaming = emit/stream.py wrapper, TT pinout)
"""
from __future__ import annotations

import copy

from chiplab.ir.ranges import ranges
from chiplab.ir.schema import RELS, IRError, validate

IO_SPEC = __doc__
DECISION_OPS = ("and", "or", "kofn")
SCORE_OPS = ("max", "sum")

_REF_KEYS = ("src", "other")  # plus a/b for add/sub only ("b" is a bias on matvec)


def io_spec(ir: dict, mode: str = "one-shot") -> dict:
    R = ranges(ir)
    outs = []
    for o in ir["outputs"]:
        rr = R[o["src"]]
        outs.append({"name": o["name"], "lanes": len(rr), "lo": min(l for l, _ in rr), "hi": max(h for _, h in rr)})
    return {"inputs": [dict(p) for p in ir["inputs"]], "outputs": outs, "mode": mode}


def compose(heads: dict, fusion: list | None = None, shared_inputs: bool = True, name: str = "composed") -> dict:
    if not heads:
        raise IRError("compose needs at least one head")
    ports: dict[str, dict] = {}
    nodes, outputs = [], []
    out_src: dict[str, str] = {}
    for h, ir0 in heads.items():
        if not h.isidentifier():
            raise IRError(f"head name {h!r} must be an identifier")
        ir = copy.deepcopy(validate(ir0))
        rename = {}
        for p in ir["inputs"]:
            spec = {k: p[k] for k in ("lanes", "bits", "signed")}
            pn = p["name"] if shared_inputs else f"{h}_{p['name']}"
            if pn in ports and ports[pn] != spec:
                if shared_inputs:
                    raise IRError(f"input {pn!r} has different specs across heads; use shared_inputs=false")
                raise IRError(f"input name clash {pn!r}")
            ports[pn] = spec
            rename[p["name"]] = pn
        for nd in ir.get("nodes", []):
            rename[nd["id"]] = f"{h}__{nd['id']}"
        for nd in ir.get("nodes", []):
            nd = dict(nd)
            nd["id"] = rename[nd["id"]]
            for k in _REF_KEYS + (("a", "b") if nd["op"] in ("add", "sub") else ()):
                if k in nd:
                    nd[k] = rename[nd[k]]
            if "srcs" in nd:
                nd["srcs"] = [rename[s] for s in nd["srcs"]]
            nodes.append(nd)
        for o in ir["outputs"]:
            on = f"{h}_{o['name']}"
            outputs.append({"name": on, "src": rename[o["src"]]})
            out_src[on] = rename[o["src"]]
    doc = {"ir": "chipir/1", "name": name,
           "inputs": [{"name": n, **s} for n, s in ports.items()], "nodes": nodes, "outputs": outputs,
           "meta": {"format": "composed", "heads": list(heads), "fusion": fusion or [], "shared_inputs": shared_inputs}}
    if fusion:
        R = ranges(validate(doc))
        for f in fusion:
            fn, op, ins = f["name"], f["op"], f["inputs"]
            if op in SCORE_OPS:
                _score_fusion(f, out_src, R, nodes, outputs)
                continue
            srcs = []
            for i in ins:
                if i not in out_src:
                    raise IRError(f"fusion {fn}: unknown head output {i!r}; known: {list(out_src)}")
                if any(not (0 <= l and h <= 1) for l, h in R[out_src[i]]):
                    raise IRError(f"fusion {fn}: {i} is not a 1-bit decision")
                srcs.append(out_src[i])
            n = sum(len(R[s]) for s in srcs)
            k = {"and": n, "or": 1}.get(op, f.get("k"))
            if op not in ("and", "or", "kofn") or not isinstance(k, int) or not 1 <= k <= n:
                raise IRError(f"fusion {fn}: op must be and|or|kofn with 1 <= k <= {n}")
            base = f"fuse_{fn}"
            nodes.append({"id": f"{base}_bits", "op": "concat", "srcs": srcs})
            nodes.append({"id": f"{base}_cnt", "op": "matvec", "src": f"{base}_bits", "W": [[1] * n]})
            nodes.append({"id": base, "op": "cmp", "src": f"{base}_cnt", "rel": "ge", "t": [k]})
            outputs.append({"name": fn, "src": base})
    return validate(doc)


def _score_fusion(f: dict, out_src: dict, R: dict, nodes: list, outputs: list) -> None:
    """max | sum over every lane of the named head outputs, then one threshold compare (1-bit decision)."""
    fn, op, ins = f["name"], f["op"], f.get("inputs")
    if not isinstance(ins, list) or not ins:
        raise IRError(f"fusion {fn}: inputs must be a non-empty list of head outputs")
    srcs = []
    for i in ins:
        if i not in out_src:
            raise IRError(f"fusion {fn}: unknown head output {i!r}; known: {list(out_src)}")
        srcs.append(out_src[i])
    t, rel = f.get("t"), f.get("rel", "ge")
    if not isinstance(t, int) or isinstance(t, bool):
        raise IRError(f"fusion {fn}: op {op} needs an integer threshold t")
    if rel not in RELS:
        raise IRError(f"fusion {fn}: rel must be one of {RELS}")
    n = sum(len(R[s]) for s in srcs)
    base = f"fuse_{fn}"
    nodes.append({"id": f"{base}_cat", "op": "concat", "srcs": srcs})
    if op == "max":
        nodes.append({"id": f"{base}_score", "op": "max", "src": f"{base}_cat", "groups": [list(range(n))]})
    else:
        nodes.append({"id": f"{base}_score", "op": "matvec", "src": f"{base}_cat", "W": [[1] * n]})
    nodes.append({"id": base, "op": "cmp", "src": f"{base}_score", "rel": rel, "t": [t]})
    outputs.append({"name": fn, "src": base})
    if f.get("score"):
        outputs.append({"name": f"{fn}_score", "src": f"{base}_score"})
