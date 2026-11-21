"""One benchmark run of one mode, in a fresh lab home (CHIPLAB_HOME must point at an empty folder).

  serial : (a) baseline. One warm Python process calls the lab's `synthesize` tool on each design in turn.
  batch  : (b) the lab's `synthesize-batch` on Huey workers (CHIPLAB_CPU_WORKERS of them), then in the same home
           (c) a cached re-run of the same batch, and of the serial calls, and
           (d) `estimate-batch` timed and scored against the synthesized gate counts of step (b).

Both modes first ingest every design with the lab's `ingest-model` (timed separately, not part of the speed number)
and check that the result cache holds no synthesis result before the timed step (cold). Every synthesize result's
`cached` flag is recorded per design, so a cold step that touched the cache would show in the CSV.

Usage: python bench.py --mode serial|batch --run N --designs designs.json --out results_dir
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from pathlib import Path

T_PROC = time.time()
from chiplab import cache, config  # noqa: E402
from chiplab.cli import _tools  # noqa: E402

TOOLS = _tools()
T_IMPORT = time.time() - T_PROC

RUN_FIELDS = ["run", "mode", "n", "ok", "wall_s", "designs_per_hour", "workers", "cold_checked", "startup_s",
              "ingest_s", "load1_start", "load1_end", "mem_free_pct_start", "top_procs_start", "notes"]
DESIGN_FIELDS = ["run", "mode", "name", "H", "bits", "L", "seed", "design_id", "gates", "depth", "yosys_s",
                 "cached", "gates_est_default", "gates_est_heldout"]


def call(tool_name: str, /, **kw) -> dict:
    return TOOLS[tool_name]["fn"](**kw)


def snapshot() -> dict:
    """Load average, free memory and the five busiest processes (basenames only) at this moment."""
    load1 = os.getloadavg()[0]
    mem = subprocess.run(["memory_pressure", "-Q"], capture_output=True, text=True, timeout=30).stdout
    free = next((l.split(":")[1].strip().rstrip("%") for l in mem.splitlines() if "free percentage" in l), "")
    ps = subprocess.run(["ps", "-Ao", "pcpu=,comm="], capture_output=True, text=True, timeout=30).stdout
    rows = sorted(((float(l.split(None, 1)[0]), Path(l.split(None, 1)[1].strip()).name)
                   for l in ps.splitlines() if len(l.split(None, 1)) == 2), reverse=True)[:5]
    return {"load1": round(load1, 2), "mem_free_pct": free, "top": "; ".join(f"{n} {c:.0f}%" for c, n in rows)}


def synth_cache_entries(ids: list[str]) -> int:
    return sum(cache.get("synthesize", {"design_id": d, "target": "generic"}) is not None for d in ids)


def ingest(designs: list[dict]) -> tuple[list[str], float]:
    t0 = time.time()
    ids = []
    for d in designs:
        r = call("ingest_model", format="intnn", model=d["model"], name=d["name"])
        if r.get("status") != "ok":
            raise RuntimeError(f"ingest {d['name']}: {r.get('error')}")
        ids.append(r["design_id"])
    return ids, time.time() - t0


def write(out: Path, fname: str, fields: list[str], rows: list[dict]) -> None:
    p = out / fname
    new = not p.exists()
    with p.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if new:
            w.writeheader()
        w.writerows(rows)


def r2(y: list[float], p: list[float]) -> float:
    m = sum(y) / len(y)
    return 1 - sum((a - b) ** 2 for a, b in zip(y, p)) / sum((a - m) ** 2 for a in y)


def run_serial(designs, ids, run, out, ingest_s):
    assert synth_cache_entries(ids) == 0, "cache not cold"
    s0 = snapshot()
    t0 = time.time()
    res = [call("synthesize", design_id=d, target="generic") for d in ids]
    wall = time.time() - t0
    s1 = snapshot()
    ok = sum(r.get("status") == "ok" for r in res)
    cold = not any(r.get("cached") for r in res)
    write(out, "runs.csv", RUN_FIELDS, [{
        "run": run, "mode": "a_serial", "n": len(ids), "ok": ok, "wall_s": round(wall, 3),
        "designs_per_hour": round(len(ids) / wall * 3600), "workers": 1, "cold_checked": cold,
        "startup_s": round(T_IMPORT, 3), "ingest_s": round(ingest_s, 3), "load1_start": s0["load1"],
        "load1_end": s1["load1"], "mem_free_pct_start": s0["mem_free_pct"], "top_procs_start": s0["top"],
        "notes": "one warm process; startup_s = Python import of the lab"}])
    write(out, "designs.csv", DESIGN_FIELDS, [{
        "run": run, "mode": "a_serial", **{k: d[k] for k in ("name", "H", "bits", "L", "seed")}, "design_id": i,
        "gates": r.get("metrics", {}).get("gates"), "depth": r.get("metrics", {}).get("depth"),
        "yosys_s": r.get("seconds"), "cached": bool(r.get("cached"))} for d, i, r in zip(designs, ids, res)])


def wait_jobs(job_ids: list[str], limit_s: float) -> None:
    from chiplab.jobs import queue
    t_end = time.time() + limit_s
    marks = ",".join("?" * len(job_ids))
    while time.time() < t_end:
        con = queue._db()
        left = con.execute(f"SELECT COUNT(*) FROM jobs WHERE id IN ({marks}) AND status IN ('queued','running')",
                           job_ids).fetchone()[0]
        con.close()
        if left == 0:
            return
        time.sleep(0.02)
    raise TimeoutError(f"jobs not done after {limit_s} s")


def finished_at(job_ids: list[str]) -> float:
    from chiplab.jobs import queue
    con = queue._db()
    t = con.execute(f"SELECT MAX(finished) FROM jobs WHERE id IN ({','.join('?' * len(job_ids))})", job_ids).fetchone()[0]
    con.close()
    return t


def batch(ids: list[str]) -> tuple[list[dict], float]:
    t0 = time.time()
    jids = call("synthesize_batch", design_ids=ids, target="generic")["job_ids"]
    wait_jobs(jids, 3000)
    wall = finished_at(jids) - t0
    return [call("job_result", job_id=j)["result"] for j in jids], wall


def run_batch(designs, ids, run, out, ingest_s):
    from chiplab.jobs.queue import LANES
    from chiplab.mcp_server import start_workers
    assert synth_cache_entries(ids) == 0, "cache not cold"
    t0 = time.time()
    procs = start_workers()
    probe = call("submit_job", tool="cache_stats")["job_id"]
    wait_jobs([probe], 120)
    startup = time.time() - t0
    try:
        s0 = snapshot()
        res, wall = batch(ids)
        s1 = snapshot()
        cold = not any(r.get("cached") for r in res)
        # (c) cached re-runs: the same batch through the workers, and the same calls in this one process
        c0 = snapshot()
        cres, cwall = batch(ids)
        t1 = time.time()
        sres = [call("synthesize", design_id=d, target="generic") for d in ids]
        swall = time.time() - t1
        c1 = snapshot()
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            p.wait(timeout=60)
    # (d) estimate-batch, default coefficients as shipped (no estimator.json in this fresh home)
    gates = [r["metrics"]["gates"] for r in res]
    t2 = time.time()
    est = call("estimate_batch", designs=ids)
    ewall = time.time() - t2
    basis = est["est_basis"]
    r2_def = r2(gates, est["gates_est"])
    # held-out: refit with the lab's own refit on two folds, score on the third, for each of the three folds
    from chiplab.ir.estimate import refit
    irs = [json.loads((config.HOME / "designs" / i / "ir.json").read_text()) for i in ids]
    heldout = [None] * len(ids)
    for fold in (1, 2, 3):
        refit([(irs[k], gates[k]) for k, d in enumerate(designs) if d["fold"] not in (0, fold)])
        test = [k for k, d in enumerate(designs) if d["fold"] == fold]
        e = call("estimate_batch", designs=[ids[k] for k in test])
        for k, g in zip(test, e["gates_est"]):
            heldout[k] = g
    ks = [k for k in range(len(ids)) if heldout[k] is not None]
    r2_ho = r2([gates[k] for k in ks], [heldout[k] for k in ks])
    common = {"n": len(ids), "workers": LANES["cpu"], "ingest_s": round(ingest_s, 3)}
    rows = [
        {"run": run, "mode": "b_batch", **common, "ok": sum(r.get("status") == "ok" for r in res),
         "wall_s": round(wall, 3), "designs_per_hour": round(len(ids) / wall * 3600), "cold_checked": cold,
         "startup_s": round(startup, 3), "load1_start": s0["load1"], "load1_end": s1["load1"],
         "mem_free_pct_start": s0["mem_free_pct"], "top_procs_start": s0["top"],
         "notes": "startup_s = start_workers until a no-op probe job finished; wall = submit to last job finished"},
        {"run": run, "mode": "c_cached_batch", **common, "ok": sum(r.get("status") == "ok" for r in cres),
         "wall_s": round(cwall, 3), "designs_per_hour": round(len(ids) / cwall * 3600),
         "cold_checked": f"all_cached={all(r.get('cached') for r in cres)}", "startup_s": "",
         "load1_start": c0["load1"], "load1_end": c1["load1"], "mem_free_pct_start": c0["mem_free_pct"],
         "top_procs_start": c0["top"], "notes": "same batch again through the workers"},
        {"run": run, "mode": "c_cached_serial", **common, "workers": 1,
         "ok": sum(r.get("status") == "ok" for r in sres), "wall_s": round(swall, 3),
         "designs_per_hour": round(len(ids) / swall * 3600),
         "cold_checked": f"all_cached={all(r.get('cached') for r in sres)}", "startup_s": "",
         "load1_start": c0["load1"], "load1_end": c1["load1"], "mem_free_pct_start": c0["mem_free_pct"],
         "top_procs_start": c0["top"], "notes": "same calls again in one process"},
        {"run": run, "mode": "d_estimate", **common, "workers": 1, "ok": len(est["gates_est"]),
         "wall_s": round(ewall, 4), "designs_per_hour": round(len(ids) / ewall * 3600), "cold_checked": "",
         "startup_s": "", "load1_start": c1["load1"], "load1_end": "", "mem_free_pct_start": c1["mem_free_pct"],
         "top_procs_start": c1["top"],
         "notes": f"r2_default={r2_def:.4f}; r2_heldout_3fold={r2_ho:.4f} (n={len(ks)}); basis={basis}"},
    ]
    write(out, "runs.csv", RUN_FIELDS, rows)
    write(out, "designs.csv", DESIGN_FIELDS, [{
        "run": run, "mode": "b_batch", **{k: d[k] for k in ("name", "H", "bits", "L", "seed")}, "design_id": i,
        "gates": r.get("metrics", {}).get("gates"), "depth": r.get("metrics", {}).get("depth"),
        "yosys_s": r.get("seconds"), "cached": bool(r.get("cached")), "gates_est_default": g,
        "gates_est_heldout": h} for d, i, r, g, h in zip(designs, ids, res, est["gates_est"], heldout)])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("serial", "batch"), required=True)
    ap.add_argument("--run", type=int, required=True)
    ap.add_argument("--designs", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    if any(config.HOME.iterdir()) and set(p.name for p in config.HOME.iterdir()) - {"jobs", "cache_results", "logs"}:
        print(f"lab home is not fresh: {sorted(p.name for p in config.HOME.iterdir())}", file=sys.stderr)
        return 2
    designs = json.loads(a.designs.read_text())["designs"]
    a.out.mkdir(parents=True, exist_ok=True)
    ids, ingest_s = ingest(designs)
    (run_serial if a.mode == "serial" else run_batch)(designs, ids, a.run, a.out, ingest_s)
    print(json.dumps({"run": a.run, "mode": a.mode, "done": True}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
