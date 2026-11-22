"""Run chosen designs through the chip lab (the `chiplab` CLI, used as is).

Per design: compile-ir, synthesize (generic gates, depth), map-to-process (sky130, gf180, ihp:
area and NAND2 gate-equivalents), simulate with the held-out test beats' actual inputs and the
integer model's expected outputs (level 1), prove-equivalence with the golden model (level 2),
verification-level.

Every call has a time cap; on timeout the whole process group is killed.

Usage: python -I chip_eval.py <chiplab bin> <job json> <out json>
job json: {"designs": [{"key": str, "ir": {...}, "vectors": {"b": [[...]], "rr": [[...]]}, "expected": [...]}]}
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

PDKS = ("sky130", "gf180", "ihp")


def call(chiplab: str, tool: str, args: dict, cap: int) -> dict:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(args, fh)
        path = fh.name
    proc = subprocess.Popen(
        [chiplab, tool, "--json-file", path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        out, err = proc.communicate(timeout=cap)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.communicate()
        return {"status": "timeout", "tool": tool, "cap_s": cap}
    finally:
        Path(path).unlink(missing_ok=True)
    try:
        return json.loads(out[out.find("{") :])
    except json.JSONDecodeError:
        return {"status": "error", "tool": tool, "stdout": out[-2000:], "stderr": err[-2000:]}


def main(chiplab: str, job: Path, out: Path) -> None:
    spec = json.loads(job.read_text())
    results = json.loads(out.read_text()) if out.exists() else {}
    for d in spec["designs"]:
        key = d["key"]
        if key in results and results[key].get("done"):
            continue
        r: dict = {}
        c = call(chiplab, "compile-ir", {"ir": d["ir"]}, 300)
        r["compile"] = {k: c.get(k) for k in ("status", "design_id", "lint", "error")}
        did = c.get("design_id")
        if did:
            r["synth"] = call(chiplab, "synthesize", {"design_id": did, "timeout": 900}, 960)
            r["map"] = {p: call(chiplab, "map-to-process", {"design_id": did, "pdk": p}, 900) for p in PDKS}
            r["sim"] = call(
                chiplab,
                "simulate",
                {"design_id": did, "inputs": "vectors", "vectors": d["vectors"], "expected": d["expected"], "device": "numpy"},
                900,
            )
            r["sim_random"] = call(chiplab, "simulate", {"design_id": did, "inputs": "random", "n": 100000, "device": "numpy"}, 900)
            r["proof"] = call(chiplab, "prove-equivalence", {"design_id": did, "timeout": 600, "golden": True}, 1300)
            r["level"] = call(chiplab, "verification-level", {"design_id": did}, 120)
        r["done"] = True
        results[key] = r
        out.write_text(json.dumps(results, indent=1))
        print(key, did, r.get("synth", {}).get("status"), r.get("proof", {}).get("status"), flush=True)


if __name__ == "__main__":
    main(sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]))
