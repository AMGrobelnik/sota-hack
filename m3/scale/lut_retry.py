"""Retry the xc7 LUT counts that hit count-luts' fixed 900 s cap, with a longer cap, through submit-batch.

count_luts has no timeout argument; synthesize(target="xc7", timeout=N) runs the same Yosys synth_xilinx flow with
a chosen cap. Jobs go to the sweep's running workers (same lab home). Polls until all are done and writes one record
per design: luts, carry4, muxf, seconds, or the error with its tail.

Usage: python lut_retry.py --designs <id,id,...> --timeout 3600 --out lut_retry.json
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from chiplab.cli import _tools

TOOLS = _tools()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--designs", required=True)
    ap.add_argument("--timeout", type=int, default=3600)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    from chiplab.jobs import queue
    ids = a.designs.split(",")
    r = TOOLS["submit_batch"]["fn"](tool="synthesize", args_list=[{"design_id": d, "target": "xc7", "timeout": a.timeout}
                                                                  for d in ids])
    jobs, out = dict(zip(r["job_ids"], ids)), {}
    while len(out) < len(jobs):
        for j, d in jobs.items():
            if d in out:
                continue
            st = queue.status(j, with_result=True)
            if st["state"] in ("done", "failed", "timeout", "cancelled"):
                res = st.get("result") or {}
                m = res.get("metrics") or {}
                out[d] = {"state": st["state"], "status": res.get("status"), "cap_s": a.timeout,
                          "run_s": st.get("run_s"), "wall_s": (res.get("cost") or {}).get("wall_s"),
                          "luts": m.get("luts"), "carry4": m.get("carry4"), "muxf": m.get("muxf"),
                          "yosys_s": m.get("seconds"), "error": str(res.get("error") or "")[-600:] or None}
                a.out.write_text(json.dumps(out, indent=1))
                print(json.dumps({d: out[d]["status"]}), flush=True)
        time.sleep(5)


if __name__ == "__main__":
    main()
