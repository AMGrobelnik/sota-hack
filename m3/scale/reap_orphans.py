"""Stopgap until the proposed patch lands: find and kill yosys-abc processes a timed-out lab step left behind.

Every --every seconds, lists yosys-abc processes working inside --home with no yosys left among their ancestors
(orphan_check.abc_orphans), logs each one as a JSON line (pids, elapsed, CPU time) and kills it with its sh wrapper.
Stops when the process --until-pid exits (the sweep), then makes one last pass.

Usage: python reap_orphans.py --home <lab home> --until-pid <pid> [--every 15]
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import time
from pathlib import Path

from orphan_check import abc_orphans


def cpu_time(pid: int) -> str:
    return subprocess.run(["ps", "-o", "time=", "-p", str(pid)], capture_output=True, text=True, timeout=10).stdout.strip()


def sweep_once(home: Path) -> None:
    for o in abc_orphans(home):
        rec = {"t": time.strftime("%H:%M:%S"), **o, "cpu_time": cpu_time(o["pids"][0])}
        for pid in o["pids"]:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        print(json.dumps(rec), flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--home", type=Path, required=True)
    ap.add_argument("--until-pid", type=int, required=True)
    ap.add_argument("--every", type=float, default=15.0)
    a = ap.parse_args()
    while True:
        alive = subprocess.run(["ps", "-p", str(a.until_pid)], capture_output=True, timeout=10).returncode == 0
        sweep_once(a.home)
        if not alive:
            break
        time.sleep(a.every)


if __name__ == "__main__":
    main()
