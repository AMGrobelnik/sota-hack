"""Yosys runs: generic gates (count by type, depth, transistor estimate, netlist), LUT counts, Liberty mapping."""
from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path

from chiplab.config import oss_bin

SIMPLE_GATES = "AND,NAND,OR,NOR,XOR,XNOR,ANDNOT,ORNOT,MUX"
# ABC optimisation scripts. Yosys's default script (choice computation) can take >15 min on adder-heavy chips of
# ~5k cells; "fast" maps the same design in about a second at a few percent more gates.
ABC_SCRIPTS = {"fast": "+strash;dc2;map", "medium": "+strash;ifraig;scorr;dc2;dretime;strash;dc2;map",
               "high": None}  # None = Yosys default script


class SynthError(RuntimeError):
    pass


def run(script: str, workdir: Path, timeout: int = 900, name: str = "yosys") -> dict:
    workdir.mkdir(parents=True, exist_ok=True)
    ys = workdir / f"{name}.ys"
    ys.write_text(script)
    log = workdir / f"{name}.log"
    t0 = time.time()
    try:
        p = subprocess.run([oss_bin("yosys"), "-q", "-l", str(log), "-s", str(ys)], cwd=workdir,
                           capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise SynthError(f"{name}: timed out after {timeout}s (see {log})")
    if p.returncode != 0:
        tail = (p.stderr or "")[-1500:] + (log.read_text()[-1500:] if log.exists() else "")
        raise SynthError(f"{name}: yosys failed:\n{tail}")
    return {"seconds": round(time.time() - t0, 2), "log": str(log)}


def _stat_json(path: Path, top: str) -> dict:
    d = json.loads(path.read_text())
    mods = d.get("modules", {})
    m = mods.get(top) or mods.get("\\" + top) or (next(iter(mods.values())) if mods else {})
    cells = m.get("num_cells_by_type", {})
    return {"cells_by_type": {k: int(v) for k, v in cells.items()}, "num_cells": int(m.get("num_cells", sum(cells.values())))}


def abc_cmd(effort: str, lib: str) -> str:
    sc = ABC_SCRIPTS[effort]
    return f'abc {lib}' + (f' -script "{sc}"' if sc else "")


def synth_generic(rtl: Path, top: str, workdir: Path, gates: str = SIMPLE_GATES, effort: str = "fast", timeout: int = 900) -> dict:
    """Generic logic: cells by gate type, total gates, logic depth, CMOS transistor estimate, JSON + gate netlist."""
    script = f"""read_verilog {rtl}
hierarchy -check -top {top}
synth -top {top} -flatten -noabc
{abc_cmd(effort, "-g " + gates)}
opt_clean -purge
tee -q -o stat.json stat -json
tee -q -o stat_cmos.txt stat -tech cmos
tee -q -o ltp.txt ltp -noff
write_json net.json
write_verilog -noattr gates.v
"""
    r = run(script, workdir, timeout, "synth_generic")
    st = _stat_json(workdir / "stat.json", top)
    by = st["cells_by_type"]
    gates_total = sum(v for k, v in by.items() if k not in ("$_BUF_",))
    cm = re.search(r"(\d+)\s+transistors|transistors:\s*(\d+)", (workdir / "stat_cmos.txt").read_text())
    lt = re.search(r"length=(\d+)", (workdir / "ltp.txt").read_text())
    return {"gates": gates_total, "cells_by_type": by, "depth": int(lt.group(1)) if lt else None,
            "transistors_est": int(cm.group(1) or cm.group(2)) if cm else None,
            "netlist_json": str(workdir / "net.json"), "gate_verilog": str(workdir / "gates.v"),
            "seconds": r["seconds"], "tool": "yosys " + version(), "abc_effort": effort}


def count_luts(rtl: Path, top: str, workdir: Path, family: str = "xc7", timeout: int = 900) -> dict:
    """LUT counts: xc7 (6-input LUTs, Spartan-7 class) or ice40 (4-input LUTs, iCE40UP5K)."""
    if family == "xc7":
        cmd = f"synth_xilinx -family xc7 -flatten -top {top}"
    elif family == "ice40":
        cmd = f"synth_ice40 -device u -top {top}"
    else:
        raise ValueError("family must be xc7 or ice40")
    script = f"read_verilog {rtl}\nhierarchy -check -top {top}\n{cmd}\ntee -q -o stat_{family}.json stat -json\n"
    if family == "ice40":
        script += "write_json ice40.json\n"
    r = run(script, workdir, timeout, f"luts_{family}")
    by = _stat_json(workdir / f"stat_{family}.json", top)["cells_by_type"]
    if family == "xc7":
        luts = {k: v for k, v in by.items() if re.fullmatch(r"LUT\d", k)}
        return {"family": "xc7", "luts": sum(luts.values()), "by_size": luts, "carry4": by.get("CARRY4", 0),
                "muxf": by.get("MUXF7", 0) + by.get("MUXF8", 0), "ff": sum(v for k, v in by.items() if k.startswith("FD")),
                "dsp": by.get("DSP48E1", 0), "seconds": r["seconds"]}
    return {"family": "ice40", "luts": by.get("SB_LUT4", 0), "carry": by.get("SB_CARRY", 0),
            "ff": sum(v for k, v in by.items() if k.startswith("SB_DFF")), "seconds": r["seconds"],
            "json": str(workdir / "ice40.json")}


_VERSION = None


def version() -> str:
    global _VERSION
    if _VERSION is None:
        out = subprocess.run([oss_bin("yosys"), "-V"], capture_output=True, text=True).stdout
        m = re.search(r"Yosys (\S+)", out)
        _VERSION = m.group(1) if m else out.strip()
    return _VERSION
