"""Collect designs.json (accuracy) and chip_results.json (lab numbers) into a small results.json and print the
size-against-accuracy table in markdown.

Run with: python -I summarize.py <designs dir> <out results.json>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BASELINES = {
    "apdet_reference_rule": {
        "what": "PhysioNet apdet (Mietus et al., CinC 2000): hand-set thresholds on Hilbert amplitude and "
                "frequency of the NN series, RR only, no learning",
        "source": "https://archive.physionet.org/physiotools/apdet/",
        "test_minute": "14591 of 17268 (84.5 percent; challenge table 84.49)",
        "test_A_vs_C": "28 of 30", "learning_minute": "13895 of 17045 (82.1 percent)",
        "learning_A_vs_C": "26 of 30"},
    "challenge_2000_top": {
        "what": "CinC Challenge 2000 best entries; several entries per team scored on the test set",
        "source": "https://physionet.org/content/challenge-2000/1.0.0/",
        "test_minute": "McNames et al. 15994 of 17268 (92.62); de Chazal et al. 15432 of 17268 (89.36)",
        "test_A_vs_C": "30 of 30 (four teams)"},
    "song_2016_hmm_svm": {
        "what": "Song et al., IEEE TBME 63(7) 2016, hand-crafted ECG and EDR features, discriminative HMM",
        "source": "https://doi.org/10.1109/TBME.2015.2498199",
        "test_minute": "86.2 percent", "test_ahi5": "97.1 percent (34 of 35)"},
    "sharma_2016_lssvm": {
        "what": "Sharma and Sharma, Comput Biol Med 77 2016, Hermite QRS-shape + RR features, LS-SVM / SVM",
        "source": "https://doi.org/10.1016/j.compbiomed.2016.08.012",
        "test_minute": "about 84 percent (83.8 in Chang 2020 Table 5)", "test_ahi5": "97.14 percent"},
    "chang_2020_1dcnn": {
        "what": "Chang et al., Sensors 20(15) 4157, 2020, 1D CNN on raw ECG minutes",
        "source": "https://doi.org/10.3390/s20154157",
        "test_minute": "87.9 percent (of 17234 minutes)", "test_ahi5": "97.1 percent (34 of 35)"},
}


def main() -> None:
    ddir, outp = Path(sys.argv[1]), Path(sys.argv[2])
    des = json.loads((ddir / "designs.json").read_text())
    chip = json.loads((ddir / "chip_results.json").read_text()) if (ddir / "chip_results.json").exists() else {}
    rows = []
    out = {"database": "PhysioNet Apnea-ECG 1.0.0 (ODC-By 1.0), 35 learning / 35 test records",
           "baselines": BASELINES, "designs": {}}
    for tag, d in des["designs"].items():
        te, cv = d.get("test", {}), d["train_cv"]
        c = chip.get(tag, {})
        mn, nc, ck = c.get("minute", {}), c.get("night_core", {}), c.get("night_clocked", {})
        item = {
            "features": d.get("feat_names", "all context features"),
            "model": {k: v for k, v in (d.get("model") or {}).items() if k not in ("lo", "step")},
            "night_rule": f"OSA if {d['night_k']} x positive minutes >= minutes",
            "train_cv": {"minute_acc": cv["minute"]["acc"], "night": f"{cv['night_ahi5']['correct']} of 35",
                         "A_vs_C": f"{cv['challenge_event1_A_vs_C']['correct']} of 30"},
            "test": {"minute": f"{te['minute']['correct']} of {te['minute']['n']}",
                     "minute_acc": te["minute"]["acc"],
                     "minute_wilson95": te["minute"]["acc_wilson95"],
                     "minute_subject_bootstrap95": te["minute"]["acc_subject_bootstrap95"],
                     "minute_sens": te["minute"]["sens"], "minute_spec": te["minute"]["spec"],
                     "night_ahi5": f"{te['night_ahi5']['correct']} of 35",
                     "night_wilson95": te["night_ahi5"]["wilson95"],
                     "night_sens": te["night_ahi5"]["sens"], "night_spec": te["night_ahi5"]["spec"],
                     "night_errors": te["night_ahi5"]["errors"],
                     "night_k12": f"{d['test_k12']['correct']} of 35",
                     "A_vs_C": f"{te['challenge_event1_A_vs_C']['correct']} of 30",
                     "A_vs_C_errors": te["challenge_event1_A_vs_C"]["errors"],
                     "worst_subject": te["worst_subject"]} if te else None,
        }
        if mn:
            item["chip"] = {
                "minute_classifier": {"design_id": mn.get("design_id"), **{k: mn.get("synth", {}).get(k) for k in
                                      ("gates", "depth", "transistors_est")},
                                      "ge": {p: mn["map"][p].get("gate_equivalents") for p in mn.get("map", {})},
                                      "area_um2": {p: mn["map"][p].get("area_um2") for p in mn.get("map", {})},
                                      "bit_exact_test": (mn.get("simulate_test_vectors") or {}).get("bit_exact"),
                                      "proved": (mn.get("prove_equivalence") or {}).get("proved"),
                                      "verification_level": mn.get("verification_level")},
                "night_core": {"design_id": nc.get("design_id"), **{k: nc.get("synth", {}).get(k) for k in
                               ("gates", "depth")},
                               "bit_exact_test": (nc.get("simulate_test_vectors") or {}).get("bit_exact"),
                               "proved": (nc.get("prove_equivalence") or {}).get("proved")},
                "night_clocked": {"gates": (ck.get("generic") or {}).get("gates"),
                                  "depth": (ck.get("generic") or {}).get("depth"),
                                  "flip_flops": sum(v for k, v in ((ck.get("generic") or {}).get("cells_by_type") or {}).items()
                                                    if "DFF" in k),
                                  "ge": {p: (ck.get(p) or {}).get("gate_equivalents") for p in ("sky130", "gf180", "ihp")},
                                  "area_um2": {p: (ck.get(p) or {}).get("area_um2") for p in ("sky130", "gf180", "ihp")},
                                  "seq_proof_compositional": (ck.get("prove_sequential_compositional") or {}).get("proved"),
                                  "seq_proof_whole": (ck.get("prove_sequential_whole") or {}).get("proved"),
                                  "icarus_all_test_nights": c.get("night_clocked_sim")},
            }
        out["designs"][tag] = item
        if te:
            ch = item.get("chip", {})
            rows.append((tag, ch.get("minute_classifier", {}).get("gates"), ch.get("night_clocked", {}).get("gates"),
                         ch.get("night_clocked", {}).get("flip_flops"),
                         (ch.get("night_clocked", {}).get("ge") or {}).get("sky130"),
                         item["test"]["minute"], round(100 * item["test"]["minute_acc"], 2),
                         item["test"]["night_ahi5"], item["test"]["A_vs_C"]))
    outp.write_text(json.dumps(out, indent=1))
    print("| design | min gates | night gates | FF | sky130 GE | minutes | % | AHI5 | A/C |")
    print("|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        print("| " + " | ".join(str(v) for v in r) + " |")


if __name__ == "__main__":
    main()
