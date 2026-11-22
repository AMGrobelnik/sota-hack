"""Summarise the baseline authors' own released Monte Carlo CV results (COIN, flexwnn repo).

Reads the res_coin_*.csv files of the archive cv_almost_2023-05-04.tar.gz (pickles are never
opened) and applies the authors' cv_summary.py rule: per fold, keep the model with the highest
validation AUC. Prints per-fold sensitivity and specificity on that fold's 3 test patients.

Usage: python -I coin_archive_summary.py <extracted cv dir> <out json>
"""

from __future__ import annotations

import csv
import json
import statistics
import sys
from pathlib import Path


def main(cv_dir: Path, out_json: Path) -> None:
    rows = []
    for fold_dir in sorted((cv_dir / "outs").iterdir()):
        res = sorted(fold_dir.glob("res_coin_*.csv"))
        if not res:
            continue
        with res[0].open() as fh:
            recs = list(csv.DictReader(fh))
        best = max(recs, key=lambda r: float(r["auc_val"]))
        fold = int(fold_dir.name.split("_")[1])
        test = [int(x) for x in (cv_dir / "lists" / f"test_{fold:02d}.txt").read_text().split()]
        rows.append(
            {
                "fold": fold,
                "test_patients": test,
                "n_minterms": int(best["n_minterms"]),
                "sensitivity": float(best["sensitivity"]),
                "specificity": float(best["specificity"]),
                "accuracy": float(best["acc_fixed"]),
                "auc": float(best["auc"]),
            }
        )
    rows = [r for r in rows if r["fold"] < 50]
    summ = {
        "n_folds": len(rows),
        "mean_sensitivity": statistics.mean(r["sensitivity"] for r in rows),
        "mean_specificity": statistics.mean(r["specificity"] for r in rows),
        "mean_accuracy": statistics.mean(r["accuracy"] for r in rows),
        "mean_auc": statistics.mean(r["auc"] for r in rows),
        "mean_minterms": statistics.mean(r["n_minterms"] for r in rows),
        "folds_with_spec_ge_0998": sum(r["specificity"] >= 0.998 for r in rows),
        "min_sensitivity": min(r["sensitivity"] for r in rows),
        "folds": rows,
    }
    out_json.write_text(json.dumps(summ, indent=1))
    print({k: v for k, v in summ.items() if k != "folds"})


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
