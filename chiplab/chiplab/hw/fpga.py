"""iCE40 UP5K bitstream (UPduino-class board, $36): Yosys synth_ice40 -> nextpnr-ice40 -> icepack, plus icetime.
Wraps the OSS CAD Suite tools; nothing reimplemented."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from pathlib import Path

from chiplab.config import oss_bin
from chiplab.hw.yosys import run as yosys_run


class FpgaError(RuntimeError):
    pass


def board_top_for_tt(tt_top: str, name: str = "chipin_fpga") -> tuple[str, str]:
    """A board-level top around a Tiny Tapeout module: only clk, rst_n, ui_in[7:0], uo_out[7:0] reach pins
    (18 I/O, fits the sg48 package); the bidirectional bank is tied off."""
    v = f"""`default_nettype none
// chipin.space chip lab: iCE40 board top around {tt_top}. Generated; do not edit.
module {name} (input wire clk, input wire rst_n, input wire [7:0] ui_in, output wire [7:0] uo_out);
  wire [7:0] uio_out, uio_oe;
  {tt_top} chip (.ui_in(ui_in), .uo_out(uo_out), .uio_in(8'd0), .uio_out(uio_out), .uio_oe(uio_oe),
                 .ena(1'b1), .clk(clk), .rst_n(rst_n));
endmodule
"""
    return v, name


def ice40_bitstream(rtl_files: list[Path], top: str, workdir: Path, pcf: Path | None = None, device: str = "up5k",
                    package: str = "sg48", freq_mhz: float = 12.0, seed: int = 1, timeout: int = 1800) -> dict:
    t0 = time.time()
    wd = Path(workdir); wd.mkdir(parents=True, exist_ok=True)
    reads = "\n".join(f"read_verilog {Path(f).resolve()}" for f in rtl_files)
    yosys_run(f"{reads}\nhierarchy -check -top {top}\nsynth_ice40 -device u -top {top} -json {wd / 'ice40.json'}\n"
              f"tee -q -o {wd / 'stat_ice40.json'} stat -json\n", wd, timeout, "synth_ice40")
    cmd = [oss_bin("nextpnr-ice40"), f"--{device}", "--package", package, "--json", str(wd / "ice40.json"),
           "--asc", str(wd / "chip.asc"), "--report", str(wd / "pnr.json"), "--freq", str(freq_mhz), "--seed", str(seed)]
    cmd += ["--pcf", str(pcf)] if pcf else ["--pcf-allow-unconstrained"]
    try:
        p = subprocess.run(cmd, cwd=wd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise FpgaError(f"nextpnr timed out after {timeout}s")
    (wd / "nextpnr.log").write_text(p.stdout + p.stderr)
    if p.returncode != 0:
        raise FpgaError("nextpnr-ice40 failed:\n" + (p.stdout + p.stderr)[-2000:])
    q = subprocess.run([oss_bin("icepack"), str(wd / "chip.asc"), str(wd / "chip.bin")], capture_output=True, text=True, timeout=300)
    if q.returncode != 0:
        raise FpgaError("icepack failed:\n" + q.stderr[-1000:])
    t = subprocess.run([oss_bin("icetime"), "-d", device, "-mt", "-c", str(freq_mhz), str(wd / "chip.asc")], capture_output=True, text=True, timeout=600)
    (wd / "icetime.log").write_text(t.stdout + t.stderr)
    rep = json.loads((wd / "pnr.json").read_text()) if (wd / "pnr.json").exists() else {}
    util = rep.get("utilization", {})
    fmax = {k: round(v.get("achieved", 0), 2) for k, v in rep.get("fmax", {}).items()}
    tm = re.search(r"Total path delay:\s*([\d.]+)\s*ns\s*\(([\d.]+)\s*MHz\)", t.stdout)
    used = lambda k: util.get(k, {}).get("used")
    avail = lambda k: util.get(k, {}).get("available")
    return {"device": f"iCE40{device.upper()}", "package": package, "bin": str(wd / "chip.bin"),
            "luts": used("ICESTORM_LC"), "luts_available": avail("ICESTORM_LC"), "io_used": used("SB_IO"),
            "io_available": avail("SB_IO"), "ram": used("ICESTORM_RAM"), "dsp": used("ICESTORM_DSP"),
            "fmax_mhz": fmax, "target_mhz": freq_mhz,
            "icetime_path_ns": float(tm.group(1)) if tm else None, "icetime_mhz": float(tm.group(2)) if tm else None,
            "bin_bytes": (wd / "chip.bin").stat().st_size, "seconds": round(time.time() - t0, 1),
            "note": "logic cells (ICESTORM_LC) = 4-input LUT + flip-flop pairs after placement"}
