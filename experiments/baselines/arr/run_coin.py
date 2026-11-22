"""The baseline's protocol: Monte Carlo rounds with the baseline's own released patient lists
(train / val / test per round, flexwnn cv_almost_2023-05-04), binary normal (AAMI N incl. '+')
vs abnormal (S, V, F, Q incl. paced), per-beat sensitivity and specificity on the round's test
patients. Round 18 is the split of the published chip (test patients 107, 213, 209).

Operating threshold: fixed on the round's validation patients only. Headline rule (set before
any test result was seen): specificity >= 0.999 on validation normals. The ladder 0.99, 0.995,
0.998 is also recorded so the whole trade-off is visible.

Usage: python -I run_coin.py <beats.npz> <baseline cv lists dir> <out dir> <workers> <folds|all>
"""

from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier

import designs as D
from arrlib import N_SAMP, load_beats, ratio_feats, run_ir, threshold_for_spec

N_FOLDS = 50
TRAIN_NORMAL_CAP = 20000
TEST_SPEC = 0.998
VAL_SPECS = (0.999, 0.998, 0.995, 0.99)  # first = headline rule

BASE = np.arange(D.N_BASE)  # exactly the baseline chip's 372 input bits
MORPH = np.arange(D.N_BITS)  # baseline bits + 7-level thermometer of the same samples
EXT = np.arange(D.N_BITS + len(D.RR_GRID))  # + RR-ratio indicator bits
RRONLY = np.arange(D.N_BITS, D.N_BITS + len(D.RR_GRID))

DESIGNS: list[tuple[str, str, callable]] = [
    ("S1_width", "strict", lambda tr: D.fit_width(tr, "S1_width")),
    ("S2_tree_d5", "strict", lambda tr: D.fit_tree(tr, "S2_tree_d5", 5, BASE)),
    ("S3_lin64", "strict", lambda tr: D.fit_linear(tr, "S3_lin64", 64, BASE)),
    ("S4_gbdt48", "strict", lambda tr: D.fit_gbdt(tr, "S4_gbdt48", 48, BASE)),
    ("Q1_tree_d4", "finer_quant", lambda tr: D.fit_tree(tr, "Q1_tree_d4", 4, MORPH)),
    ("Q2_lin32", "finer_quant", lambda tr: D.fit_linear(tr, "Q2_lin32", 32, MORPH)),
    ("Q3_gbdt16", "finer_quant", lambda tr: D.fit_gbdt(tr, "Q3_gbdt16", 16, MORPH)),
    ("Q4_gbdt48", "finer_quant", lambda tr: D.fit_gbdt(tr, "Q4_gbdt48", 48, MORPH)),
    ("E1_rr_tree_d3", "rr_only", lambda tr: D.fit_tree(tr, "E1_rr_tree_d3", 3, RRONLY)),
    ("E2_tree_d4", "extended", lambda tr: D.fit_tree(tr, "E2_tree_d4", 4, EXT)),
    ("E3_lin32", "extended", lambda tr: D.fit_linear(tr, "E3_lin32", 32, EXT)),
    ("E4_gbdt16", "extended", lambda tr: D.fit_gbdt(tr, "E4_gbdt16", 16, EXT)),
    ("E5_gbdt48", "extended", lambda tr: D.fit_gbdt(tr, "E5_gbdt48", 48, EXT)),
]


def read_folds(lists: Path) -> list[dict]:
    out = []
    for f in range(N_FOLDS):
        g = {k: [int(x) for x in (lists / f"{k}_{f:02d}.txt").read_text().split()] for k in ("train", "val", "test")}
        out.append({"fold": f, **g})
    return out


def counts(pred: np.ndarray, y: np.ndarray, rec: np.ndarray) -> dict:
    per = {}
    for r in np.unique(rec):
        m = rec == r
        per[int(r)] = {
            "TP": int(((pred == 1) & (y == 1) & m).sum()),
            "P": int(((y == 1) & m).sum()),
            "TN": int(((pred == 0) & (y == 0) & m).sum()),
            "N": int(((y == 0) & m).sum()),
        }
    tot = {k: sum(v[k] for v in per.values()) for k in ("TP", "P", "TN", "N")}
    return {**tot, "per_patient": per}


def oracle_sens(score: np.ndarray, y: np.ndarray) -> float:
    """Diagnostic only (uses test labels): sensitivity at the test threshold giving spec >= 0.998."""
    t = threshold_for_spec(score[y == 0], TEST_SPEC)
    return float((score[y == 1] > t).mean())


