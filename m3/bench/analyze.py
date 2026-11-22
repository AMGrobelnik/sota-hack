"""Per-design detail from results/designs.csv: where the batch is slower per job, and how well the lab's gate
estimate tracks real gates and synthesis time.

Usage: python analyze.py <results dir>   (writes analysis.json next to the CSVs and prints it)
"""
from __future__ import annotations

import csv
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path


def r2(y: list[float], p: list[float]) -> float:
    m = sum(y) / len(y)
    return 1 - sum((a - b) ** 2 for a, b in zip(y, p)) / sum((a - m) ** 2 for a in y)


def pearson_r2(x: list[float], y: list[float]) -> float:
    mx, my = statistics.mean(x), statistics.mean(y)
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    return sxy * sxy / (sxx * syy)


def main(res: Path) -> None:
    rows = list(csv.DictReader((res / "designs.csv").open()))
    t = defaultdict(lambda: defaultdict(list))  # mode -> name -> yosys_s over runs
    gates, est_def, est_ho = {}, {}, {}
    for d in rows:
        t[d["mode"]][d["name"]].append(float(d["yosys_s"]))
        gates[d["name"]] = int(d["gates"])
        if d["mode"] == "b_batch" and d["run"] == "1":
            est_def[d["name"]] = float(d["gates_est_default"])
            est_ho[d["name"]] = float(d["gates_est_heldout"]) if d["gates_est_heldout"] else None
    names = sorted(gates, key=gates.get)
    med = {m: {n: statistics.median(t[m][n]) for n in names} for m in ("a_serial", "b_batch")}
    third = len(names) // 3
    bins = {"small": names[:third], "medium": names[third:2 * third], "large": names[2 * third:]}
    out = {"per_job_yosys_s_batch_over_serial": {}}
    for b, ns in bins.items():
        ratios = [med["b_batch"][n] / med["a_serial"][n] for n in ns]
        out["per_job_yosys_s_batch_over_serial"][b] = {
            "gates_range": [gates[ns[0]], gates[ns[-1]]], "n": len(ns),
            "serial_median_s": round(statistics.median(med["a_serial"][n] for n in ns), 3),
            "batch_median_s": round(statistics.median(med["b_batch"][n] for n in ns), 3),
            "ratio_median": round(statistics.median(ratios), 2)}
    out["sum_yosys_s"] = {m: round(sum(med[m].values()), 1) for m in med}
    g = [gates[n] for n in names]
    out["gate_estimate"] = {
        "r2_default_coefficients": round(r2(g, [est_def[n] for n in names]), 4),
        "median_est_over_real_default": round(statistics.median(est_def[n] / gates[n] for n in names), 2),
    }
    ho = [n for n in names if est_ho[n] is not None]
    out["gate_estimate"]["r2_heldout_3fold"] = round(r2([gates[n] for n in ho], [est_ho[n] for n in ho]), 4)
    out["gate_estimate"]["median_abs_pct_err_heldout"] = round(
        100 * statistics.median(abs(est_ho[n] - gates[n]) / gates[n] for n in ho), 1)
    out["gate_estimate"]["n_heldout"] = len(ho)
    ys = [med["a_serial"][n] for n in ho]
    out["synth_time_vs_estimate"] = {
        "pearson_r2_serial_yosys_s_vs_heldout_est": round(pearson_r2([est_ho[n] for n in ho], ys), 4),
        "pearson_r2_serial_yosys_s_vs_real_gates": round(pearson_r2([gates[n] for n in ho], ys), 4)}
    (res / "analysis.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
