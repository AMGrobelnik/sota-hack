"""Compile, synthesise and verify designs through the chip lab's command line, in parallel.

usage:
  python -I -m neonatal_eeg.lab compile --designs designs.json --out lab.json --chiplab BIN [--workers K]
  python -I -m neonatal_eeg.lab verify  --designs designs.json --lab lab.json --ids a,b --prep vectors.npz ...

CHIPLAB_USER_DIR and CHIPLAB_CONFIG must be set by the caller. Every call's JSON answer and exit code is kept
in lab.json so a lab fault can be reported as it happened.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from loguru import logger


def call(chiplab: str, tool: str, args: dict, cwd: Path, timeout: int = 1800) -> tuple[int, dict]:
    with tempfile.NamedTemporaryFile("w", suffix=".json", dir=cwd, delete=False) as f:
        json.dump(args, f)
        argf = f.name
    try:
        p = subprocess.run([chiplab, tool, "--json-file", argf], cwd=cwd, capture_output=True, text=True,
                           timeout=timeout)
        code = p.returncode
        try:
            ans = json.loads(p.stdout)
        except json.JSONDecodeError:
            ans = {"status": "unparsed", "stdout": p.stdout[-2000:], "stderr": p.stderr[-2000:]}
    except subprocess.TimeoutExpired:
        code, ans = 3, {"status": "timeout-local"}
    finally:
        Path(argf).unlink(missing_ok=True)
    return code, ans


def compile_one(chiplab: str, cwd: Path, d: dict) -> dict:
    t0 = time.time()
    rec: dict = {"id": d["id"]}
    code, ans = call(chiplab, "compile-ir", {"ir": d["ir"]}, cwd)
    rec["compile"] = {"exit": code, "status": ans.get("status"), "error": ans.get("error")}
    if code != 0 or "design_id" not in ans:
        rec["compile"]["answer"] = ans
        return rec
    rec["design_id"] = ans["design_id"]
    code, ans = call(chiplab, "synthesize", {"design_id": rec["design_id"]}, cwd)
    rec["synth"] = {"exit": code, "status": ans.get("status"), "error": ans.get("error")}
    if code == 0:
        met = ans.get("metrics") or {}
        rec["gates"] = met.get("gates")
        rec["depth"] = met.get("depth")
        rec["cells_by_type"] = ans.get("cells_by_type")
    else:
        rec["synth"]["answer"] = ans
    rec["wall_s"] = round(time.time() - t0, 1)
    return rec


@logger.catch(reraise=True)
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["compile", "verify"])
    ap.add_argument("--designs", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--chiplab", required=True)
    ap.add_argument("--cwd", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--ids", default="")
    ap.add_argument("--vectors", type=Path)
    a = ap.parse_args()
    logger.add(a.out.with_suffix(".log"))
    a.cwd.mkdir(parents=True, exist_ok=True)
    dj = json.loads(a.designs.read_text())
    designs = dj["designs"] + ([dj["baseline"]] if dj["baseline"].get("ir") else [])
    if a.cmd == "compile":
        done = json.loads(a.out.read_text()) if a.out.exists() else {}
        todo = [d for d in designs if d["id"] not in done or done[d["id"]].get("gates") is None]
        if a.ids:
            keep = set(a.ids.split(","))
            todo = [d for d in todo if d["id"] in keep]
        # smallest first, so a time limit still leaves a spread of compiled designs
        todo.sort(key=lambda d: (d.get("spec", {}).get("channels", 0) * max(1, d.get("spec", {}).get("hidden", 0)), d["id"]))
        logger.info(f"compiling {len(todo)} designs with {a.workers} workers")
        with ThreadPoolExecutor(a.workers) as ex:
            for i, rec in enumerate(ex.map(lambda d: compile_one(a.chiplab, a.cwd, d), todo), 1):
                done[rec["id"]] = rec
                a.out.write_text(json.dumps(done, indent=1))
                logger.info(f"{i}/{len(todo)} {rec['id']} gates={rec.get('gates')} depth={rec.get('depth')} "
                            f"compile={rec['compile']['exit']} synth={rec.get('synth', {}).get('exit')} {rec.get('wall_s')}s")
        logger.info("LAB-COMPILE-DONE")
    else:
        lab = json.loads(a.designs.with_name("lab.json").read_text())
        vec = json.loads(a.vectors.read_text())
        ids = a.ids.split(",")
        res = json.loads(a.out.read_text()) if a.out.exists() else {}

        def one(i: str) -> dict:
            did = lab[i]["design_id"]
            v = vec[i]
            c1, s = call(a.chiplab, "simulate", {"design_id": did, "inputs": "vectors",
                                                 "vectors": {"x": v["x"]}, "expected": v["expected"]}, a.cwd)
            c2, p = call(a.chiplab, "prove-equivalence", {"design_id": did, "golden": True, "timeout": 600}, a.cwd)
            c3, lv = call(a.chiplab, "verification-level", {"design_id": did}, a.cwd)
            return {"id": i, "design_id": did, "simulate": {"exit": c1, "answer": s},
                    "prove": {"exit": c2, "answer": p}, "level": {"exit": c3, "answer": lv}}

        with ThreadPoolExecutor(min(a.workers, 6)) as ex:
            for r in ex.map(one, ids):
                res[r["id"]] = r
                a.out.write_text(json.dumps(res, indent=1))
                logger.info(f"verify {r['id']} sim={r['simulate']['exit']} prove={r['prove']['exit']} "
                            f"level={r['level']['exit']}")
        logger.info("LAB-VERIFY-DONE")


if __name__ == "__main__":
    main()