def run_fold(args: tuple) -> dict:
    beats_path, fold = args
    B = load_beats(Path(beats_path))
    bits = B.bits
    Xfull = np.concatenate([bits, D.rr_bits(B.rr)], axis=1)
    y = (B.y5 > 0).astype(np.int64)
    rng = np.random.default_rng(1000 + fold["fold"])
    va_m = np.isin(B.rec, fold["val"])
    te_m = np.isin(B.rec, fold["test"])
    tr_idx = np.flatnonzero(np.isin(B.rec, fold["train"]))
    norm = tr_idx[y[tr_idx] == 0]
    if len(norm) > TRAIN_NORMAL_CAP:
        tr_idx = np.setdiff1d(tr_idx, rng.choice(norm, len(norm) - TRAIN_NORMAL_CAP, replace=False))
    tr = D.Data(Xfull[tr_idx], y[tr_idx], D.balanced_weights(y[tr_idx]))
    Xva, yva = Xfull[va_m], y[va_m]
    yte, rte = y[te_m], B.rec[te_m]
    res = {
        "fold": fold["fold"],
        "test": fold["test"],
        "class_counts_test": np.bincount(B.y5[te_m], minlength=5).tolist(),
        "class_counts_val": np.bincount(B.y5[va_m], minlength=5).tolist(),
        "designs": {},
        "refs": {},
    }
    irs = {}
    for name, track, fit in DESIGNS:
        t0 = time.time()
        probe = fit(tr)
        sva = D.eval_ir(probe, Xva, node="score")
        entry = {"track": track, "fit_s": None, "rules": {}}
        for vs in VAL_SPECS:
            t = threshold_for_spec(sva[yva == 0], vs)
            ir = D.finalize(probe, t)
            pred = run_ir(ir, bits[te_m], B.rr[te_m])["y"][:, 0]
            assert np.array_equal(pred, D.eval_ir(ir, Xfull[te_m])), name
            entry["rules"][str(vs)] = {
                "threshold": t,
                **counts(pred, yte, rte),
                "n_bit_inputs": len(ir["meta"]["bit_features"]),
                "n_rr_bits": len(ir["meta"]["rr_feature_idx"]),
            }
            if vs == VAL_SPECS[0]:
                irs[name] = ir
        entry["oracle_sens_at_spec0998"] = oracle_sens(D.eval_ir(probe, Xfull[te_m], node="score"), yte)
        entry["fit_s"] = round(time.time() - t0, 1)
        res["designs"][name] = entry
    # float references (not chips): what the inputs allow at all
    xs = B.x16[:, :N_SAMP].astype(np.float32) / 65535
    refs = {
        "R1_hgb_samples": xs,
        "R2_hgb_baseline_bits": bits[:, : D.N_BASE].astype(np.float32),
        "R3_hgb_samples_rr": np.concatenate([xs, ratio_feats(B.rr)], axis=1),
    }
    for name, X in refs.items():
        clf = HistGradientBoostingClassifier(max_iter=100, early_stopping=False, random_state=0)
        clf.fit(X[tr_idx], y[tr_idx], sample_weight=D.balanced_weights(y[tr_idx]))
        sv, st = clf.decision_function(X[va_m]), clf.decision_function(X[te_m])
        entry = {"rules": {}, "oracle_sens_at_spec0998": oracle_sens(st, yte)}
        for vs in VAL_SPECS:
            neg = np.sort(sv[yva == 0])[::-1]
            t = float(neg[int(np.floor((1 - vs) * len(neg)))])
            entry["rules"][str(vs)] = counts((st > t).astype(np.int64), yte, rte)
        res["refs"][name] = entry
    return {"res": res, "irs": irs}


def main(beats: Path, lists: Path, out: Path, workers: int, which: str) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "irs").mkdir(exist_ok=True)
    folds = read_folds(lists)
    (out / "folds.json").write_text(json.dumps(folds))
    sel = folds if which == "all" else [folds[int(i)] for i in which.split(",")]
    sel = [f for f in sel if not (out / f"fold{f['fold']:02d}.json").exists()]
    with ProcessPoolExecutor(workers) as ex:
        for r in ex.map(run_fold, [(str(beats), f) for f in sel]):
            f = r["res"]["fold"]
            (out / "irs" / f"fold{f:02d}.json").write_text(json.dumps(r["irs"]))
            (out / f"fold{f:02d}.json").write_text(json.dumps(r["res"]))
            h = {k: v["rules"][str(VAL_SPECS[0])] for k, v in r["res"]["designs"].items()}
            print(f, {k: (v["TP"], v["P"], v["TN"], v["N"]) for k, v in h.items()}, flush=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), int(sys.argv[4]), sys.argv[5])
