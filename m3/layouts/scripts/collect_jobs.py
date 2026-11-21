"""Collect finished `layout` jobs from the lab's docker lane into raw/<name>_<pdk>_<tag>.json.

Usage: python collect_jobs.py <worktree root> <tag> <note> <name>=<job_id> [...]
Prints the job states; writes a raw file only for a job that has finished (ok or error).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
TAG, NOTE = sys.argv[2], sys.argv[3]
PAIRS = [a.split("=", 1) for a in sys.argv[4:]]
RAW = ROOT / "m3" / "layouts" / "raw"
CLI = str(ROOT / "chiplab" / ".venv" / "bin" / "chiplab")


def cli(tool: str, args: dict) -> dict:
    p = subprocess.run([CLI, tool, "--json", json.dumps(args)], capture_output=True, text=True, timeout=60,
                       cwd=str(ROOT / "chiplab"))
    return json.loads(p.stdout)


def main() -> None:
    for name, job in PAIRS:
        st = cli("job-status", {"job_id": job})
        state = st.get("state")
        print(json.dumps({"name": name, "job": job, "state": state, "run_s": st.get("run_s")}), flush=True)
        if state in ("queued", "running", None):
            continue
        res = cli("job-result", {"job_id": job})
        r = res.get("result", res)
        gds = r.get("gds")
        mj = Path(gds).parent.parent / "metrics.json" if gds else None
        metrics = json.loads(mj.read_text()) if mj and mj.exists() else {}
        out = {"name": name, "tag": TAG, "note": NOTE, "job_id": job, "status": st, "result": r,
               "metrics_full": metrics}
        (RAW / f"{name}_{TAG}.json").write_text(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
