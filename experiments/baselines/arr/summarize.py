"""Aggregate fold results, chip-lab results and the DS1/DS2 run into results.json.

Usage: python -I summarize.py <coin run dir> <coin archive summary json> <baseline lists dir>
                              <chip json> <ds results json> <out results.json>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

from arrlib import wilson

BASELINE = {
    "source": "Miranda et al., IEEE TVLSI 34(2), 2026, doi 10.1109/TVLSI.2025.3630337; preprint https://utw10244.utweb.utexas.edu/pubs/miranda_ieeevlsi26.pdf",
    "fold": 18,
    "test_patients": [107, 213, 209],
    "TP": 2147,
    "P": 3129,
    "TN": 5311,
    "N": 5320,
    "sensitivity": 0.6862,
    "specificity": 0.9983,
    "nand2_eq_synthesis": 2549,
    "nand2_eq_after_layout": 5706,
    "note": "counts derived from the published rates and this fold's class counts (2147/3129 = 0.68616, 5311/5320 = 0.99831)",
}
GROUPS = {"paced": [102, 104, 107, 217], "fusion": [208, 213], "sveb": [209, 222, 201, 118, 220]}
RULE = "0.999"


def rate(k: int, n: int) -> dict:
    lo, hi = wilson(k, n)
    return {"k": k, "n": n, "rate": k / n if n else None, "wilson95": [lo, hi]}


def patient_bootstrap(per: dict[int, dict], reps: int = 2000, seed: int = 0) -> dict:
    """Stratified (paced / fusion / S groups) bootstrap over distinct test patients of pooled counts."""
    rng = np.random.default_rng(seed)
    sens, spec = [], []
    for _ in range(reps):
        tp = p = tn = n = 0
        for g in GROUPS.values():
            avail = [r for r in g if r in per]
            for r in rng.choice(avail, len(avail), replace=True):
                c = per[int(r)]
                tp += c["TP"]; p += c["P"]; tn += c["TN"]; n += c["N"]
        sens.append(tp / p if p else np.nan)
        spec.append(tn / n if n else np.nan)
    return {"sens95": [float(np.nanpercentile(sens, 2.5)), float(np.nanpercentile(sens, 97.5))], "spec95": [float(np.nanpercentile(spec, 2.5)), float(np.nanpercentile(spec, 97.5))]}


def summarize_design(folds: list[dict], key: str, kind: str, archive: dict[int, dict]) -> dict:
    out: dict = {"rules": {}}
    rules = folds[0][kind][key]["rules"].keys()
    for rule in rules:
        rows = [(f["fold"], f[kind][key]["rules"][rule]) for f in folds]
        TP = sum(r["TP"] for _, r in rows); P = sum(r["P"] for _, r in rows)
        TN = sum(r["TN"] for _, r in rows); N = sum(r["N"] for _, r in rows)
        per: dict[int, dict] = {}
        for _, r in rows:
            for pid, c in r["per_patient"].items():
                d = per.setdefault(int(pid), {"TP": 0, "P": 0, "TN": 0, "N": 0})
                for k in d:
                    d[k] += c[k]
        fsens = [r["TP"] / r["P"] for _, r in rows]
        fspec = [r["TN"] / r["N"] for _, r in rows]
        h2h = [(fo, r) for fo, r in rows if fo in archive]
        wins = sum(1 for fo, r in h2h if r["TP"] / r["P"] > archive[fo]["sensitivity"] and r["TN"] / r["N"] >= archive[fo]["specificity"])
        worst = min((pid for pid in per if per[pid]["P"] > 0), key=lambda pid: per[pid]["TP"] / per[pid]["P"])
        worst_fp = max(per, key=lambda pid: per[pid]["N"] - per[pid]["TN"])
        f18 = dict(rows)[18] if 18 in dict(rows) else None
        entry = {
            "pooled_all_folds": {"sensitivity": rate(TP, P), "specificity": rate(TN, N), "patient_bootstrap": patient_bootstrap(per)},
            "n_folds": len(rows),
            "mean_fold_sensitivity": float(np.mean(fsens)),
            "mean_fold_specificity": float(np.mean(fspec)),
            "folds_spec_ge_0998": int(sum(s >= 0.998 for s in fspec)),
            "folds_spec_ge_0998_and_sens_gt_06862": int(sum(se > 0.6862 and sp >= 0.998 for se, sp in zip(fsens, fspec))),
            "head_to_head_vs_coin_archive": {"folds": len(h2h), "higher_sens_and_no_lower_spec": wins},
            "worst_patient_sensitivity": {"patient": worst, **rate(per[worst]["TP"], per[worst]["P"])},
            "most_false_positives": {"patient": worst_fp, "FP": per[worst_fp]["N"] - per[worst_fp]["TN"], "N": per[worst_fp]["N"]},
            "per_patient_pooled": per,
        }
        if f18 is not None:
            entry["fold18_published_split"] = {
                "sensitivity": rate(f18["TP"], f18["P"]),
                "specificity": rate(f18["TN"], f18["N"]),
                "FP": f18["N"] - f18["TN"],
                "per_patient": f18["per_patient"],
                "beats_baseline": bool(f18["TP"] > BASELINE["TP"] and f18["TN"] / f18["N"] >= 0.998),
            }
        out["rules"][rule] = entry
    if kind == "designs":
        out["track"] = folds[0][kind][key]["track"]
        out["oracle_mean_sens_at_test_spec0998_DIAGNOSTIC"] = float(np.mean([f[kind][key]["oracle_sens_at_spec0998"] for f in folds]))
        out["n_bit_inputs_fold18"] = next((f[kind][key]["rules"][RULE]["n_bit_inputs"] for f in folds if f["fold"] == 18), None)
    return out


def check_counts(folds: list[dict], lists: Path) -> dict:
    """Compare our per-fold class counts with the baseline's archived classes_count files."""
    ok = bad = 0
    for f in folds:
        p = lists / f"classes_count_{f['fold']:02d}.txt"
        if not p.exists():
            continue
        lines = {ln.split(":")[0].strip(): [int(x) for x in ln.split(":")[1].split(",") if x.strip()] for ln in p.read_text().splitlines() if ":" in ln}
        good = lines.get("Test") == f["class_counts_test"] and lines.get("Val") == f["class_counts_val"]
        ok += good
        bad += not good
    return {"folds_checked": ok + bad, "test_and_val_counts_identical": ok}


