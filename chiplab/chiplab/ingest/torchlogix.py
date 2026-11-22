"""torchlogix logic-gate networks -> chipir/1.

Supported modules, in order (an nn.Sequential or anything whose .children() are these): Flatten (identity on
vectors), LogicDense with lut_rank=2 (fixed or learnable connections; any parametrization exposing
get_luts_and_ids), GroupSum. Inputs are 1-bit lanes (binarise off-chip, or feed sensor bits directly).

Each logic neuron becomes one 2-input `lut` lane whose truth table is read from torchlogix's own export-mode
gate table (functional._map), so the chip computes exactly torchlogix's discrete eval/export forward.
GroupSum(k) becomes k popcounts (matvec of ones over each group) and an argmax; tau and beta are dropped
because they do not change the argmax (tau > 0). Outputs: "y" = class index, "scores" = the k popcounts.
"""
from __future__ import annotations

import torch

from chiplab.ir.schema import validate


def _truth_table(lut_id: int) -> list[int]:
    from torchlogix.functional import _map
    tab = []
    for idx in range(4):                       # IR lut index = bit(a) << 0 | bit(b) << 1
        a = torch.tensor([bool(idx & 1)]); b = torch.tensor([bool(idx & 2)])
        tab.append(int(_map[lut_id](a, b).item()))
    return tab


def _indices(layer) -> torch.Tensor:
    conn = layer.connections
    if hasattr(conn, "resolve_connections"):
        return conn.resolve_connections()
    return conn.indices


def _modules(model):
    kids = list(model.children())
    return kids if kids else [model]


def to_ir(model, in_dim: int | None = None, name: str = "torchlogix") -> dict:
    from torchlogix.layers import GroupSum, LogicDense
    nodes, prev, width = [], "x", in_dim
    gsum = None
    li = 0
    for m in _modules(model):
        if isinstance(m, torch.nn.Flatten) or isinstance(m, torch.nn.Identity):
            continue
        if isinstance(m, LogicDense):
            if m.lut_rank != 2:
                raise ValueError("only lut_rank=2 LogicDense layers are supported")
            if width is None:
                width = m.in_dim
            if m.in_dim != width:
                raise ValueError(f"LogicDense expects {m.in_dim} inputs, previous layer gives {width}")
            with torch.no_grad():
                _, ids = m.get_luts_and_ids()
                idx = _indices(m).cpu().long()
            ids = ids.cpu().long().tolist()
            cache = {}
            sel = [[int(idx[0, o]), int(idx[1, o])] for o in range(m.out_dim)]
            tabs = [cache.setdefault(i, _truth_table(i)) for i in ids]
            nodes.append({"id": f"g{li}", "op": "lut", "src": prev, "inputs": sel, "tables": tabs})
            prev, width, li = f"g{li}", m.out_dim, li + 1
        elif isinstance(m, GroupSum):
            gsum = m
            break
        else:
            raise ValueError(f"unsupported torchlogix module {type(m).__name__}")
    if width is None:
        raise ValueError("model has no LogicDense layer and no in_dim was given")
    outputs = []
    if gsum is not None:
        k = gsum.k
        if width % k:
            raise ValueError("GroupSum: features not divisible by k")
        g = width // k
        W = [[1 if j // g == c else 0 for j in range(width)] for c in range(k)]
        nodes.append({"id": "scores", "op": "matvec", "src": prev, "W": W})
        nodes.append({"id": "cls", "op": "argmax", "src": "scores"})
        outputs = [{"name": "y", "src": "cls"}, {"name": "scores", "src": "scores"}]
    else:
        outputs = [{"name": "y", "src": prev}]
    in_lanes = in_dim if in_dim is not None else next(m.in_dim for m in _modules(model) if isinstance(m, LogicDense))
    ir = {"ir": "chipir/1", "name": name, "inputs": [{"name": "x", "lanes": int(in_lanes), "bits": 1, "signed": False}],
          "nodes": nodes, "outputs": outputs,
          "meta": {"format": "torchlogix", "groupsum": {"k": gsum.k, "tau": float(gsum.tau), "beta": float(gsum.beta)} if gsum else None,
                   "note": "tau/beta dropped: argmax-invariant"}}
    return validate(ir)


def reference(model, X) -> dict:
    """torchlogix's own discrete forward (export mode, boolean ops) on 0/1 inputs: {'y', 'scores'}."""
    from torchlogix.layers import GroupSum
    from torchlogix.utils import set_export_mode
    set_export_mode(model, True)
    h = torch.as_tensor(X).bool()
    scores = None
    with torch.no_grad():
        for m in _modules(model):
            if isinstance(m, GroupSum):
                k = m.k
                scores = h.reshape(h.shape[0], k, -1).sum(-1).long()
                break
            h = m(h)
    set_export_mode(model, False)
    if scores is None:
        return {"y": h.long().numpy()}
    return {"y": scores.argmax(1).numpy()[:, None], "scores": scores.numpy()}
