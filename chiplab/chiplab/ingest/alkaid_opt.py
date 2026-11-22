"""Optional: alkaid (LGPL-3.0, used as a pip dependency only, never vendored) as a constant-multiply optimiser.

alkaid traces a quantised constant matrix-vector product and emits shift-add Verilog with common-subexpression
elimination (CMVM). compare_matvec() synthesises alkaid's version and ours for the same weights so the AI
scientist can see which is smaller for a given layer. Our emitter stays the production path; alkaid output is
reported for comparison (its port layout is alkaid's own, so it is not spliced into chips here).
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np

from chiplab.emit.verilog import emit
from chiplab.hw.yosys import run, synth_generic, _stat_json


def alkaid_matvec(W, b, bits: int, signed: bool, workdir: Path, name: str = "alk_mv") -> dict:
    from alkaid.codegen import RTLModel
    from alkaid.trace import FVArrayInput, trace
    W = np.asarray(W); b = np.zeros(W.shape[0], dtype=np.int64) if b is None else np.asarray(b)
    x = FVArrayInput((W.shape[1],))
    xq = x.quantize(k=1 if signed else 0, i=bits - 1 if signed else bits, f=0)
    comb = trace(x, xq @ W.T + b)
    workdir = Path(workdir); workdir.mkdir(parents=True, exist_ok=True)
    prj = workdir / name
    RTLModel(comb, prj, prj_name=name, flavor="verilog", print_latency=False).write()
    files = sorted(p for p in (prj / "src").rglob("*.v") if not p.name.endswith("_wrapper.v"))
    lo, hi = (-(1 << (bits - 1)), 1 << (bits - 1)) if signed else (0, 1 << bits)
    X = np.random.default_rng(0).integers(lo, hi, size=(2000, W.shape[1])).astype(float)
    exact = bool(np.array_equal(comb.predict(X), X @ W.T + b))
    return {"files": [str(f) for f in files], "top": name, "predict_bit_exact": exact}


def compare_matvec(W, b, bits: int, signed: bool, workdir: Path) -> dict:
    """Gate counts (Yosys generic gates, fast ABC) of the same constant matvec: alkaid vs chiplab's emitter."""
    workdir = Path(workdir)
    a = alkaid_matvec(W, b, bits, signed, workdir / "alkaid")
    reads = "\n".join(f"read_verilog -sv {f}" for f in a["files"])
    script = f"""{reads}
hierarchy -check -top {a['top']}
synth -top {a['top']} -flatten -noabc
abc -g AND,NAND,OR,NOR,XOR,XNOR,ANDNOT,ORNOT,MUX -script "+strash;dc2;map"
opt_clean -purge
tee -q -o stat.json stat -json
"""
    run(script, workdir / "alkaid_syn", 900, "alkaid_synth")
    by = _stat_json(workdir / "alkaid_syn" / "stat.json", a["top"])["cells_by_type"]
    alk = sum(v for k, v in by.items() if k != "$_BUF_")
    ir = {"ir": "chipir/1", "name": "mv", "inputs": [{"name": "x", "lanes": int(np.shape(W)[1]), "bits": bits, "signed": signed}],
          "nodes": [{"id": "mv", "op": "matvec", "src": "x", "W": np.asarray(W).tolist(),
                     "b": (np.zeros(len(W), int) if b is None else np.asarray(b)).tolist()}],
          "outputs": [{"name": "y", "src": "mv"}]}
    text, info = emit(ir)
    (workdir / "ours.v").write_text(text)
    ours = synth_generic(workdir / "ours.v", info["top"], workdir / "ours_syn")["gates"]
    return {"alkaid_gates": alk, "chiplab_gates": ours, "alkaid_predict_bit_exact": a["predict_bit_exact"],
            "note": "alkaid ports differ (fixed-point packing); comparison of logic size only"}
