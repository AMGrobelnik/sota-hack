"""Verification ladder level 1: circuit == integer model (== training model) on every given input."""
from __future__ import annotations

import numpy as np

from chiplab.ir.interp import run as interp
from chiplab.verify.netlist_eval import Netlist, bits_to_lanes, lanes_to_bits


def circuit_outputs(netlist_json: str, port_info: dict, X: dict | np.ndarray, device: str = "numpy") -> dict:
    """Run integer inputs through the gate netlist; return {output name: int [N, lanes]}."""
    if not isinstance(X, dict):
        X = {port_info["inputs"][0]["name"]: X}
    from chiplab.device import resolve
    device = resolve(device)
    net = Netlist(netlist_json, port_info["top"])
    bits_in = {p["name"]: lanes_to_bits(X[p["name"]], p["bits"]) for p in port_info["inputs"]}
    raw = net.evaluate(bits_in, device=device)
    return {o["name"]: bits_to_lanes(raw[o["name"]], o["lanes"], o["bits"], o["signed"]) for o in port_info["outputs"]}


def check(ir: dict, netlist_json: str, port_info: dict, X: dict | np.ndarray, reference: np.ndarray | None = None,
          device: str = "numpy") -> dict:
    """Compare circuit vs IR interpreter (vs an optional third reference, e.g. the training framework's decisions).

    Returns counts per pair; `bit_exact` is True only when every compared pair matches on every input and lane.
    """
    model = interp(ir, X)
    circ = circuit_outputs(netlist_json, port_info, X, device=device)
    res = {"n": None, "pairs": {}}
    ok = True
    for o in port_info["outputs"]:
        a, b = circ[o["name"]], model[o["name"]]
        n = a.shape[0]; res["n"] = n
        mism = int((a != b).any(axis=1).sum())
        res["pairs"][f"circuit_vs_integer_model[{o['name']}]"] = {"identical": n - mism, "mismatches": mism}
        ok &= mism == 0
    if reference is not None:
        name = port_info["outputs"][0]["name"]
        ref = np.asarray(reference).reshape(len(reference), -1)
        for lab, arr in (("integer_model_vs_training_model", model[name]), ("circuit_vs_training_model", circ[name])):
            mism = int((arr != ref).any(axis=1).sum())
            res["pairs"][lab] = {"identical": len(ref) - mism, "mismatches": mism}
            ok &= mism == 0
    res["bit_exact"] = bool(ok)
    res["circuit"] = circ
    return res
