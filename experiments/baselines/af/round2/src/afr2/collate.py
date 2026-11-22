"""Collate round two into round2/results.json: counts, intervals, subject ids and counts only (no per-segment or
per-interval arrays).

Usage: python -I -m afr2.collate --runs RUNS_DIR --out FILE --protocol-commit HASH
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from afr2.fit import FAMILIES
from afr2.stats2 import BASE_SE, BASE_SP, wording

CONFIGS = [("23", 128), ("25", 128), ("23", 64), ("25", 64), ("23", 32), ("25", 32)]


def rnd(x, d: int = 4):
    if isinstance(x, float):
        return round(x, d)
    if isinstance(x, list):
        return [rnd(v, d) for v in x]
    if isinstance(x, dict):
        return {k: rnd(v, d) for k, v in x.items()}
    return x


def slim(s: dict) -> dict:
    """Summary without per-segment data; adds the per-subject mean over subjects with >= 10 segments."""
    out = {}
    ps = s.get("per_subject", {})
    for c, (k, n) in (("sens", ("tp", "pos")), ("spec", ("tn", "neg"))):
        v = dict(s[c])
        r10 = [p[k] / p[n] for p in ps.values() if p[n] >= 10]
        v["per_subject_mean_min10"] = float(np.mean(r10)) if r10 else None
        v["subjects_min10"] = len(r10)
        out[c] = v
    if "interval_level" in s:
        out["interval_level"] = s["interval_level"]
    if ps:
        out["per_subject_counts"] = ps
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--protocol-commit", required=True)
    a = ap.parse_args()
    res: dict = {"protocol_commit": a.protocol_commit,
                 "baseline": {"source": "Andersson et al. 2015, IEEE TBioCAS 9(3), Table III, PrecSeg",
                              "sens": BASE_SE, "spec": BASE_SP, "nand2_eq_65nm_synthesis": 24038},
                 "nested": {}}
    for recs, n in CONFIGS:
        f = a.runs / f"nested_{recs}_{n}" / "nested.json"
        if not f.exists():
            continue
        d = json.loads(f.read_text())
        nest = d["nested"]
        chosen = d["chosen_per_fold"]
        res["nested"][f"{recs}rec_n{n}"] = {
            "config": d["config"],
            "nested": slim(nest),
            "wording_vs_published": wording(nest),
            "chosen_family_counts": {fam: sum(v == fam for v in chosen.values()) for fam in FAMILIES if fam in chosen.values()},
            "chosen_per_fold": chosen,
            "models_per_fold": d["models_per_fold"],
            "final_design_fit_on_all_subjects": d["final"]["model"],
            "final_design_inner_loso": d["final"]["inner"],
            "per_family_loso_descriptive_only": {fam: {c: {k: v[c][k] for k in ("k", "n", "wilson95", "subject_boot95")}
                                                       for c in ("sens", "spec")}
                                                 for fam, v in d["per_family_loso_descriptive"].items()},
        }
    for name in ("untouched", "r1fix"):
        f = a.runs / f"{name}.json"
        if f.exists():
            d = json.loads(f.read_text())
            if name == "untouched":
                for db in ("mitdb", "ltafdb"):
                    for k, v in list(d[db].items()):
                        if isinstance(v, dict) and "sens" in v:
                            d[db][k] = slim(v)
                        elif isinstance(v, dict) and "pooled" in v:
                            d[db][k] = {part: slim(s) for part, s in v.items()}
                res["untouched_mitdb_and_secondary_ltafdb"] = d
            else:
                d["r1_and2_n128_afdb_loso_recomputed"] = slim(d["r1_and2_n128_afdb_loso_recomputed"])
                res["round1_recheck"] = d
    res["clocked_chips"] = {}
    for tag in ("r1_and2", "r2_chip"):
        f = a.runs / "chip" / tag / "seqchip.json"
        if f.exists():
            d = json.loads(f.read_text())
            c = d.get("clocked") or {}
            for p in ("sky130", "gf180", "ihp"):
                (c.get(p) or {}).pop("cells_by_type", None)
            if c.get("generic"):
                c["generic"] = {k: c["generic"].get(k) for k in ("gates", "depth", "transistors_est", "cells_by_type")}
            lay = d.get("layout_sky130") or {}
            res["clocked_chips"][tag] = {
                "model": d.get("model"), "features": d.get("features"), "n": d.get("n"),
                "core_design_id": d.get("core_design_id"), "core_ports": d.get("core_ports"),
                "core_synth": d.get("core_synth"), "core_map": d.get("core_map"),
                "core_simulate_afdb": d.get("core_simulate_afdb"), "core_simulate_random": d.get("core_simulate_random"),
                "core_prove_equivalence": d.get("core_prove_equivalence"),
                "core_verification_level": (d.get("core_verification_level") or {}).get("verification_level"),
                "clocked": c, "clocked_generic_flip_flops": d.get("clocked_generic_flip_flops"),
                "prove_sequential_whole": d.get("prove_sequential_whole"), "icarus_rtl": d.get("icarus"),
                "icarus_gate_netlist": d.get("icarus_gate_netlist"),
                "layout_sky130": {k: lay.get(k) for k in ("area_um2", "die_area_um2", "timing_ws_ns", "critical_path_ns",
                                                          "gate_equivalents_layout", "combinational", "error", "status",
                                                          "seconds")} if lay else None,
            }
    a.out.write_text(json.dumps(rnd(res), indent=1))
    print("wrote", a.out)


if __name__ == "__main__":
    main()
