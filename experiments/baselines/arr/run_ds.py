"""Standard inter-patient protocol (de Chazal): train on DS1, test on DS2, AAMI classes,
paced records 102, 104, 107, 217 excluded. Two binary detectors per design (V vs rest, S vs rest);
class = V if the V detector fires, else S if the S detector fires, else N.

Operating thresholds are fixed on DS1 only: 5-fold record-grouped CV inside DS1 picks the
training false-positive rate that maximises out-of-fold F1; the final model (all DS1) uses the
threshold that gives that false-positive rate on its own DS1 negatives.

Usage: python -I run_ds.py <beats.npz> <out dir>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from sklearn.model_selection import GroupKFold

import designs as D
from arrlib import load_beats, run_ir, threshold_for_spec

DS1 = [101, 106, 108, 109, 112, 114, 115, 116, 118, 119, 122, 124, 201, 203, 205, 207, 208, 209, 215, 220, 223, 230]
DS2 = [100, 103, 105, 111, 113, 117, 121, 123, 200, 202, 210, 212, 213, 214, 219, 221, 222, 228, 231, 232, 233, 234]
AAMI = {**{c: 0 for c in "NLRej"}, **{c: 1 for c in "AaJS"}, **{c: 2 for c in "VE"}, "F": 3, **{c: 4 for c in "/fQ"}}
NORMAL_CAP = 20000
ALPHAS = np.geomspace(1e-4, 0.3, 40)
STRICT = np.arange(D.N_BITS)
EXT = np.arange(D.N_BITS + len(D.RR_GRID))
RRONLY = np.arange(D.N_BITS, D.N_BITS + len(D.RR_GRID))

FAMILIES = {
    "width": lambda tr, n: D.fit_width(tr, n),
    "rr_tree_d3": lambda tr, n: D.fit_tree(tr, n, 3, RRONLY),
    "tree_d4": lambda tr, n: D.fit_tree(tr, n, 4, EXT),
    "lin32": lambda tr, n: D.fit_linear(tr, n, 32, EXT),
    "gbdt16": lambda tr, n: D.fit_gbdt(tr, n, 16, EXT),
    "gbdt48": lambda tr, n: D.fit_gbdt(tr, n, 48, EXT),
}
PAIRS = {  # design -> (V family, S family)
    "DS_A_tiny": ("width", "rr_tree_d3"),
    "DS_B_tree_d4": ("tree_d4", "tree_d4"),
    "DS_C_lin32": ("lin32", "lin32"),
    "DS_D_gbdt16": ("gbdt16", "gbdt16"),
    "DS_E_gbdt48": ("gbdt48", "gbdt48"),
}


def f1(pred: np.ndarray, y: np.ndarray) -> float:
    tp = int((pred & y).sum())
    return 2 * tp / max(1, int(pred.sum()) + int(y.sum()))


def fit_detector(fam: str, X: np.ndarray, y: np.ndarray, rec: np.ndarray, name: str, seed: int) -> tuple[dict, dict]:
    rng = np.random.default_rng(seed)

    def cap(idx: np.ndarray) -> np.ndarray:
        neg = idx[y[idx] == 0]
        if len(neg) > NORMAL_CAP:
            idx = np.setdiff1d(idx, rng.choice(neg, len(neg) - NORMAL_CAP, replace=False))
        return idx

    oof_pred = {a: np.zeros(len(y), dtype=np.int64) for a in range(len(ALPHAS))}
    for tr_i, ho_i in GroupKFold(5).split(X, y, rec):
        ti = cap(tr_i)
        probe = FAMILIES[fam](D.Data(X[ti], y[ti], D.balanced_weights(y[ti])), name)
        s_tr = D.eval_ir(probe, X[ti], node="score")[y[ti] == 0]
        s_ho = D.eval_ir(probe, X[ho_i], node="score")
        for a, alpha in enumerate(ALPHAS):
            oof_pred[a][ho_i] = (s_ho > threshold_for_spec(s_tr, 1 - alpha)).astype(np.int64)
    f1s = [f1(oof_pred[a], y) for a in range(len(ALPHAS))]
    a_best = int(np.argmax(f1s))
    ti = cap(np.arange(len(y)))
    probe = FAMILIES[fam](D.Data(X[ti], y[ti], D.balanced_weights(y[ti])), name)
    t = threshold_for_spec(D.eval_ir(probe, X[ti], node="score")[y[ti] == 0], 1 - ALPHAS[a_best])
    return D.finalize(probe, t), {"alpha": float(ALPHAS[a_best]), "oof_f1": f1s[a_best], "threshold": int(t)}


def per_class(pred: np.ndarray, y: np.ndarray, cls: int) -> dict:
    return {"TP": int(((pred == cls) & (y == cls)).sum()), "P": int((y == cls).sum()), "PP": int((pred == cls).sum())}


def main(beats: Path, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    B = load_beats(beats)
    lab = np.asarray([AAMI.get(chr(c), -1) for c in B.sym])
    keep = lab >= 0
    B = B.subset(keep)
    lab = lab[keep]
    bits = B.bits
    X = np.concatenate([bits, D.rr_bits(B.rr)], axis=1)
    m1, m2 = np.isin(B.rec, DS1), np.isin(B.rec, DS2)
    counts = {"DS1": np.bincount(lab[m1], minlength=5).tolist(), "DS2": np.bincount(lab[m2], minlength=5).tolist()}
    print("class counts N,S,V,F,Q", counts, flush=True)
    dets: dict[str, tuple[dict, dict]] = {}
    for fam_v, fam_s in PAIRS.values():
        for cls, fam in ((2, fam_v), (1, fam_s)):
            key = f"{'V' if cls == 2 else 'S'}_{fam}"
            if key not in dets:
                y1 = (lab[m1] == cls).astype(np.int64)
                dets[key] = fit_detector(fam, X[m1], y1, B.rec[m1], key, seed=cls)
                print(key, dets[key][1], len(dets[key][0]["meta"]["bit_features"]), flush=True)
    results, irs = {}, {}
    for name, (fam_v, fam_s) in PAIRS.items():
        irv, infv = dets[f"V_{fam_v}"]
        irs_, infs = dets[f"S_{fam_s}"]
        pv = run_ir(irv, bits[m2], B.rr[m2])["y"][:, 0]
        ps = run_ir(irs_, bits[m2], B.rr[m2])["y"][:, 0]
        pred = np.where(pv == 1, 2, np.where(ps == 1, 1, 0))
        y2, r2 = lab[m2], B.rec[m2]
        nsv = y2 <= 2
        res = {"V_info": infv, "S_info": infs}
        for scope, msk in (("NSV_only", nsv), ("all_beats", np.ones_like(nsv))):
            res[scope] = {"V": per_class(pred[msk], y2[msk], 2), "S": per_class(pred[msk], y2[msk], 1), "accuracy_3class": float((pred[msk & nsv] == y2[msk & nsv]).mean())}
        res["per_record"] = {
            int(r): {"V": per_class(pred[(r2 == r) & nsv], y2[(r2 == r) & nsv], 2), "S": per_class(pred[(r2 == r) & nsv], y2[(r2 == r) & nsv], 1)}
            for r in DS2
        }
        results[name] = res
        irs[name] = {"V": irv, "S": irs_}
        v, s = res["NSV_only"]["V"], res["NSV_only"]["S"]
        print(name, "V sens/ppv", round(v["TP"] / v["P"], 4), round(v["TP"] / max(1, v["PP"]), 4), "S sens/ppv", round(s["TP"] / s["P"], 4), round(s["TP"] / max(1, s["PP"]), 4), flush=True)
    (out / "ds_results.json").write_text(json.dumps({"class_counts": counts, "designs": results}))
    (out / "ds_irs.json").write_text(json.dumps(irs))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
