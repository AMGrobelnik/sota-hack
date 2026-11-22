"""Place and route one constant ROM with the lab's LibreLane wrapper (needs Docker; not run on the night of
22 Nov 2026 because the Docker engine was stopped on purpose). Answers: does a 128 kbit case-statement ROM route,
and what is its placed area and leakage, against the synthesis area in results/rom.json.

  LAB_HOME=<lab install> bash m3/folded/run.sh layout_rom.py --size-kbit 128 --stats uniform4 --pdk sky130
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from rom_bench import pack, rom_verilog, weights

HERE = Path(__file__).resolve().parent


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--size-kbit", type=int, default=128)
    ap.add_argument("--stats", choices=["ternary", "uniform4"], default="uniform4")
    ap.add_argument("--word", type=int, default=16)
    ap.add_argument("--pdk", default="sky130")
    ap.add_argument("--clock-ns", type=float, default=1000.0)     # 1 MHz
    ap.add_argument("--core-util", type=int, default=40)
    ap.add_argument("--timeout", type=int, default=14400)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    from chiplab.hw.librelane import timing_power_layout
    name = f"layout_{a.size_kbit}k_{a.stats}_w{a.word}_{a.pdk}"
    wd = HERE / "work" / name
    wd.mkdir(parents=True, exist_ok=True)
    b = 2 if a.stats == "ternary" else 4
    rtl = wd / "rom.v"
    rtl.write_text(rom_verilog(pack(a.stats, weights(a.stats, a.size_kbit * 1024 // b, a.seed), a.word), a.word))
    r = timing_power_layout([rtl], "rom_top", wd / "librelane", a.pdk, clock_period_ns=a.clock_ns,
                            clock_port="clk", core_util=a.core_util, timeout=a.timeout, tag=name)
    out = HERE / "results" / f"{name}.json"
    out.write_text(json.dumps({"args": vars(a), **{k: v for k, v in r.items() if k != "metrics"},
                               "metrics": r.get("metrics")}, indent=1, default=str))
    print(out)


if __name__ == "__main__":
    main()
