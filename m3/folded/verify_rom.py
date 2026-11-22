"""Check that a synthesised ROM netlist still holds every word: simulate RTL and netlist side by side with Icarus
over the whole address range (the counter visits every address, so the check is exhaustive).

  python verify_rom.py work/rom_16k_ternary_sky130_w16 sky130
  python verify_rom.py work/rom_16k_ternary_generic_w16 generic
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from chiplab.config import oss_bin
from chiplab.hw.pdk import liberty


def models(kind: str) -> tuple[list[str], list[str]]:
    """Cell simulation models and defines for a netlist kind."""
    if kind == "generic":
        share = Path(oss_bin("yosys")).resolve().parent.parent / "share" / "yosys"
        return [str(share / "simcells.v")], []
    vdir = liberty(kind).parent.parent / "verilog"
    if kind == "sky130":
        return [str(vdir / "primitives.v"), str(vdir / "sky130_fd_sc_hd.v")], ["-DFUNCTIONAL", "-DUNIT_DELAY=#0"]
    return [str(vdir / "primitives.v"), str(vdir / "gf180mcu_fd_sc_mcu7t5v0.v")], ["-DFUNCTIONAL"]


def verify(wd: Path, kind: str) -> dict:
    rtl = (wd / "rom.v").read_text()
    word = int(re.search(r"output reg \[(\d+):0\] q", rtl).group(1)) + 1
    depth = len(re.findall(r"'d\d+: d =", rtl))
    net = (wd / ("gates.v" if kind == "generic" else f"mapped_{kind}.v")).read_text()
    net = re.sub(r"\bmodule\s+\\?rom_top\b", "module rom_net", net, count=1)
    (wd / "net_renamed.v").write_text(net)
    tb = f"""`timescale 1ns/1ps
module tb;
  reg clk = 0, rst = 1;
  wire [{word - 1}:0] qa, qb;
  integer i, bad = 0;
  rom_top a(.clk(clk), .rst(rst), .q(qa));
  rom_net b(.clk(clk), .rst(rst), .q(qb));
  always #5 clk = ~clk;
  initial begin
    @(posedge clk); @(posedge clk); #1 rst = 0;
    for (i = 0; i < {depth + 2}; i = i + 1) begin
      @(posedge clk); #1;
      if (qa !== qb) bad = bad + 1;
    end
    $display("CHECKED %0d MISMATCH %0d", {depth + 2}, bad);
    $finish;
  end
endmodule
"""
    (wd / "tb_rom.v").write_text(tb)
    files, defs = models(kind)
    exe = wd / "tb_rom.vvp"
    subprocess.run([oss_bin("iverilog"), "-g2012", *defs, "-o", str(exe), str(wd / "tb_rom.v"), str(wd / "rom.v"),
                    str(wd / "net_renamed.v"), *files], check=True, capture_output=True, text=True, timeout=1800)
    out = subprocess.run([oss_bin("vvp"), "-n", str(exe)], check=True, capture_output=True, text=True, timeout=1800).stdout
    m = re.search(r"CHECKED (\d+) MISMATCH (\d+)", out)
    return {"workdir": wd.name, "kind": kind, "cycles": int(m.group(1)), "mismatches": int(m.group(2)),
            "ok": int(m.group(2)) == 0}


if __name__ == "__main__":
    r = verify(Path(sys.argv[1]), sys.argv[2])
    print(r)
    sys.exit(0 if r["ok"] else 1)
