"""Subject-wise evaluation on AFDB (leave-one-subject-out) and cross-database test (train AFDB, test LTAFDB).

Usage: python -I run_eval.py --afdb <dir> --ltafdb <dir> --out <dir>
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from afchip.afdata import list_records, load_record, segments
from afchip.features import dash_rule, dash_stats, int_features, set_featureset
from afchip.models import FAMILIES, predict
from afchip.stats import summarize

WINDOWS = (16, 32, 64, 128)
DASH_EXCLUDED = {"04936", "05091"}  # excluded by Dash 2009 (incorrect RR annotations)


def load_db(db: Path, beat_ext: str, exclude: set[str]) -> list:
    recs = []
    for r in list_records(db):
        if r in exclude:
            continue
        if not (db / f"{r}.{beat_ext}").exists() or not (db / f"{r}.atr").exists():
            print(f"skip {r}: missing annotation file", flush=True)
            continue
        recs.append(load_record(db, r, beat_ext=beat_ext))
    return recs


def windows(recs: list, n: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    X, Y, S, A = [], [], [], []
    for r in recs:
        x, y, naf = segments(r, n)
        X.append(x); Y.append(y); S += [r.name] * len(y); A.append(naf)
    return np.concatenate(X), np.concatenate(Y), np.asarray(S), np.concatenate(A)


def interval_level(y_seg_pred: np.ndarray, naf: np.ndarray, n: int) -> dict:
    """Beat (interval) level: every interval inherits its segment's decision (Dash 2009 Table 2 'AF beats')."""
    tp = int((y_seg_pred * naf).sum()); pos = int(naf.sum())
    tn = int(((1 - y_seg_pred) * (n - naf)).sum()); neg = int((n - naf).sum())
    return {"sens": [tp, pos, tp / max(pos, 1)], "spec": [tn, neg, tn / max(neg, 1)]}


def ref_models(Ftr: np.ndarray, ytr: np.ndarray, Fte: np.ndarray) -> dict[str, np.ndarray]:
    """Plain float reference models on all integer features plus the Dash statistics."""
    sc = StandardScaler().fit(Ftr)
    lr = LogisticRegression(class_weight="balanced", max_iter=3000, random_state=0).fit(sc.transform(Ftr), ytr)
    gb = HistGradientBoostingClassifier(class_weight="balanced", random_state=0).fit(Ftr, ytr)
    return {"ref_logreg_float": lr.predict(sc.transform(Fte)), "ref_gbdt_float": gb.predict(Fte)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--afdb", type=Path, required=True)
    ap.add_argument("--ltafdb", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--windows", type=int, nargs="*", default=list(WINDOWS))
    ap.add_argument("--no-ref", action="store_true")
    ap.add_argument("--features", default="v2", choices=["v1", "v2"])
    a = ap.parse_args()
    set_featureset(a.features)
    a.out.mkdir(parents=True, exist_ok=True)
    afdb = load_db(a.afdb, "qrs", DASH_EXCLUDED)
    lt = load_db(a.ltafdb, "atr", set())
    print(f"AFDB records {len(afdb)}  LTAFDB records {len(lt)}", flush=True)
    results: dict = {"featureset": a.features, "afdb_records": [r.name for r in afdb], "ltafdb_records": [r.name for r in lt], "runs": {}}
    final_models: dict = {}
    for n in a.windows:
        X, y, S, naf = windows(afdb, n)
        Xl, yl, Sl, nafl = windows(lt, n)
        F, Fl = int_features(X), int_features(Xl)
        D, Dl = dash_stats(X), dash_stats(Xl)
        FA, FAl = np.hstack([F, D]), np.hstack([Fl, Dl])
        print(f"N={n}: AFDB windows {len(y)} (AF {y.sum()})  LTAFDB windows {len(yl)} (AF {yl.sum()})", flush=True)
        preds: dict[str, np.ndarray] = {}
        # Dash 2009 published thresholds, no refit (float, no ectopic filter)
        preds["dash2009_fixed_float"] = dash_rule(D)
        names = list(FAMILIES) + ([] if a.no_ref else ["ref_logreg_float", "ref_gbdt_float"])
        loso = {k: np.zeros_like(y) for k in names}
        for s in np.unique(S):
            tr, te = S != s, S == s
            for fam, fit in FAMILIES.items():
                m = fit(F[tr], y[tr], n)
                loso[fam][te] = predict(F[te], m)
            if not a.no_ref:
                for k, v in ref_models(FA[tr], y[tr], FA[te]).items():
                    loso[k][te] = v
        preds.update(loso)
        run: dict = {"n": n, "afdb_windows": int(len(y)), "afdb_af_windows": int(y.sum()),
                     "ltafdb_windows": int(len(yl)), "ltafdb_af_windows": int(yl.sum()), "afdb_loso": {}, "ltafdb_cross": {}}
        for k, p in preds.items():
            run["afdb_loso"][k] = summarize(y, p, S) | {"interval_level": interval_level(p, naf, n)}
        # train on all AFDB, test on LTAFDB
        lpreds = {"dash2009_fixed_float": dash_rule(Dl)}
        for fam, fit in FAMILIES.items():
            m = fit(F, y, n)
            final_models[f"{fam}_n{n}"] = m
            lpreds[fam] = predict(Fl, m)
        if not a.no_ref:
            lpreds.update(ref_models(FA, y, FAl))
        for k, p in lpreds.items():
            run["ltafdb_cross"][k] = summarize(yl, p, Sl) | {"interval_level": interval_level(p, nafl, n)}
        results["runs"][str(n)] = run
        for k in preds:
            r1, r2 = run["afdb_loso"][k], run["ltafdb_cross"].get(k)
            line = f"  {k:22s} AFDB Se {r1['sens']['value']:.3f} Sp {r1['spec']['value']:.3f}"
            if r2:
                line += f" | LTAF Se {r2['sens']['value']:.3f} Sp {r2['spec']['value']:.3f}"
            print(line, flush=True)
        (a.out / "eval_full.json").write_text(json.dumps(results, indent=1))
        (a.out / "final_models.json").write_text(json.dumps(final_models, indent=1))
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
