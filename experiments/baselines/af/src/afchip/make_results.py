"""Collect evaluation and chip-lab outputs into a small results.json and a size-against-accuracy table.

Usage: python -I -m afchip.make_results --work <dir with eval2_n*/, eval_n*/, chip_v2/> --dest <experiment dir>
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

WINDOWS = (16, 32, 64, 128)
FAMS = ("thr1", "and2", "tree3", "lin", "mlp4")
REFS = ("dash2009_fixed_float", "ref_logreg_float", "ref_gbdt_float")

BASELINES = {
    "andersson2015_asic": {
        "source": "https://biosignal.uconn.edu/wp-content/uploads/sites/2503/2018/09/11_Andersson_2015_TBCS.pdf",
        "database": "MIT-BIH AF database, same records as Dash 2009 (Table I, III)",
        "sens": 0.949, "spec": 0.958, "config": "PrecSeg, N=128 (Table II, III)",
        "protocol": "thresholds grid-searched on the same databases; no held-out subjects; no interval reported",
        "nand2_eq_65nm_synthesis": 24038, "area_um2_65nm_synthesis": 50000, "silicon_area_mm2": 0.10,
        "on_chip": "ectopic preprocessing, TPR, RMSSD, Shannon entropy, log2, shared multiplier, thresholds, 1664-bit RAM",
        "off_chip": "R-wave detection and RR interval computation",
    },
    "dash2009_algorithm": {
        "source": "https://biosignal.uconn.edu/wp-content/uploads/sites/2503/2018/09/10_Dash_2009_AnnalsBME.pdf",
        "sens": 0.944, "spec": 0.951, "database": "MIT-BIH AF database minus 04936 and 05091",
        "protocol": "128-beat segments, AF if more than 50% AF beats; thresholds optimised on the same database",
    },
    "cinotti2025_int8_cnn": {
        "source": "https://pmc.ncbi.nlm.nih.gov/articles/PMC12694393/",
        "tp_tn_rates": {"25": [0.971, 0.953], "50": [0.980, 0.969], "100": [0.974, 0.983]},
        "protocol": "23 AFDB subjects, 5-fold subject-wise; other arrhythmias removed; sinus windows undersampled",
    },
    "fda_den180044_goals": {
        "source": "https://www.accessdata.fda.gov/cdrh_docs/reviews/DEN180044.pdf",
        "sens_goal": 0.90, "spec_goal": 0.92, "task": "30 s single-lead ECG strip vs 12-lead reference",
    },
}


def _short(s: dict) -> dict:
    out = {}
    for c in ("sens", "spec"):
        v = s[c]
        out[c] = {"k": v["k"], "n": v["n"], "value": round(v["value"], 4),
                  "wilson95": [round(x, 4) for x in v["wilson95"]],
                  "subject_boot95": [round(x, 4) for x in v["subject_boot95"]],
                  "worst_subject": v["worst_subject"], "worst_subject_min10": v.get("worst_subject_min10")}
    il = s["interval_level"]
    out["interval_level"] = {c: {"k": il[c][0], "n": il[c][1], "value": round(il[c][2], 4)} for c in ("sens", "spec")}
    return out


def _chip(d: Path) -> dict | None:
    f = d / "summary.json"
    if not f.exists():
        return None
    r = json.loads(f.read_text())
    sm = r.get("synth", {}).get("metrics", {})
    out = {"design_id": r.get("design_id"), "gates": sm.get("gates"), "depth": sm.get("depth"),
           "cells_by_type": r.get("synth", {}).get("cells_by_type")}
    out["core_map"] = {p: r["map"][p].get("metrics") for p in r.get("map", {})}
    out["sequential_map"] = {p: {k: v.get(k) for k in ("area_um2", "gate_equivalents", "std_cells", "flip_flops")}
                             for p, v in r.get("seqmap", {}).items()}
    out["bit_exact"] = {db: {"bit_exact": v.get("bit_exact"),
                             **v.get("pairs", {}).get("circuit_vs_integer_model[af]", {}),
                             "training_model_pair": v.get("pairs", {}).get("circuit_vs_training_model")}
                        for db, v in r.get("sim", {}).items()}
    pv = r.get("prove", {})
    out["formal"] = {"proved": pv.get("proved"), "method": pv.get("method"), "against": pv.get("against"),
                     "verification_level": pv.get("verification_level"), "status": pv.get("status")}
    ps = r.get("prove_seq", {})
    out["formal_sequential"] = {"proved": ps.get("proved"), "scope": ps.get("scope"), "status": ps.get("status")}
    rs = r.get("rtl_sim", {})
    out["rtl_sim"] = {k: rs.get(k) for k in ("status", "n", "mismatches", "lint", "verification_level") if k in rs}
    out["ice40_luts"] = r.get("bitstream", {}).get("metrics", {}).get("luts")
    out["verification_level"] = r.get("vlevel", {}).get("level", r.get("vlevel", {}).get("verification_level"))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--dest", type=Path, required=True)
    a = ap.parse_args()
    res: dict = {"baselines": BASELINES, "v2": {}, "v1": {}, "references": {}}
    models: dict = {}
    for n in WINDOWS:
        f2 = a.work / f"eval2_n{n}" / "eval_full.json"
        if f2.exists():
            run = json.loads(f2.read_text())["runs"][str(n)]
            res.setdefault("windows", {})[str(n)] = {k: run[k] for k in ("afdb_windows", "afdb_af_windows", "ltafdb_windows", "ltafdb_af_windows")}
            fm = json.loads((a.work / f"eval2_n{n}" / "final_models.json").read_text())
            for fam in FAMS:
                key = f"{fam}_n{n}"
                models[key] = fm[key]
                res["v2"][key] = {"afdb_loso": _short(run["afdb_loso"][fam]), "ltafdb_cross": _short(run["ltafdb_cross"][fam]),
                                  "chip": _chip(a.work / "chip_v2" / key)}
            for ref in REFS:
                res["references"][f"{ref}_n{n}"] = {"afdb_loso": _short(run["afdb_loso"][ref]),
                                                    "ltafdb_cross": _short(run["ltafdb_cross"][ref])}
        f1 = a.work / f"eval_n{n}" / "eval_full.json"
        if f1.exists():
            run = json.loads(f1.read_text())["runs"][str(n)]
            for fam in FAMS:
                s, t = run["afdb_loso"][fam], run["ltafdb_cross"][fam]
                res["v1"][f"{fam}_n{n}"] = {"afdb_loso": {c: [s[c]["k"], s[c]["n"]] for c in ("sens", "spec")},
                                            "ltafdb_cross": {c: [t[c]["k"], t[c]["n"]] for c in ("sens", "spec")}}
    (a.dest / "results.json").write_text(json.dumps(res, indent=1))
    (a.dest / "models").mkdir(exist_ok=True)
    (a.dest / "models" / "final_models_v2.json").write_text(json.dumps(models, indent=1))
    # size-against-accuracy table (markdown rows, short cells)
    rows = ["| design | gates | depth | GE sky130 | FF | AFDB Se | AFDB Sp | LTAF Se | LTAF Sp |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for key, v in sorted(res["v2"].items(), key=lambda kv: ((kv[1]["chip"] or {}).get("gates") or 0)):
        c = v["chip"] or {}
        ge = (c.get("core_map", {}).get("sky130") or {}).get("gate_equivalents")
        ff = (c.get("sequential_map", {}).get("sky130") or {}).get("flip_flops")
        s, t = v["afdb_loso"], v["ltafdb_cross"]
        rows.append(f"| {key} | {c.get('gates')} | {c.get('depth')} | {ge} | {ff} | "
                    f"{s['sens']['k']}/{s['sens']['n']} | {s['spec']['k']}/{s['spec']['n']} | "
                    f"{t['sens']['value']:.3f} | {t['spec']['value']:.3f} |")
    (a.dest / "size_accuracy_table.md").write_text("\n".join(rows) + "\n")
    print("\n".join(rows))


if __name__ == "__main__":
    main()
