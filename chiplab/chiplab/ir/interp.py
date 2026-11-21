"""Reference interpreter for chipir/1 in numpy int64. This IS "the integer model" of the verification ladder."""
from __future__ import annotations

import numpy as np

from chiplab.ir.ranges import ranges as ir_ranges
from chiplab.ir.schema import IRError

_REL = {"gt": np.greater, "ge": np.greater_equal, "lt": np.less, "le": np.less_equal, "eq": np.equal, "ne": np.not_equal}


def run(ir: dict, inputs: dict | np.ndarray, check_ranges: bool = True, all_nodes: bool = False) -> dict:
    """Evaluate the IR on integer inputs. inputs: {name: int array [N, lanes]} or a single array for one input.

    Returns {output name: int64 [N, lanes]} (plus every node if all_nodes). With check_ranges, asserts every
    value lies inside its interval, which is what makes the derived Verilog widths safe.
    """
    R = ir_ranges(ir)
    if not isinstance(inputs, dict):
        if len(ir["inputs"]) != 1:
            raise IRError("several inputs: pass a dict")
        inputs = {ir["inputs"][0]["name"]: inputs}
    V: dict[str, np.ndarray] = {}
    N = None
    for p in ir["inputs"]:
        x = np.asarray(inputs[p["name"]], dtype=np.int64)
        if x.ndim == 1:
            x = x[:, None]
        if x.shape[1] != p["lanes"]:
            raise IRError(f"input {p['name']}: expected {p['lanes']} lanes, got {x.shape[1]}")
        N = x.shape[0]
        V[p["name"]] = x

    def lane_bc(a, b):
        if a.shape[1] == b.shape[1]:
            return a, b
        return (np.repeat(a, b.shape[1], 1), b) if a.shape[1] == 1 else (a, np.repeat(b, a.shape[1], 1))

    for nd in ir.get("nodes", []):
        op = nd["op"]
        if op == "const":
            y = np.broadcast_to(np.asarray(nd["values"], np.int64)[None, :], (N, len(nd["values"]))).copy()
        elif op == "matvec":
            W = np.asarray(nd["W"], dtype=np.int64)
            y = V[nd["src"]] @ W.T
            if nd.get("b") is not None:
                y = y + np.asarray(nd["b"], dtype=np.int64)[None, :]
        elif op == "add":
            a, b = lane_bc(V[nd["a"]], V[nd["b"]]); y = a + b
        elif op == "sub":
            a, b = lane_bc(V[nd["a"]], V[nd["b"]]); y = a - b
        elif op == "shift":
            y = V[nd["src"]] >> nd["k"]          # numpy >> on int64 is arithmetic (floor)
        elif op == "clip":
            y = np.clip(V[nd["src"]], nd["lo"], nd["hi"])
        elif op == "abs":
            y = np.abs(V[nd["src"]])
        elif op == "max":
            x = V[nd["src"]]
            y = np.stack([x[:, g].max(axis=1) for g in nd["groups"]], axis=1)
        elif op == "cmp":
            x = V[nd["src"]]
            if "other" in nd:
                x, o = lane_bc(x, V[nd["other"]])
            else:
                t = nd["t"]
                o = np.asarray([t] if isinstance(t, int) else t, dtype=np.int64)[None, :]
            y = _REL[nd["rel"]](x, o).astype(np.int64)
        elif op == "gather":
            y = V[nd["src"]][:, nd["idx"]]
        elif op == "concat":
            y = np.concatenate([V[s] for s in nd["srcs"]], axis=1)
        elif op == "lut":
            x = V[nd["src"]]
            cols = []
            for sel, tab in zip(nd["inputs"], nd["tables"]):
                idx = np.zeros(N, dtype=np.int64)
                for m, j in enumerate(sel):
                    idx |= (x[:, j] & 1) << m
                cols.append(np.asarray(tab, dtype=np.int64)[idx])
            y = np.stack(cols, axis=1)
        elif op == "argmax":
            y = np.argmax(V[nd["src"]], axis=1)[:, None].astype(np.int64)  # first max on ties
        else:  # pragma: no cover
            raise IRError(f"unknown op {op}")
        if check_ranges and y.size:
            lo = np.array([r[0] for r in R[nd["id"]]]); hi = np.array([r[1] for r in R[nd["id"]]])
            if (y < lo[None, :]).any() or (y > hi[None, :]).any():
                raise IRError(f"node {nd['id']}: value outside its derived range (interpreter or range bug)")
        V[nd["id"]] = y
    out = {o["name"]: V[o["src"]] for o in ir["outputs"]}
    if all_nodes:
        out["_nodes"] = V
    return out
