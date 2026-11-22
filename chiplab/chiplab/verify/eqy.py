"""Sequential equivalence (ladder level 2 for clocked designs, e.g. the streaming wrapper): RTL vs its own
synthesised gate netlist with YosysHQ eqy (partitions by matched registers, proves each partition with sby)."""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

from chiplab.config import oss_bin
from chiplab.hw.yosys import SIMPLE_GATES, run


def _kill_group(p: subprocess.Popen) -> None:
    """Kill a process started with start_new_session=True together with every child it spawned."""
    import os
    import signal
    try:
        os.killpg(p.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    p.communicate()


def synth_seq_netlist(rtl_files: list[Path], top: str, workdir: Path, timeout: int = 900, blackbox: list[str] | None = None) -> Path:
    reads = "\n".join(f"read_verilog {Path(f).resolve()}" for f in rtl_files)
    bb = "".join(f"blackbox {m}\n" for m in (blackbox or []))
    if blackbox:  # keep the names of wires at black-box ports so eqy can pair gold and gate cut points
        cells = " ".join(f"t:{m}" for m in blackbox)
        bb += f"hierarchy -top {top}\nselect -set bbw {cells} %x:+[*] w:* %i\nsetattr -set keep 1 @bbw\n"
    run(f"{reads}\n{bb}hierarchy -check -top {top}\nsynth -top {top} -flatten -noabc\n"
        f"abc -g {SIMPLE_GATES} -script \"+strash;dc2;map\"\nopt_clean -purge\nwrite_verilog -noattr gate_seq.v\n",
        workdir, timeout, "synth_seq")
    return workdir / "gate_seq.v"


def prove_sequential(rtl_files: list[Path], top: str, workdir: Path, gate_verilog: Path | None = None,
                     depth: int = 8, timeout: int = 900, blackbox: list[str] | None = None,
                     blackbox_sources: list[Path] | None = None) -> dict:
    """blackbox: modules treated as uninterpreted on both sides (e.g. the combinational core, which is proven
    separately by the combinational equivalence check). This keeps eqy's job to the clocked wrapper, whose size
    does not grow with the model, so the proof stays fast for large chips (compositional proof)."""
    t0 = time.time()
    wd = Path(workdir); wd.mkdir(parents=True, exist_ok=True)
    gate = Path(gate_verilog) if gate_verilog else synth_seq_netlist(rtl_files, top, wd, timeout, blackbox)
    gold_reads = "\n".join(f"read_verilog {Path(f).resolve()}" for f in rtl_files)
    bb = "".join(f"blackbox {m}\n" for m in (blackbox or []))
    # the written gate netlist omits black-boxed module definitions: declare them from their own source (ports only)
    gate_reads = f"read_verilog {gate.resolve()}\n" + "".join(f"read_verilog -lib {Path(f).resolve()}\n" for f in (blackbox_sources or []))
    (wd / "chip.eqy").write_text(f"""[gold]
{gold_reads}
{bb}prep -top {top}
flatten
{"opt_clean -purge" if blackbox else ""}

[gate]
{gate_reads}{bb}prep -top {top}

[collect *]

[strategy sby]
use sby
depth {depth}
engine smtbmc yices
""")
    out = wd / "eqy_out"
    # own process group, killed whole on timeout: eqy's sby/yosys/solver children must not outlive the cap
    p = subprocess.Popen([oss_bin("eqy"), "-f", "chip.eqy", "-d", str(out), "-j", "4"], cwd=wd,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        stdout, stderr = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_group(p)
        return {"proved": None, "method": "eqy", "error": f"timed out after {timeout}s", "seconds": round(time.time() - t0, 1),
                "blackboxed": blackbox or []}
    log = stdout + stderr
    (wd / "eqy.log").write_text(log)
    proved = p.returncode == 0 and "Successfully proved designs equivalent" in log
    failed = "Failed to prove equivalence" in log or "FAIL" in log
    return {"proved": True if proved else (False if failed else None), "method": "eqy (sby, smtbmc yices)",
            "blackboxed": blackbox or [], "scope": ("clocked wrapper with the combinational core as a black box; the core is "
                                                   "proven by the combinational equivalence check") if blackbox else "whole design",
            "depth": depth, "gate_netlist": str(gate), "detail": log[-600:], "seconds": round(time.time() - t0, 1),
            "verification_level": 2 if proved else 1}
