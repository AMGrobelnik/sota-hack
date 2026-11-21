"""Summarise results/runs.csv and results/designs.csv: median, min and max per mode, the paired speedup, the
correctness check (same gates and depth for every design in every run and mode) and the estimate accuracy.

Usage: python summarize.py <results dir>   (writes summary.json next to the CSVs and prints it)
"""
from __future__ import annotations

import csv
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path


def spread(xs: list[float]) -> dict:
    return {"median": statistics.median(xs), "min": min(xs), "max": max(xs), "runs": xs}


def main(res: Path) -> None:
    runs = list(csv.DictReader((res / "runs.csv").open()))
    designs = list(csv.DictReader((res / "designs.csv").open()))
    by = defaultdict(dict)
    for r in runs:
        by[r["mode"]][int(r["run"])] = r
    out = {"modes": {}}
    for m, rr in sorted(by.items()):
        ks = sorted(rr)
        out["modes"][m] = {
            "designs_per_hour": spread([float(rr[k]["designs_per_hour"]) for k in ks]),
            "wall_s": spread([float(rr[k]["wall_s"]) for k in ks]),
            "workers": sorted({rr[k]["workers"] for k in ks}),
            "load1_start": [float(rr[k]["load1_start"]) for k in ks],
            "all_ok": all(rr[k]["ok"] == rr[k]["n"] for k in ks),
            "cold_or_cached_flags": [rr[k]["cold_checked"] for k in ks],
            "startup_s": [rr[k]["startup_s"] for k in ks if rr[k]["startup_s"]],
        }
    a, b = by["a_serial"], by["b_batch"]
    paired = [float(b[k]["designs_per_hour"]) / float(a[k]["designs_per_hour"]) for k in sorted(a) if k in b]
    out["speedup_b_over_a"] = {
        "ratio_of_medians": statistics.median(float(b[k]["designs_per_hour"]) for k in b)
        / statistics.median(float(a[k]["designs_per_hour"]) for k in a),
        "paired_per_run": spread(paired)}
    # end to end per run: serial ingest + start-up + synthesis, the same for the batch (ingest is serial in both)
    e2e = {m: {k: float(r["ingest_s"]) + float(r["startup_s"]) + float(r["wall_s"]) for k, r in by[m].items()}
           for m in ("a_serial", "b_batch")}
    out["end_to_end_s_incl_ingest"] = {m: spread([v[k] for k in sorted(v)]) for m, v in e2e.items()}
    out["end_to_end_speedup"] = {
        "ratio_of_medians": statistics.median(e2e["a_serial"].values()) / statistics.median(e2e["b_batch"].values()),
        "paired_per_run": spread([e2e["a_serial"][k] / e2e["b_batch"][k] for k in sorted(e2e["a_serial"])])}
    sig = defaultdict(set)
    for d in designs:
        sig[d["name"]].add((d["gates"], d["depth"]))
    out["correctness"] = {"designs": len(sig), "rows": len(designs),
                          "mismatching_designs": sorted(n for n, s in sig.items() if len(s) > 1),
                          "cached_flag_in_cold_rows": sum(d["cached"] == "True" for d in designs)}
    est = by["d_estimate"]
    out["estimate"] = {k: est[k]["notes"] for k in sorted(est)}
    first = [d for d in designs if d["mode"] == "b_batch" and d["run"] == "1"]
    g = [int(d["gates"]) for d in first]
    out["gates"] = {"min": min(g), "median": statistics.median(g), "max": max(g), "n": len(g)}
    (res / "summary.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
