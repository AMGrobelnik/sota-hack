"""The run log: every tool call, append-only. It is the leaderboard, the built-today evidence, the source of the
front end's visuals (candidate dots, stage changes) and future fine-tuning data."""
from __future__ import annotations

import hashlib
import json
import subprocess
import time
from pathlib import Path

from chiplab import config

CORE_DIRS = ("ir", "emit", "verify", "referee", "data", "hw", "train")


def _hash_files(paths) -> str:
    h = hashlib.sha256()
    for p in sorted(paths):
        h.update(str(p.relative_to(config.PKG_DIR)).encode())
        h.update(p.read_bytes())
    return h.hexdigest()[:12]


_CORE = None


def core_hash() -> str:
    """Hash of the lab's fixed core (IR, emitter, verification, referee, data/splits, hardware, engine)."""
    global _CORE
    if _CORE is None:
        _CORE = _hash_files([p for d in CORE_DIRS for p in (config.PKG_DIR / d).rglob("*.py")]
                            + list((config.PKG_DIR / "referee").glob("*.yaml")))
    return _CORE


def git_rev() -> str:
    try:
        rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=config.PROJECT_DIR, capture_output=True,
                             text=True, timeout=5).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--", "."], cwd=config.PROJECT_DIR,
                               capture_output=True, text=True, timeout=5).stdout.strip()
        return rev + ("+dirty" if dirty else "")
    except Exception:
        return "unknown"


def _append(name: str, rec: dict) -> None:
    path = config.home() / name
    with open(path, "a") as f:
        f.write(json.dumps(rec, default=str) + "\n")


def log_call(tool: str, args: dict, result: dict, wall_s: float, **extra) -> dict:
    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "tool": tool, "args": args, "git_rev": git_rev(),
           "core_hash": core_hash(), "status": result.get("status", "ok"), "wall_s": round(wall_s, 3)}
    for k in ("task_id", "split_hash", "view_id", "batch_id", "design_id", "data_kind", "hw_kind",
              "verification_level", "metrics", "files", "cost"):
        if k in result:
            rec[k] = result[k]
    rec.update(extra)
    _append("log.jsonl", rec)
    return rec


def event(kind: str, **fields) -> None:
    """A small event for the front end (stage change, candidate dot, check result)."""
    _append("events.jsonl", {"ts": time.time(), "kind": kind, **fields})


def read(name: str = "log.jsonl", since: float | None = None) -> list[dict]:
    path = config.home() / name
    if not path.exists():
        return []
    out = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    if since is not None:
        out = [r for r in out if r.get("ts", 0) >= since] if name == "events.jsonl" else out
    return out
