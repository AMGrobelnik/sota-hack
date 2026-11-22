"""Measure gates and area per stored bit of a synthesised constant ROM (case statement read by an address counter).

Each job synthesises one ROM with the chip lab's own Yosys flows: `chiplab.hw.yosys.synth_generic` (generic
gates) and `chiplab.hw.pdk.map_to_process` (sky130 / gf180 standard cells, same script as the lab's
`map-to-process` tool). Every job runs in its own process group under `memgate run` with a hard time cap; on a
timeout the whole group is killed.

  python rom_bench.py run --out results/rom.json --workers 4 --cap 1800
  python rom_bench.py job --size-kbit 16 --stats ternary --target sky130 --word 16 --workdir work/x
"""
from __future__ import annotations

import argparse
import json
import os
import random
import signal
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
TERNARY_CODE = {0: 0b00, 1: 0b01, -1: 0b11}   # 2 bits per weight: sign-magnitude, 10 unused


def weights(stats: str, n: int, seed: int) -> list[int]:
    """Realistic weight statistics: ternary with about 50% zeros (25% +1, 25% -1), or uniform signed 4-bit."""
    rng = random.Random(seed)
    if stats == "ternary":
        return [rng.choices([0, 1, -1], weights=[0.5, 0.25, 0.25])[0] for _ in range(n)]
    if stats == "uniform4":
        return [rng.randrange(-8, 8) for _ in range(n)]
    raise ValueError(stats)


def pack(stats: str, ws: list[int], word: int) -> list[int]:
    """Pack weights little-endian into words: weight i of a word sits at bits [i*b, i*b + b)."""
    b = 2 if stats == "ternary" else 4
    per = word // b
    out = []
    for i in range(0, len(ws), per):
        v = 0
        for j, w in enumerate(ws[i:i + per]):
            v |= (TERNARY_CODE[w] if stats == "ternary" else (w & 0xF)) << (j * b)
        out.append(v)
    return out


def rom_verilog(words: list[int], word: int, top: str = "rom_top") -> str:
    """A constant ROM as a case statement, read by a free-running address counter; output registered."""
    depth = len(words)
    a = max(1, (depth - 1).bit_length())
    hexw = (word + 3) // 4
    lines = [f"module {top}(input wire clk, input wire rst, output reg [{word - 1}:0] q);",
             f"  reg [{a - 1}:0] addr;", f"  reg [{word - 1}:0] d;",
             "  always @(posedge clk) if (rst) addr <= 0; else addr <= addr + 1'b1;",
             "  always @(*) begin", "    case (addr)"]
    lines += [f"      {a}'d{i}: d = {word}'h{w:0{hexw}x};" for i, w in enumerate(words)]
    lines += [f"      default: d = {word}'h0;", "    endcase", "  end",
              "  always @(posedge clk) q <= d;", "endmodule", ""]
    return "\n".join(lines)


