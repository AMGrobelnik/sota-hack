"""Run the eight P2 layouts in parallel through the lab's own `chiplab layout` CLI (LibreLane in Docker).

Each run is one `chiplab layout` process (through layout_cli.py, the CLI with the gf180 liberty fix) (its own work folder: runs/designs/<id>/layout_<pdk>), at most
WORKERS at once (one per 12 GB of Docker engine memory). A failed run keeps its log tail and is retried once
with a lower utilisation and a doubled clock period. Results go to m3/layouts/raw/<name>_<pdk>.json.

Usage: python run_layouts.py <worktree root> <workers> [name_pdk ...]
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
WORKERS = int(sys.argv[2])
ONLY = set(sys.argv[3:])
OUT = ROOT / "m3" / "layouts"
RAW = OUT / "raw"
RAW.mkdir(parents=True, exist_ok=True)
CLI = [str(ROOT / "chiplab" / ".venv" / "bin" / "python"), str(Path(__file__).resolve().parent / "layout_cli.py")]
DESIGNS = json.loads((OUT / "designs.json").read_text())
RUNS = [("spike", "gf180"), ("spike", "ihp"), ("torchlogix", "sky130"), ("torchlogix", "gf180"),
        ("torchlogix", "ihp"), ("fusion", "sky130"), ("fusion", "gf180"), ("fusion", "ihp")]
CLOCK_NS = 20.0
UTIL = 40


def call(design_id: str, pdk: str, clock: float, util: int) -> tuple[dict, float, str]:
    args = {"design_id": design_id, "pdk": pdk, "clock_period_ns": clock, "core_util": util, "timeout": 5400}
    t0 = time.time()
    p = subprocess.run([*CLI, "layout", "--json", json.dumps(args)], capture_output=True, text=True, timeout=6000,
                       cwd=str(ROOT / "chiplab"))
    wall = round(time.time() - t0, 1)
    try:
        res = json.loads(p.stdout)
    except json.JSONDecodeError:
        res = {"status": "error", "error": (p.stdout + p.stderr)[-3000:]}
    return res, wall, p.stderr[-3000:]


def full_metrics(res: dict) -> dict:
    gds = res.get("gds")
    if not gds:
        return {}
    mj = Path(gds).parent.parent / "metrics.json"
    return json.loads(mj.read_text()) if mj.exists() else {}


def one(name: str, pdk: str) -> dict:
    did = DESIGNS[name]["design_id"]
    attempts = []
    clock, util = CLOCK_NS, UTIL
    for attempt in (1, 2):
        start = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        res, wall, err = call(did, pdk, clock, util)
        ok = res.get("status", "ok") != "error" and res.get("gds") is not None
        rec = {"attempt": attempt, "clock_period_ns": clock, "core_util": util, "started": start, "wall_seconds": wall,
               "ok": ok}
        if ok:
            rec["result"] = res
            rec["metrics_full"] = full_metrics(res)
            if res.get("png"):
                shutil.copy(res["png"], OUT / f"{name}_{res['pdk']}.png")
        else:
            rec["error"] = res.get("error") or res
            rec["stderr_tail"] = err
        attempts.append(rec)
        print(json.dumps({"run": f"{name}_{pdk}", "attempt": attempt, "ok": ok, "wall_s": wall}), flush=True)
        if ok:
            break
        clock, util = clock * 2, 25  # retry: longer clock, lower density
    out = {"name": name, "pdk": pdk, "design_id": did, "attempts": attempts}
    prev = RAW / f"{name}_{pdk}.json"
    if prev.exists():  # keep earlier failed tries on record
        old = json.loads(prev.read_text())
        out["earlier_attempts"] = old.get("earlier_attempts", []) + old["attempts"]
    prev.write_text(json.dumps(out, indent=1, default=str))
    return out


def main() -> None:
    todo = [r for r in RUNS if not ONLY or f"{r[0]}_{r[1]}" in ONLY]
    t0 = time.time()
    with ThreadPoolExecutor(WORKERS) as ex:
        list(ex.map(lambda r: one(*r), todo))
    print(json.dumps({"done": len(todo), "workers": WORKERS, "batch_wall_s": round(time.time() - t0, 1)}), flush=True)


if __name__ == "__main__":
    main()
