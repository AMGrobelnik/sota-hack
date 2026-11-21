"""Sequential equivalence (ladder level 2 for clocked designs, e.g. the streaming wrapper): RTL vs its own
synthesised gate netlist with YosysHQ eqy (partitions by matched registers, proves each partition with sby)."""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

from chiplab.config import oss_bin
from chiplab.hw.yosys import SIMPLE_GATES, run


def synth_seq_netlist(rtl_files: list[Path], top: str, workdir: Path, timeout: int = 900) -> Path:
    reads = "\n".join(f"read_verilog {Path(f).resolve()}" for f in rtl_files)
    run(f"{reads}\nhierarchy -check -top {top}\nsynth -top {top} -flatten -noabc\n"
        f"abc -g {SIMPLE_GATES} -script \"+strash;dc2;map\"\nopt_clean -purge\nwrite_verilog -noattr gate_seq.v\n",
        workdir, timeout, "synth_seq")
    return workdir / "gate_seq.v"


def prove_sequential(rtl_files: list[Path], top: str, workdir: Path, gate_verilog: Path | None = None,
                     depth: int = 8, timeout: int = 900) -> dict:
    t0 = time.time()
    wd = Path(workdir); wd.mkdir(parents=True, exist_ok=True)
    gate = Path(gate_verilog) if gate_verilog else synth_seq_netlist(rtl_files, top, wd, timeout)
    gold_reads = "\n".join(f"read_verilog {Path(f).resolve()}" for f in rtl_files)
    (wd / "chip.eqy").write_text(f"""[gold]
{gold_reads}
prep -top {top}
flatten

[gate]
read_verilog {gate.resolve()}
prep -top {top}

[collect *]

[strategy sby]
use sby
depth {depth}
engine smtbmc yices
""")
    out = wd / "eqy_out"
    try:
        p = subprocess.run([oss_bin("eqy"), "-f", "chip.eqy", "-d", str(out), "-j", "4"], cwd=wd,
                           capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"proved": None, "method": "eqy", "error": f"timed out after {timeout}s", "seconds": round(time.time() - t0, 1)}
    log = p.stdout + p.stderr
    (wd / "eqy.log").write_text(log)
    proved = p.returncode == 0 and "Successfully proved designs equivalent" in log
    failed = "Failed to prove equivalence" in log or "FAIL" in log
    return {"proved": True if proved else (False if failed else None), "method": "eqy (sby, smtbmc yices)",
            "depth": depth, "gate_netlist": str(gate), "detail": log[-600:], "seconds": round(time.time() - t0, 1),
            "verification_level": 2 if proved else 1}