def job(size_kbit: int, stats: str, target: str, word: int, workdir: Path, seed: int) -> dict:
    from chiplab.hw.pdk import map_to_process
    from chiplab.hw.yosys import synth_generic, version
    bits = size_kbit * 1024
    b = 2 if stats == "ternary" else 4
    ws = weights(stats, bits // b, seed)
    words = pack(stats, ws, word)
    workdir.mkdir(parents=True, exist_ok=True)
    rtl = workdir / "rom.v"
    rtl.write_text(rom_verilog(words, word))
    t0 = time.time()
    if target == "generic":
        r = synth_generic(rtl, "rom_top", workdir, timeout=10 ** 6)
        res = {"gates": r["gates"], "cells_by_type": r["cells_by_type"], "depth": r["depth"]}
    else:
        r = map_to_process(rtl, "rom_top", workdir, target, timeout=10 ** 6)
        res = {k: r[k] for k in ("area_um2", "gate_equivalents", "std_cells", "cells_by_type", "nand2_um2")}
    zeros = sum(1 for w in ws if w == 0) / len(ws)
    return {"size_kbit": size_kbit, "stored_bits": bits, "stats": stats, "target": target, "word_bits": word,
            "rom_depth": len(words), "weights": len(ws), "bits_per_weight": b, "zero_fraction": round(zeros, 4),
            "seed": seed, "yosys": version(), "abc_effort": "fast", "seconds": round(time.time() - t0, 1), **res}


def plan(sizes: list[int], words: list[int]) -> list[dict]:
    """Largest first, so the long synthesis starts first."""
    out = [{"size_kbit": s, "stats": st, "target": t, "word": w}
           for s in sorted(sizes, reverse=True) for w in words for st in ("ternary", "uniform4")
           for t in ("sky130", "gf180", "generic")]
    return out


def run_one(spec: dict, args: argparse.Namespace, env: dict) -> dict:
    name = f"rom_{spec['size_kbit']}k_{spec['stats']}_{spec['target']}_w{spec['word']}"
    wd = Path(args.work) / name
    wd.mkdir(parents=True, exist_ok=True)
    out = wd / "result.json"
    cmd = ["memgate", "run", "--need-gb", str(args.need_gb), "--label", name, "--",
           sys.executable, str(Path(__file__).resolve()), "job", "--size-kbit", str(spec["size_kbit"]),
           "--stats", spec["stats"], "--target", spec["target"], "--word", str(spec["word"]),
           "--workdir", str(wd), "--seed", str(args.seed), "--out", str(out)]
    t0 = time.time()
    with open(wd / "job.log", "w") as log:
        p = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, env=env, start_new_session=True)
        try:
            rc = p.wait(timeout=args.cap)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGKILL)
            p.wait()
            return {**spec, "status": "timeout", "cap_s": args.cap, "seconds": round(time.time() - t0, 1)}
    if rc != 0 or not out.exists():
        tail = (wd / "job.log").read_text()[-600:]
        return {**spec, "status": "failed", "rc": rc, "log_tail": tail, "seconds": round(time.time() - t0, 1)}
    return {"status": "ok", **json.loads(out.read_text())}


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    j = sub.add_parser("job")
    j.add_argument("--size-kbit", type=int, required=True)
    j.add_argument("--stats", choices=["ternary", "uniform4"], required=True)
    j.add_argument("--target", choices=["generic", "sky130", "gf180"], required=True)
    j.add_argument("--word", type=int, default=16)
    j.add_argument("--workdir", required=True)
    j.add_argument("--seed", type=int, default=1)
    j.add_argument("--out", required=True)
    r = sub.add_parser("run")
    r.add_argument("--out", default=str(HERE / "results" / "rom.json"))
    r.add_argument("--work", default=str(HERE / "work"))
    r.add_argument("--sizes", default="128,64,16")
    r.add_argument("--words", default="16")
    r.add_argument("--workers", type=int, default=4)
    r.add_argument("--cap", type=int, default=1800)
    r.add_argument("--need-gb", type=int, default=6)
    r.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    if a.cmd == "job":
        res = job(a.size_kbit, a.stats, a.target, a.word, Path(a.workdir), a.seed)
        Path(a.out).write_text(json.dumps(res, indent=1))
        print(json.dumps({k: v for k, v in res.items() if k != "cells_by_type"}))
        return
    specs = plan([int(s) for s in a.sizes.split(",")], [int(w) for w in a.words.split(",")])
    env = dict(os.environ)
    results: list[dict] = []
    outp = Path(a.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(a.workers) as ex:
        futs = [ex.submit(run_one, s, a, env) for s in specs]
        for f in as_completed(futs):
            res = f.result()
            results.append(res)
            print(json.dumps({k: v for k, v in res.items() if k not in ("cells_by_type", "log_tail")}), flush=True)
            outp.write_text(json.dumps(results, indent=1))
    print("DONE", len(results), flush=True)


if __name__ == "__main__":
    main()
