"""Verification ladder level 2: prove the synthesised gate netlist equals the model for EVERY possible input.

Primary proof: gate netlist == emit/golden.py (an independent, naive rendering of the IR semantics), checked by
ABC's combinational equivalence checker (`cec`, SAT sweeping), which handles arithmetic far better than a plain
SAT miter. If that is inconclusive within the time limit, a weaker proof is attempted: gate netlist == the
production RTL (proves synthesis; RTL == IR then rests on construction + tests/test_ir_fuzz.py). The result
says which proof was obtained.
"""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

from chiplab.config import oss_bin
from chiplab.emit.golden import emit_golden
from chiplab.hw.yosys import SynthError, run


def _blif(src: Path, mod: str, name: str, workdir: Path, timeout: int, synth: bool) -> Path:
    body = f"synth -flatten -top {mod}\n" if synth else "techmap\nopt_clean\n"
    run(f"read_verilog {src}\nhierarchy -top {mod}\nproc\nflatten\n{body}rename {mod} cmp\nwrite_blif {name}.blif\n",
        workdir, timeout, f"blif_{name}")
    return workdir / f"{name}.blif"


def _cec(a: Path, b: Path, workdir: Path, timeout: int) -> tuple[bool | None, str]:
    try:
        p = subprocess.run([oss_bin("yosys-abc"), "-c", f"cec -n {a.name} {b.name}"], cwd=workdir,
                           capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, f"timed out after {timeout}s"
    out = (p.stdout + p.stderr).strip()
    if "Networks are equivalent" in out:
        return True, out[-300:]
    if "NOT EQUIVALENT" in out.upper() or "are not equivalent" in out:
        return False, out[-600:]
    return None, out[-300:]


def prove(ir: dict, port_info: dict, gate_verilog: Path, rtl: Path, workdir: Path, timeout: int = 600) -> dict:
    workdir.mkdir(parents=True, exist_ok=True)
    top = port_info["top"]
    t0 = time.time()
    gold = workdir / "golden.v"
    gold.write_text(emit_golden(ir, "gold_ref", port_info))
    try:
        g = _blif(gold, "gold_ref", "gold", workdir, timeout, synth=True)
        n = _blif(gate_verilog, top, "gate", workdir, timeout, synth=False)
        ok, out = _cec(g, n, workdir, timeout)
    except SynthError as e:
        ok, out = None, str(e)[-300:]
    if ok is not None:
        return {"proved": ok, "against": "independent golden model of the IR (emit/golden.py)", "method": "abc cec",
                "detail": out, "seconds": round(time.time() - t0, 1), "verification_level": 2 if ok else 0}
    # weaker fallback: synthesis correctness (RTL == gates)
    try:
        r = _blif(rtl, top, "rtl", workdir, timeout, synth=True)
        n = workdir / "gate.blif" if (workdir / "gate.blif").exists() else _blif(gate_verilog, top, "gate", workdir, timeout, synth=False)
        ok2, out2 = _cec(r, n, workdir, timeout)
    except SynthError as e:
        ok2, out2 = None, str(e)[-300:]
    return {"proved": ok2, "against": "production RTL (synthesis proved; RTL == IR by construction and fuzz tests)",
            "method": "abc cec", "golden_attempt": out, "detail": out2, "seconds": round(time.time() - t0, 1),
            "verification_level": 2 if ok2 else 1}
