"""Formal check of the folded neuron against the lab's fully wired chip of the same integer model (SymbiYosys BMC).

The miter loads n symbolic activations (anyconst, so every input vector at once), starts the folded engine, and
asserts at `done` that its output equals the wired chip's output; it also asserts `done` arrives on time. From
reset, one decision is a fixed-length run, so a BMC to that depth is a complete proof of one decision for every
input. A proof for every later decision also needs an induction step (the controller returns to its idle state).

  python prove_proto.py --n 16 --wtype ternary --engine smtbmc-yices --timeout 300
"""
from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import time
from pathlib import Path

from folded_proto import folded_verilog, make_model

HERE = Path(__file__).resolve().parent


def descendants(pid: int) -> list[int]:
    out = subprocess.run(["pgrep", "-P", str(pid)], capture_output=True, text=True).stdout.split()
    kids = [int(k) for k in out]
    return kids + [d for k in kids for d in descendants(k)]


def kill_tree(pid: int) -> None:
    """Kill a running process, every descendant (found before any is killed) and their process groups. sby starts
    its engines in their own process groups, so killing sby's group alone leaves the solver running."""
    procs = [pid] + descendants(pid)
    for q in procs:
        for kill in (lambda x: os.killpg(os.getpgid(x), signal.SIGKILL), lambda x: os.kill(x, signal.SIGKILL)):
            try:
                kill(q)
            except (ProcessLookupError, PermissionError):
                pass


def miter(n: int, top_ref: str, ob: int, steps: int) -> str:
    aw = max(1, (n - 1).bit_length())
    return f"""module miter(input wire clk);
  (* anyconst *) wire [{4 * n - 1}:0] x;
  reg [15:0] t = 16'd0;
  always @(posedge clk) if (t != 16'hffff) t <= t + 16'd1;
  wire rst = (t == 16'd0);
  wire ld = (t >= 16'd1) && (t <= 16'd{n});
  wire [15:0] tm1 = t - 16'd1;
  wire [{aw - 1}:0] ld_addr = tm1[{aw - 1}:0];
  wire [3:0] ld_data = x[tm1[{aw - 1}:0] * 4 +: 4];
  wire start = (t == 16'd{n + 1});
  wire done;
  wire [{ob - 1}:0] y, yref;
  folded_neuron dut(.clk(clk), .rst(rst), .ld(ld), .ld_addr(ld_addr), .ld_data(ld_data), .start(start),
                    .done(done), .y(y));
  {top_ref} ref(.x(x), .y(yref));
  always @(*) begin
    if (t != 16'd0 && done) assert (y == yref);
    if (t == 16'd{n + steps + 2}) assert (done);
  end
endmodule
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=16)
    ap.add_argument("--p", type=int, default=1)
    ap.add_argument("--wtype", default="ternary")
    ap.add_argument("--engine", default="smtbmc yices")
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", default="")
    ap.add_argument("--work", default=str(HERE.parent / "work" / "prove"))
    ap.add_argument("--mutate", action="store_true", help="change one ROM weight: the check must then FAIL")
    a = ap.parse_args()
    from chiplab.config import oss_bin
    from chiplab.tools import TOOLS
    m = make_model(a.n, a.wtype, a.seed)
    c = TOOLS["compile_verilog"]["fn"](ir=m["ir"])
    ref_v = Path(c["files"][0])
    ob = max(1, m["amax"].bit_length())
    tag = f"{a.wtype}_n{a.n}_p{a.p}_{a.engine.replace(' ', '-')}{'_mut' if a.mutate else ''}"
    wd = Path(a.work) / tag
    wd.mkdir(parents=True, exist_ok=True)
    fm = {**m, "w": list(m["w"])}
    if a.mutate:
        fm["w"][a.n // 2] = 1 if fm["w"][a.n // 2] != 1 else -1
    (wd / "folded_neuron.v").write_text(folded_verilog(fm, a.n, a.p))
    (wd / "ref.v").write_text(ref_v.read_text())
    (wd / "miter.sv").write_text(miter(a.n, c["top"], ob, a.n // a.p))
    depth = a.n + a.n // a.p + 6
    (wd / "miter.sby").write_text(f"""[options]
mode bmc
depth {depth}

[engines]
{a.engine}

[script]
read_verilog -formal folded_neuron.v
read_verilog -formal ref.v
read_verilog -formal miter.sv
prep -top miter

[files]
folded_neuron.v
ref.v
miter.sv
""")
    t0 = time.time()
    env = {**os.environ, "PATH": str(Path(oss_bin("sby")).parent) + os.pathsep + os.environ.get("PATH", "")}
    with open(wd / "sby.out", "w") as log:
        p = subprocess.Popen([oss_bin("sby"), "-f", "miter.sby"], cwd=wd, stdout=log, stderr=subprocess.STDOUT,
                             env=env, start_new_session=True)
        try:
            p.wait(timeout=a.timeout)
            done = re.search(r"DONE \((\w+)", (wd / "sby.out").read_text())
            status = done.group(1) if done else "ERROR"
        except subprocess.TimeoutExpired:
            kill_tree(p.pid)
            p.wait()
            status = "TIMEOUT"
    res = {"n": a.n, "p": a.p, "wtype": a.wtype, "engine": a.engine, "mutated": a.mutate, "depth": depth, "status": status,
           "seconds": round(time.time() - t0, 1), "timeout_s": a.timeout}
    if a.out:
        Path(a.out).write_text(json.dumps(res, indent=1))
    print(json.dumps(res))


if __name__ == "__main__":
    main()
