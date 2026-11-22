"""Async jobs for several agents at once: Huey (SQLite backend) with one queue per resource lane, plus a job table.

Lanes are sized to the machine (config.lanes()): cpu = cores - 1 (yosys, iverilog, verilator, ABC are single-
threaded, so batches fan out one job per worker), gpu = 1 (batched netlist simulation, training), docker = Docker
memory / 12 GB, 1..4 (LibreLane, Tiny Tapeout harden). Override with CHIPLAB_{CPU,GPU,DOCKER}_WORKERS. Start the
workers with `chiplab workers` (or `chiplab serve`, which starts them too). Each job gets its own row; results
are also cached by content (cache.py), so duplicate designs from different agents return instantly.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid

from huey import SqliteHuey

from chiplab import config

LANES = {k: v for k, v in config.lanes().items() if k in ("cpu", "gpu", "docker")}  # sized to this machine
_jobs_dir = config.home("jobs")
HUEY_CPU = SqliteHuey(name="chiplab-cpu", filename=str(_jobs_dir / "cpu.db"))
HUEY_GPU = SqliteHuey(name="chiplab-gpu", filename=str(_jobs_dir / "gpu.db"))
HUEY_DOCKER = SqliteHuey(name="chiplab-docker", filename=str(_jobs_dir / "docker.db"))
HUEYS = {"cpu": HUEY_CPU, "gpu": HUEY_GPU, "docker": HUEY_DOCKER}
MAX_ACTIVE_PER_SESSION = int(os.environ.get("CHIPLAB_MAX_ACTIVE", 500))


def _db() -> sqlite3.Connection:
    con = sqlite3.connect(str(_jobs_dir / "jobs.db"), timeout=60, isolation_level=None)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("""CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, session_id TEXT, run_id TEXT, tool TEXT,
                   args TEXT, lane TEXT, status TEXT, created REAL, started REAL, finished REAL, result TEXT,
                   error TEXT, huey_id TEXT)""")
    con.execute("CREATE INDEX IF NOT EXISTS jobs_session ON jobs(session_id, status)")
    return con


def _execute(job_id: str) -> str:
    from chiplab.tools import TOOLS
    import chiplab.tools_hw  # noqa: F401
    import chiplab.tools_jobs  # noqa: F401
    con = _db()
    row = con.execute("SELECT tool, args, status FROM jobs WHERE id=?", (job_id,)).fetchone()
    if row is None or row[2] == "cancelled":
        return "skipped"
    tool, args = row[0], json.loads(row[1])
    con.execute("UPDATE jobs SET status='running', started=? WHERE id=?", (time.time(), job_id))
    try:
        res = TOOLS[tool]["fn"](**args)
    except Exception as e:  # tools already catch; this is a last resort
        res = {"status": "error", "error": f"{type(e).__name__}: {e}"}
    con.execute("UPDATE jobs SET status=?, finished=?, result=?, error=? WHERE id=?",
                ({"ok": "done", "fail": "done", "timeout": "timeout"}.get(res.get("status"), "failed"), time.time(), json.dumps(res, default=str),
                 res.get("error"), job_id))
    con.close()
    return res.get("status", "ok")


run_cpu = HUEY_CPU.task(name="run_cpu")(_execute)
run_gpu = HUEY_GPU.task(name="run_gpu")(_execute)
run_docker = HUEY_DOCKER.task(name="run_docker")(_execute)
_RUNNERS = {"cpu": run_cpu, "gpu": run_gpu, "docker": run_docker}


def submit(tool: str, args: dict, session_id: str | None = None, lane: str | None = None) -> dict:
    from chiplab.tools import TOOLS
    import chiplab.tools_hw  # noqa: F401
    if tool not in TOOLS:
        raise ValueError(f"unknown tool {tool}")
    lane = lane or TOOLS[tool].get("lane", "cpu")
    if lane == "inline":
        lane = "cpu"
    con = _db()
    if session_id:
        active = con.execute("SELECT COUNT(*) FROM jobs WHERE session_id=? AND status IN ('queued','running')",
                             (session_id,)).fetchone()[0]
        if active >= MAX_ACTIVE_PER_SESSION:
            raise RuntimeError(f"session {session_id} has {active} active jobs (quota {MAX_ACTIVE_PER_SESSION})")
    jid = "j-" + uuid.uuid4().hex[:12]
    a = dict(args)
    if session_id:
        a.setdefault("session_id", session_id)
    con.execute("INSERT INTO jobs (id, session_id, run_id, tool, args, lane, status, created) VALUES (?,?,?,?,?,?,?,?)",
                (jid, session_id, a.get("run_id"), tool, json.dumps(a, default=str), lane, "queued", time.time()))
    r = _RUNNERS[lane](jid)
    con.execute("UPDATE jobs SET huey_id=? WHERE id=?", (getattr(r, "id", None), jid))
    con.close()
    return {"job_id": jid, "tool": tool, "lane": lane, "state": "queued"}


def status(job_id: str, with_result: bool = False) -> dict:
    con = _db()
    row = con.execute("SELECT id, session_id, tool, lane, status, created, started, finished, result, error FROM jobs WHERE id=?",
                      (job_id,)).fetchone()
    con.close()
    if row is None:
        raise KeyError(f"unknown job {job_id}")
    out = {"job_id": row[0], "session_id": row[1], "tool": row[2], "lane": row[3], "state": row[4],
           "queued_s": round((row[6] or time.time()) - row[5], 2),
           "run_s": round((row[7] or time.time()) - row[6], 2) if row[6] else None}
    if row[9]:
        out["error"] = row[9]
    if with_result and row[8]:
        out["result"] = json.loads(row[8])
    return out


def cancel(job_id: str) -> dict:
    con = _db()
    row = con.execute("SELECT status, lane, huey_id FROM jobs WHERE id=?", (job_id,)).fetchone()
    if row is None:
        raise KeyError(f"unknown job {job_id}")
    if row[0] == "queued":
        con.execute("UPDATE jobs SET status='cancelled', finished=? WHERE id=?", (time.time(), job_id))
        if row[2]:
            HUEYS[row[1]].revoke_by_id(row[2])
        state = "cancelled"
    else:
        state = row[0] + " (running jobs finish; nothing to cancel)" if row[0] == "running" else row[0]
    con.close()
    return {"job_id": job_id, "state": state}


def listing(session_id: str | None = None, limit: int = 100) -> list[dict]:
    con = _db()
    q = "SELECT id, session_id, tool, lane, status, created, finished FROM jobs"
    rows = con.execute(q + (" WHERE session_id=?" if session_id else "") + " ORDER BY created DESC LIMIT ?",
                       ((session_id, limit) if session_id else (limit,))).fetchall()
    con.close()
    return [{"job_id": r[0], "session_id": r[1], "tool": r[2], "lane": r[3], "state": r[4],
             "age_s": round(time.time() - r[5], 1)} for r in rows]


def lane_load() -> dict:
    con = _db()
    rows = con.execute("SELECT lane, status, COUNT(*) FROM jobs WHERE status IN ('queued','running') GROUP BY lane, status").fetchall()
    con.close()
    out = {l: {"workers": n, "queued": 0, "running": 0} for l, n in LANES.items()}
    for lane, st, n in rows:
        out.setdefault(lane, {"workers": 0, "queued": 0, "running": 0})[st] = n
    return out
