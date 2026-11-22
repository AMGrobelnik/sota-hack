"""Build the dashboard's data file (dashboard/data/neonatal-eeg.json) from the pipeline and lab results, and
validate it.

usage:
  python -I -m neonatal_eeg.publish build --stage-dir DIR --out FILE [--verify verify.json]
  python -I -m neonatal_eeg.publish validate FILE
  python -I -m neonatal_eeg.publish frontier --stage-dir DIR      (prints frontier ids, for verification)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

from neonatal_eeg import scoring as S

DATASET = {
    "name": "A dataset of neonatal EEG recordings with seizure annotations (Helsinki University Hospital)",
    "licence": "CC BY 4.0",
    "url": "https://doi.org/10.5281/zenodo.4940267",
    "credit": ("Stevenson NJ, Tapani K, Lauronen L, Vanhatalo S. A dataset of neonatal EEG recordings with seizure "
               "annotations. Scientific Data 6, 190039 (2019), https://doi.org/10.1038/sdata.2019.39. Data: Zenodo, "
               "https://doi.org/10.5281/zenodo.4940267 (version 4), CC BY 4.0."),
}
MEASURED_METRICS = ["sensitivity_worst", "sensitivity_pooled", "false_alarms_per_hour", "lead_time_s"]


def nonzero_weights(ir: dict) -> int:
    return int(sum(sum(1 for w in row if w) for nd in ir["nodes"] if nd["op"] == "matvec" for row in nd["W"]))


def design_metrics(test: list[dict], min_events: int) -> dict:
    sc = [S.BabyScore(**s) for s in test]
    pb = S.pooled(sc)
    ws = S.worst_sens(sc, min_events)
    return {"metrics": {"sensitivity_worst": None if ws is None else round(ws, 4),
                        "sensitivity_pooled": round(pb["sens"], 4),
                        "false_alarms_per_hour": round(pb["fah"], 3),
                        "lead_time_s": pb["delay_med"]},
            "counts": {"events_caught": pb["caught"], "events_total": pb["total"], "hours": round(pb["hours"], 3),
                       "patients": len(sc)}}


def frontier(rows: list[dict]) -> list[str]:
    """Pareto set: fewer gates (measured, else estimated) and higher worst-baby sensitivity (ties: pooled).
    Designs that never raise an alarm (a constant output, 0 gates) are not frontier candidates."""
    pts = []
    for r in rows:
        g = r["gates"] if r["gates"] is not None else r.get("gates_est")
        if not g or r["metrics"]["sensitivity_worst"] is None:
            continue
        pts.append((g, -(r["metrics"]["sensitivity_worst"]), -r["metrics"]["sensitivity_pooled"], r["id"]))
    pts.sort()
    out, best = [], None
    for g, nw, npool, i in pts:
        q = (-nw, -npool)
        if best is None or q > best:
            out.append(i)
            best = q
    return out


def fit_gates(rows: list[dict], irs: dict) -> tuple[dict | None, str]:
    """Least squares of log(gates) on log(nonzero weights + 1) and log(input lanes) over compiled designs."""
    xs, ys = [], []
    for r in rows:
        if r["gates"]:
            ir = irs[r["id"]]
            xs.append([1.0, np.log(nonzero_weights(ir) + 1), np.log(ir["inputs"][0]["lanes"])])
            ys.append(np.log(r["gates"]))
    if len(xs) < 5:
        return None, "too few compiled designs to fit"
    X, Y = np.array(xs), np.array(ys)
    coef, *_ = np.linalg.lstsq(X, Y, rcond=None)
    err = np.exp(np.abs(X @ coef - Y)) - 1
    rule = (f"gates_est = exp({coef[0]:.3f} + {coef[1]:.3f} ln(nonzero weights + 1) + {coef[2]:.3f} ln(input lanes)), "
            f"fitted on {len(xs)} compiled designs; median error {100 * np.median(err):.0f}%, "
            f"90th percentile {100 * np.quantile(err, 0.9):.0f}%")
    return {"coef": coef.tolist()}, rule


def build(stage_dir: Path, out: Path, verify_path: Path | None) -> None:
    d = json.loads((stage_dir / "designs.json").read_text())
    lab = json.loads((stage_dir / "lab.json").read_text())
    ver = json.loads(verify_path.read_text()) if verify_path and verify_path.exists() else {}
    meta = d["meta"]
    min_ev = meta["rules"]["MIN_EVENTS"]
    # anonymous order of held-out babies (fixed shuffle, not the file numbering)
    order = np.random.default_rng(7).permutation(len(meta["split"]["test"]))
    anon = [f"H{int(k) + 1:02d}" for k in order]
    designs = [dict(x, role="design") for x in d["designs"]]
    base = d["baseline"]
    designs.append({"id": base["id"], "role": "baseline", "spec": {"channels": 1, "hidden": 0, "wmax": None},
                    "t": base["t"], "ir": base.get("ir"), "test": base["test"]})
    irs = {x["id"]: x["ir"] for x in designs if x.get("ir")}
    rows = []
    for x in designs:
        L = lab.get(x["id"], {})
        r = {"id": x["id"], "role": x["role"], "channels": x["spec"]["channels"],
             "hidden_units": x["spec"]["hidden"], "weight_levels": None if not x["spec"]["wmax"] else 2 * x["spec"]["wmax"] + 1,
             "gates": L.get("gates"), "depth": L.get("depth")}
        r.update(design_metrics(x["test"], min_ev))
        r["per_patient"] = [{"id": anon[i], "caught": s["caught"], "total": s["total"],
                             "false_alarms": s["false_alarms"], "hours": round(s["hours"], 3)}
                            for i, s in enumerate(x["test"])]
        r["per_patient"].sort(key=lambda p: p["id"])
        v = ver.get(x["id"])
        if v and v["simulate"]["exit"] in (0, 2):
            sa = v["simulate"]["answer"]
            lvl = v["level"]["answer"].get("verification_level") if v["level"]["exit"] == 0 else None
            mism = max(pr.get("mismatches", 0) for pr in sa.get("pairs", {}).values()) if sa.get("pairs") else None
            r["verified"] = {"vectors": sa.get("n"), "mismatches": mism, "level": lvl,
                             "proved_equivalent": v["prove"]["exit"] == 0}
        else:
            r["verified"] = None
        r["power_uw_est"] = None
        r["source"] = "measured"
        r["measured"] = list(MEASURED_METRICS) + (["gates", "depth"] if r["gates"] is not None else []) + \
            (["verified"] if r["verified"] else [])
        r["estimated"] = []
        rows.append(r)
    fit, rule = fit_gates(rows, irs)
    n_est = 0
    for r in rows:
        if r["gates"] is None and fit is not None and r["id"] in irs:
            ir = irs[r["id"]]
            c = fit["coef"]
            r["gates_est"] = int(round(float(np.exp(c[0] + c[1] * np.log(nonzero_weights(ir) + 1)
                                                    + c[2] * np.log(ir["inputs"][0]["lanes"])))))
            r["estimated"] = ["gates_est"]
            n_est += 1
    front = set(frontier([r for r in rows if r["role"] == "design"]))
    for r in rows:
        r["frontier"] = r["id"] in front

    sp = meta["split"]
    ev = meta["events"]
    n_compiled = sum(1 for r in rows if r["gates"] is not None)
    n_ver = sum(1 for r in rows if r["verified"])
    n_zero = sum(1 for r in rows if r["gates"] == 0)
    n_proved = sum(1 for r in rows if r["verified"] and r["verified"].get("proved_equivalent"))
    specs = [x["spec"] for x in designs if x["role"] == "design"]
    hs = sorted({sp_["hidden"] for sp_ in specs if sp_["hidden"]})
    hid = ", ".join(map(str, hs))
    lev = ", ".join(str(2 * w + 1) for w in sorted({sp_["wmax"] for sp_ in specs}))
    n_seeds = len({sp_["seed"] for sp_ in specs})
    # spread across seeds
    groups = defaultdict(list)
    for r, x in zip(rows, designs):
        if r["role"] == "design":
            groups[(x["spec"]["channels"], x["spec"]["hidden"], x["spec"]["wmax"])].append(r)
    spread_pool = [max(g["metrics"]["sensitivity_pooled"] for g in v) - min(g["metrics"]["sensitivity_pooled"] for g in v)
                   for v in groups.values() if len(v) > 1]
    spread_worst = [max(g["metrics"]["sensitivity_worst"] for g in v) - min(g["metrics"]["sensitivity_worst"] for g in v)
                    for v in groups.values() if len(v) > 1 and all(g["metrics"]["sensitivity_worst"] is not None for g in v)]
    test_ev = ev["test"]
    eligible = sum(1 for n in test_ev if n >= min_ev)
    b = next(r for r in rows if r["role"] == "baseline")
    stage_note = (f"Stage {meta['stage']}: this file uses a SUBSET of the record, babies numbered 1 to {meta['babies_used']} "
                  f"({sum(len(v) for v in sp.values())} of 79); a run on all 79 babies follows."
                  if meta["babies_used"] < 79 else
                  f"Stage {meta['stage']}: all 79 babies of the record are used; this replaces the earlier subset file.")
    doc = {
        "case": "neonatal-eeg",
        "label": "Measured on open data",
        "task": "continuous event monitoring",
        "primary": "sensitivity_worst",
        "datasets": [dict(DATASET, subjects=sum(len(v) for v in sp.values()))],
        "split": (f"Split by baby before any modelling (seeded, stratified by whether a baby has any consensus seizure): "
                  f"{len(sp['train'])} babies for training ({sum(ev['train'])} seizure events), {len(sp['val'])} for "
                  f"validation, which alone sets each design's alarm threshold ({sum(ev['val'])} events), and "
                  f"{len(sp['test'])} held out ({sum(test_ev)} events; {sum(1 for n in test_ev if n > 0)} of them have "
                  f"seizures). Held-out babies were never used for training, feature scaling, thresholds or selection."),
        "designs": rows,
        "notes": [
            stage_note,
            "Feasibility result on one hospital's recordings, not clinical evidence; no design here is a medical device.",
            "Label rule: a second is seizure when at least 2 of the 3 experts marked it. Consensus runs closer than "
            f"{S.MERGE_GAP_S} s are one event; events shorter than {S.MIN_EVENT_S} s are not scored (alarms over them do not count as false).",
            f"Event matching: an event is caught when the design's alarm is on at any decision between its onset and "
            f"its end plus {S.MARGIN_S} s. Decisions come every second at the end of an 8 s window. Alarm runs closer than "
            f"{S.REFRACTORY_S} s are merged; a merged alarm that touches no seizure (plus margin) is one false alarm.",
            f"Worst-baby sensitivity is the lowest per-baby share of events caught among held-out babies with at least "
            f"{min_ev} events: {eligible} of {len(test_ev)} held-out babies qualify, with event counts "
            f"{sorted([n for n in test_ev if n >= min_ev])}. With so few babies it rests on one baby's count.",
            f"Each design's threshold is set on the validation babies only: the best mean per-baby sensitivity with at "
            f"most {meta['rules']['FA_BUDGET']} false alarm per hour on validation; held-out false alarm rates can differ.",
            "Design: 6 integer features per channel (line length, mean absolute amplitude, zero crossings, high-frequency "
            "residual, and line length and residual relative to a causal 120 s background), 6-bit log-scaled; one tiny "
            f"network shared by the channels (a single linear unit, or {hid} hidden units with 4-bit activations), "
            f"weights of {lev} levels, {n_seeds} training seeds each; alarm when the maximum score over channels passes the threshold. "
            "Channels: 1 = C3-C4; 2 = C3-P3, C4-P4; 4 = adds T3-O1, T4-O2; 18 = double banana. Band-pass 0.5-30 Hz, 64 Hz.",
            f"Gates are from the chip lab's synthesis (simple 2-input gates) of the classifier only; the feature front end "
            f"is not included. {n_compiled} of {len(rows)} designs compiled by the lab"
            + (f"; {n_zero} of them trained to a constant output (never alarm), synthesise to 0 gates and are left "
               f"off the frontier" if n_zero else "")
            + (f"; {n_est} carry gates_est only: {rule}." if n_est else "."),
            f"Verified: {n_ver} designs (the frontier and the baseline) were checked bit for bit by the lab's simulation "
            f"on held-out windows' integer features against the integer model; {n_proved} of them were also formally "
            f"proved equal to an independent model of the design for every input (level 2).",
            "Development: the training recipe was revised once after a first stage-1 run (baby-balanced sampling, the "
            "validation threshold rule, one added feature), judged on validation figures, but that run's held-out "
            "figures had been printed in its log; nothing was selected on them afterwards.",
            f"Baseline, scored the same way: line length of C3-C4 against a threshold set on validation babies: "
            f"worst-baby {b['metrics']['sensitivity_worst']}, pooled {b['counts']['events_caught']}/{b['counts']['events_total']}, "
            f"{b['metrics']['false_alarms_per_hour']} false alarms per hour.",
            f"Spread across training seeds (same channels, size and weights): pooled sensitivity differs by a median of "
            f"{np.median(spread_pool):.2f} (max {max(spread_pool):.2f}); worst-baby sensitivity by a median of "
            f"{np.median(spread_worst):.2f} (max {max(spread_worst):.2f}).",
            "Not done: power (layout and timing tools were not run, so power_uw_est is null), other hospitals' "
            "recordings, per-channel seizure localisation, and any tuning on the held-out babies.",
        ],
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1) + "\n")
    print(f"BUILT {out} designs={len(rows)} compiled={n_compiled} verified={n_ver} estimated={n_est}")


def validate(path: Path) -> int:
    doc = json.loads(path.read_text())
    errs = []
    for k in ("case", "label", "task", "primary", "datasets", "split", "designs", "notes"):
        if k not in doc:
            errs.append(f"missing {k}")
    for ds in doc["datasets"]:
        for k in ("name", "licence", "url", "credit", "subjects"):
            if k not in ds:
                errs.append(f"dataset missing {k}")
    m = re_min_events(doc)
    for r in doc["designs"]:
        for k in ("id", "channels", "gates", "depth", "metrics", "counts", "per_patient", "verified", "power_uw_est",
                  "source", "measured", "estimated"):
            if k not in r:
                errs.append(f"{r.get('id')}: missing {k}")
        for k in MEASURED_METRICS:
            if k not in r["metrics"]:
                errs.append(f"{r['id']}: metrics missing {k}")
        pp, c = r["per_patient"], r["counts"]
        if sum(p["caught"] for p in pp) != c["events_caught"] or sum(p["total"] for p in pp) != c["events_total"]:
            errs.append(f"{r['id']}: per-patient events do not sum to counts")
        if len(pp) != c["patients"] or abs(sum(p["hours"] for p in pp) - c["hours"]) > 0.01:
            errs.append(f"{r['id']}: patients or hours do not match")
        fah = sum(p["false_alarms"] for p in pp) / sum(p["hours"] for p in pp)
        if abs(fah - r["metrics"]["false_alarms_per_hour"]) > 0.002:
            errs.append(f"{r['id']}: false alarms per hour {fah} != {r['metrics']['false_alarms_per_hour']}")
        if abs(c["events_caught"] / c["events_total"] - r["metrics"]["sensitivity_pooled"]) > 1e-4:
            errs.append(f"{r['id']}: pooled sensitivity mismatch")
        el = [p["caught"] / p["total"] for p in pp if p["total"] >= m]
        w = round(min(el), 4) if el else None
        if w != r["metrics"]["sensitivity_worst"]:
            errs.append(f"{r['id']}: worst-baby {r['metrics']['sensitivity_worst']} != recomputed {w}")
        if r["gates"] is None and r["source"] == "measured" and "gates_est" not in r:
            errs.append(f"{r['id']}: neither gates nor gates_est")
        if r["gates"] is not None and "gates_est" in r:
            errs.append(f"{r['id']}: both gates and gates_est")
        if r["verified"] is not None and r["verified"].get("mismatches") not in (0,):
            errs.append(f"{r['id']}: verified with mismatches {r['verified'].get('mismatches')}")
    text = json.dumps(doc)
    if re.search(r"/(?:Users|home)/\w", text) or re.search(r"eeg\d+\.edf", text):
        errs.append("absolute path or file name in the file")
    for e in errs:
        print("ERROR", e)
    print(f"VALIDATE {'OK' if not errs else 'FAILED'} designs={len(doc['designs'])} errors={len(errs)}")
    return 1 if errs else 0


def re_min_events(doc: dict) -> int:
    for n in doc["notes"]:
        mm = re.search(r"held-out babies with at least (\d+) events", n)
        if mm:
            return int(mm.group(1))
    raise ValueError("minimum events rule not stated in notes")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "validate", "frontier"])
    ap.add_argument("path", nargs="?", type=Path)
    ap.add_argument("--stage-dir", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--verify", type=Path)
    a = ap.parse_args()
    if a.cmd == "validate":
        return validate(a.path)
    if a.cmd == "build":
        build(a.stage_dir, a.out, a.verify)
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
