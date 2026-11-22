"""Write the small results.json from summarize.py's full output plus the DS2 chip-lab results.

Usage: python -I compact_results.py <results_full.json> <ds chip json> <wrapper flops json> <out results.json>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RULE = "0.999"
DFF_GE_SKY130 = 20.0192 / 3.7536  # sky130_fd_sc_hd dfxtp_1 area / nand2_1 area


def r4(x: float | None) -> float | None:
    return None if x is None else round(x, 4)


def rate(e: dict) -> str:
    lo, hi = e["wilson95"]
    return f"{e['k']}/{e['n']} = {r4(e['rate'])} [{r4(lo)}, {r4(hi)}]"


def chip(c: dict | None) -> dict | None:
    if c is None:
        return None
    return {
        "generic_gates": c["generic_gates"],
        "logic_depth": c["logic_depth"],
        "GE_sky130_gf180_ihp": [c["gate_equivalents"].get(p) for p in ("sky130", "gf180", "ihp")],
        "area_um2_sky130_gf180_ihp": [c["area_um2"].get(p) for p in ("sky130", "gf180", "ihp")],
        "bit_exact_on_test_beats": f"{c['bit_exact_test_vectors']} ({c['n_test_vectors']} vectors)",
        "bit_exact_random_100k": c["bit_exact_random_100k"],
        "formal_proof": c["proof"].get("proved"),
        "verification_level": c["verification_level"],
    }


def main(full_p: Path, ds_chip_p: Path, wrap_p: Path, out: Path) -> None:
    F = json.loads(full_p.read_text())
    chips = F.get("chips_fold18", {})
    wraps = json.loads(wrap_p.read_text())
    res: dict = {
        "baseline": F["baseline"],
        "baseline_own_released_cv_runs": F["baseline_archive_cv"],
        "protocol_check": F["protocol_check"],
        "headline_rule": F["headline_rule"],
        "fold18_published_split": {},
        "all_50_folds": {},
        "references_float_not_chips": {},
    }
    for k, d in F["designs"].items():
        e = d["rules"][RULE]
        f18 = e["fold18_published_split"]
        res["fold18_published_split"][k] = {
            "track": d["track"],
            "sensitivity": rate(f18["sensitivity"]),
            "specificity": rate(f18["specificity"]),
            "false_positives": f18["FP"],
            "per_patient_TP_P_FP": {p: [c["TP"], c["P"], c["N"] - c["TN"]] for p, c in f18["per_patient"].items()},
            "threshold_ladder_TP_FP": {
                rule: [d["rules"][rule]["fold18_published_split"]["sensitivity"]["k"], d["rules"][rule]["fold18_published_split"]["FP"]]
                for rule in d["rules"]
            },
            "beats_baseline_at_headline_rule": f18["beats_baseline"],
            "chip": chip(chips.get(f"fold18_{k}")),
            "chip_inputs": d.get("n_bit_inputs_fold18"),
        }
        if k in wraps:
            w = wraps[k]
            res["fold18_published_split"][k]["streaming_wrapper"] = {
                "flip_flops": w,
                "estimated_total_GE_sky130": round(chips[f"fold18_{k}"]["gate_equivalents"]["sky130"] + w * DFF_GE_SKY130, 1),
                "note": "estimate: combinational GE + flip-flops x dfxtp_1 area in NAND2 units; wrapper glue logic excluded; no layout",
            }
        p = e["pooled_all_folds"]
        res["all_50_folds"][k] = {
            "sensitivity_pooled": rate(p["sensitivity"]),
            "specificity_pooled": rate(p["specificity"]),
            "patient_bootstrap_95": {kk: [r4(x) for x in v] for kk, v in p["patient_bootstrap"].items()},
            "mean_fold_sens_spec": [r4(e["mean_fold_sensitivity"]), r4(e["mean_fold_specificity"])],
            "folds_spec_ge_0998": e["folds_spec_ge_0998"],
            "folds_spec_ge_0998_and_sens_gt_06862": e["folds_spec_ge_0998_and_sens_gt_06862"],
            "head_to_head_vs_baseline_runs": e["head_to_head_vs_coin_archive"],
            "worst_patient_sensitivity": e["worst_patient_sensitivity"],
            "most_false_positives": e["most_false_positives"],
            "oracle_mean_sens_at_test_spec0998_DIAGNOSTIC_uses_test_labels": r4(d["oracle_mean_sens_at_test_spec0998_DIAGNOSTIC"]),
        }
    for k, d in F["references_float_not_chips"].items():
        e = d["rules"][RULE]
        f18 = e["fold18_published_split"]
        res["references_float_not_chips"][k] = {
            "fold18_sensitivity": rate(f18["sensitivity"]),
            "fold18_FP": f18["FP"],
            "pooled_6_folds_sensitivity": rate(e["pooled_all_folds"]["sensitivity"]),
            "pooled_6_folds_specificity": rate(e["pooled_all_folds"]["specificity"]),
        }
    ds = F["inter_patient_DS1_DS2"]
    dsc = json.loads(ds_chip_p.read_text()) if ds_chip_p.exists() else {}
    res["inter_patient_DS1_DS2"] = {
        "baseline": {
            "source": "Sensors 2023, 23(3), 1365, doi 10.3390/s23031365, https://pmc.ncbi.nlm.nih.gov/articles/PMC9919183/ (Model 6)",
            "parameters": 1267,
            "VEB_sens_ppv": [95.00, 95.63],
            "SVEB_sens_ppv": [81.60, 82.68],
            "accuracy": 98.18,
            "runs_on": "cloud and Raspberry Pi (software), not a chip",
        },
        "class_counts_N_S_V_F_Q": ds["class_counts_N_S_V_F_Q"],
        "designs": {},
    }
    for k, e in ds["designs"].items():
        ge = []
        for h in ("V", "S"):
            c = dsc.get(f"DS2_{k}_{h}", {})
            m = c.get("map", {}).get("sky130", {}).get("metrics", {})
            ge.append({"gates": c.get("synth", {}).get("metrics", {}).get("gates"), "GE_sky130": m.get("gate_equivalents"), "bit_exact": c.get("sim", {}).get("bit_exact"), "proved": c.get("proof", {}).get("proved")})
        n = e["NSV_only"]
        res["inter_patient_DS1_DS2"]["designs"][k] = {
            "V_sensitivity": rate(n["V"]["sensitivity"]),
            "V_ppv": rate(n["V"]["ppv"]) if n["V"]["ppv"]["n"] else None,
            "S_sensitivity": rate(n["S"]["sensitivity"]),
            "S_ppv": rate(n["S"]["ppv"]) if n["S"]["ppv"]["n"] else None,
            "accuracy_3class": r4(n["accuracy_3class"]),
            "record_bootstrap_95": {"V": e["record_bootstrap_V"], "S": e["record_bootstrap_S"]},
            "worst_record_V": e["worst_record_V_sens"],
            "worst_record_S": e["worst_record_S_sens"],
            "chips_V_S": ge,
        }
    out.write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(*(Path(a) for a in sys.argv[1:5]))