def chip_table(chip: dict) -> dict:
    out = {}
    for k, v in chip.items():
        s = v.get("synth", {}).get("metrics", {})
        out[k] = {
            "design_id": v["compile"].get("design_id"),
            "generic_gates": s.get("gates"),
            "logic_depth": s.get("depth"),
            "cells_by_type": v.get("synth", {}).get("cells_by_type"),
            "gate_equivalents": {p: m.get("metrics", {}).get("gate_equivalents") for p, m in v.get("map", {}).items()},
            "area_um2": {p: m.get("metrics", {}).get("area_um2") for p, m in v.get("map", {}).items()},
            "std_cells": {p: m.get("metrics", {}).get("std_cells") for p, m in v.get("map", {}).items()},
            "bit_exact_test_vectors": v.get("sim", {}).get("bit_exact"),
            "n_test_vectors": v.get("sim", {}).get("n"),
            "bit_exact_random_100k": v.get("sim_random", {}).get("bit_exact"),
            "proof": {kk: v.get("proof", {}).get(kk) for kk in ("proved", "against", "method", "seconds")},
            "verification_level": v.get("level", {}).get("verification_level"),
        }
    return out


def ds_table(ds: dict) -> dict:
    out = {"class_counts_N_S_V_F_Q": ds["class_counts"], "designs": {}}
    for name, r in ds["designs"].items():
        e = {}
        for scope in ("NSV_only", "all_beats"):
            e[scope] = {}
            for c in ("V", "S"):
                x = r[scope][c]
                e[scope][c] = {"sensitivity": rate(x["TP"], x["P"]), "ppv": rate(x["TP"], x["PP"])}
            e[scope]["accuracy_3class"] = r[scope]["accuracy_3class"]
        rec = r["per_record"]
        for c in ("V", "S"):
            cand = [k for k in rec if rec[k][c]["P"] >= 20]
            w = min(cand, key=lambda k: rec[k][c]["TP"] / rec[k][c]["P"])
            e[f"worst_record_{c}_sens"] = {"record": int(w), **rate(rec[w][c]["TP"], rec[w][c]["P"])}
            rng = np.random.default_rng(0)
            keys = list(rec)
            bs = []
            for _ in range(2000):
                pick = rng.choice(keys, len(keys), replace=True)
                tp = sum(rec[k][c]["TP"] for k in pick); p = sum(rec[k][c]["P"] for k in pick); pp = sum(rec[k][c]["PP"] for k in pick)
                bs.append((tp / p if p else np.nan, tp / pp if pp else np.nan))
            bs = np.asarray(bs)
            e[f"record_bootstrap_{c}"] = {"sens95": np.nanpercentile(bs[:, 0], [2.5, 97.5]).tolist(), "ppv95": np.nanpercentile(bs[:, 1], [2.5, 97.5]).tolist()}
        e["V_info"], e["S_info"] = r["V_info"], r["S_info"]
        out["designs"][name] = e
    return out


def main(run: Path, archive_p: Path, lists: Path, chip_p: Path, ds_p: Path, out: Path) -> None:
    folds = sorted((json.loads(p.read_text()) for p in run.glob("fold[0-9][0-9].json")), key=lambda f: f["fold"])
    rf = [f for f in folds if f["refs"]]
    archive_raw = json.loads(archive_p.read_text())
    archive = {f["fold"]: f for f in archive_raw["folds"]}
    res = {
        "baseline": BASELINE,
        "baseline_archive_cv": {k: v for k, v in archive_raw.items() if k != "folds"},
        "protocol_check": check_counts(folds, lists),
        "n_folds_run": len(folds),
        "headline_rule": "threshold fixed on validation patients at specificity >= 0.999",
        "designs": {k: summarize_design(folds, k, "designs", archive) for k in folds[0]["designs"]},
        "references_float_not_chips": {k: summarize_design(rf, k, "refs", archive) for k in rf[0]["refs"]} if rf else {},
    }
    if chip_p.exists():
        res["chips_fold18"] = chip_table(json.loads(chip_p.read_text()))
    if ds_p.exists():
        res["inter_patient_DS1_DS2"] = ds_table(json.loads(ds_p.read_text()))
    out.write_text(json.dumps(res, indent=1))
    for k, v in res["designs"].items():
        e = v["rules"][RULE]
        f18 = e.get("fold18_published_split", {})
        print(k, "f18", f18.get("sensitivity", {}).get("k"), f18.get("FP"), "pooled", e["pooled_all_folds"]["sensitivity"]["k"], e["pooled_all_folds"]["sensitivity"]["n"], round(e["pooled_all_folds"]["specificity"]["rate"], 4), "h2h", e["head_to_head_vs_coin_archive"])


if __name__ == "__main__":
    main(*(Path(a) for a in sys.argv[1:7]))
