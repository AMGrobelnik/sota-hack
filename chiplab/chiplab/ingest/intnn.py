"""Integer neural networks (binary / ternary / k-bit weights, shift + clip activations) -> chipir/1.

Accepts either form:
  * single hidden layer (feasibility-spike format):
      {"cfg": {"L", "bits", "feat" | "signed"}, "W1", "b1", "shift", "W2", "b2", "amax"}
  * multi-layer (chiplab intnn family int_params):
      {"layers": [{"W", "b", "shift", "amax"}], "Wo", "bo", "out_dim"}  plus an in_spec {lanes, bits, signed}
Semantics per hidden layer: h = clip((W h_prev + b) >> shift, 0, amax). Output: score = Wo h + bo;
decision = score > 0 (one output) or argmax(score) (several).
"""
from __future__ import annotations

from chiplab.ir.schema import validate


def to_layers(params: dict) -> tuple[dict, dict]:
    """Normalise either form to (multi-layer params, in_spec or {})."""
    if "layers" in params:
        return params, params.get("in_spec", {})
    c = params.get("cfg", {})
    W2 = params["W2"]
    Wo = [W2] if W2 and not isinstance(W2[0], list) else W2
    b2 = params["b2"]
    bo = [b2] if isinstance(b2, int) else list(b2)
    ml = {"layers": [{"W": params["W1"], "b": params["b1"], "shift": int(params["shift"]), "amax": int(params["amax"])}],
          "Wo": Wo, "bo": bo, "out_dim": len(Wo)}
    in_spec = {}
    if "L" in c and "bits" in c:
        signed = c.get("signed", c.get("feat") in ("drr", "delta"))
        in_spec = {"lanes": int(c["L"]), "bits": int(c["bits"]), "signed": bool(signed)}
    return ml, in_spec


def to_ir(params: dict, in_spec: dict | None = None, name: str = "intnn", input_name: str = "x",
          output_name: str = "y") -> dict:
    ml, spec0 = to_layers(params)
    spec = {**spec0, **(in_spec or {})}
    if not {"lanes", "bits", "signed"} <= set(spec):
        raise ValueError("intnn ingest needs an input spec {lanes, bits, signed}")
    nodes, prev = [], input_name
    for l, L in enumerate(ml["layers"]):
        nodes.append({"id": f"l{l}_mv", "op": "matvec", "src": prev, "W": L["W"], "b": L["b"]})
        nodes.append({"id": f"l{l}_sh", "op": "shift", "src": f"l{l}_mv", "k": int(L["shift"])})
        nodes.append({"id": f"l{l}", "op": "clip", "src": f"l{l}_sh", "lo": 0, "hi": int(L["amax"])})
        prev = f"l{l}"
    nodes.append({"id": "score", "op": "matvec", "src": prev, "W": ml["Wo"], "b": ml["bo"]})
    if ml.get("out_dim", len(ml["Wo"])) == 1:
        nodes.append({"id": "dec", "op": "cmp", "src": "score", "rel": "gt", "t": [0]})
    else:
        nodes.append({"id": "dec", "op": "argmax", "src": "score"})
    ir = {"ir": "chipir/1", "name": name,
          "inputs": [{"name": input_name, "lanes": int(spec["lanes"]), "bits": int(spec["bits"]), "signed": bool(spec["signed"])}],
          "nodes": nodes, "outputs": [{"name": output_name, "src": "dec"}],
          "meta": {"format": "intnn", "layers": len(ml["layers"])}}
    return validate(ir)
