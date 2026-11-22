"""Does a timed-out lab Yosys run leave its ABC child running? (observation for RESULTS.md)

Uses the lab's own count_luts (hw.yosys.count_luts, xc7: Yosys synth_xilinx, whose ABC step runs for minutes on a
1k-weight 4-bit chip). Run 1, no cap: records when the step's yosys-abc process (started by Yosys as
`sh -c yosys-abc ...`, working in the step's folder) appears and ends. Run 2: the same call with the lab's timeout
set to the middle of that ABC window. After the lab reports the timeout, it lists yosys-abc processes of that
folder with no yosys left among their ancestors, records them and kills them. Run it with PYTHONPATH pointing at a
patched copy of the lab to check the proposed fix (it must leave none). Lab home: CHIPLAB_HOME (a scratch home).

Usage: python orphan_check.py <model json> [--cap S]   (--cap skips run 1)
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import threading
import time
from pathlib import Path

from chiplab.cli import _tools
from chiplab.hw import yosys


def _cwd(pid: int | str) -> str:
    return subprocess.run(["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"], capture_output=True, text=True,
                          timeout=10).stdout


def abc_orphans(workdir: Path) -> list[dict]:
    """yosys-abc processes working in `workdir` whose parent is gone: the parent is pid 1, or only `sh` wrappers sit
    between it and pid 1 (Yosys starts ABC as `sh -c yosys-abc ...`). Returns abc pid + wrapper pids, nothing else:
    a yosys-abc started directly by a live Python process (the formal check's cec / iprove) is not an orphan."""
    out = subprocess.run(["ps", "-Ao", "pid=,ppid=,etime=,command="], capture_output=True, text=True, timeout=30).stdout
    procs = {}
    for ln in out.splitlines():
        p = ln.split(None, 3)
        if len(p) == 4:
            procs[int(p[0])] = (int(p[1]), p[2], p[3])
    found = []
    for pid, (ppid, et, cmd) in procs.items():
        if Path(cmd.split()[0]).name != "yosys-abc":
            continue
        chain, cur = [pid], ppid
        while cur in procs and cur != 1 and Path(procs[cur][2].split()[0]).name == "sh":
            chain.append(cur)
            cur = procs[cur][0]
        if cur == 1 and str(workdir) in _cwd(pid):
            found.append({"pids": chain, "etime": et, "cmd": cmd.split()[0].rsplit("/", 1)[-1] + " " +
                          " ".join(cmd.split()[1:3])})
    return found


def abc_window(workdir: Path, run) -> tuple[float, float, float]:
    """Run `run()` in a thread; return (seconds until our yosys-abc appeared, until it ended, total)."""
    th = threading.Thread(target=run, daemon=True)
    t0 = time.time()
    th.start()
    start = end = None
    while th.is_alive():
        pids = subprocess.run(["pgrep", "-f", "libexec/yosys-abc"], capture_output=True, text=True, timeout=30).stdout
        here = any(str(workdir) in _cwd(p) for p in pids.split())
        if here and start is None:
            start = time.time() - t0
        if start is not None and not here and end is None:
            end = time.time() - t0
        time.sleep(0.5)
    total = time.time() - t0
    return start or 0.0, end or total, total


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("model", type=Path)
    ap.add_argument("--cap", type=int, default=0)
    a = ap.parse_args()
    tools = _tools()
    d = json.loads(a.model.read_text())
    r = tools["ingest_model"]["fn"](format="intnn", model=d["model"], name=d["meta"]["name"])
    from chiplab import config
    dd = config.HOME / "designs" / r["design_id"]
    out = {"design_id": r["design_id"], "lab_has_group_kill": hasattr(yosys, "kill_group"), "step": "count_luts xc7"}
    cap = a.cap
    if not cap:
        w1 = dd / f"orphan_full_{int(time.time())}"
        s, e, tot = abc_window(w1, lambda: yosys.count_luts(dd / "design.v", r["top"], w1, "xc7", 3600))
        out["uncapped"] = {"abc_start_s": round(s, 1), "abc_end_s": round(e, 1), "total_s": round(tot, 1)}
        cap = max(1, int((s + e) / 2))
    out["cap_s"] = cap
    wd = dd / f"orphan_cap{cap}_{int(time.time())}"
    t0 = time.time()
    try:
        yosys.count_luts(dd / "design.v", r["top"], wd, "xc7", cap)
        out.update(timed_out=False, seconds=round(time.time() - t0, 1))
    except yosys.SynthError as e:
        out.update(timed_out="timed out" in str(e), seconds=round(time.time() - t0, 1))
        time.sleep(2)
        orph = abc_orphans(wd)
        out["orphans_after_2s"] = orph
        for o in orph:
            for pid in o["pids"]:
                os.kill(pid, signal.SIGKILL)
        out["killed_by_check"] = [p for o in orph for p in o["pids"]]
    print(json.dumps(out))


if __name__ == "__main__":
    main()
