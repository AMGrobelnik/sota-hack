"""Corrections to round one, recomputed: round one's and2_n128 leave-one-subject-out (its own fitting code), with
per-subject means and the wording rule; and a check that round two's feature code computes round one's two
counts exactly (same decisions for the fixed and2_n128 on every segment of every database).

Usage: python -I -m afr2.r1fix --data DATA_ROOT --out FILE
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from afchip.features import int_features, set_featureset
from afchip.models import fit_and2
from afchip.models import predict as r1_predict
from afchip.run_eval import DASH_EXCLUDED, load_db, windows
from afr2.fit import predict
from afr2.seqfeat import segment_features
from afr2.stats2 import full_summary, wording


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    set_featureset("v2")
    recs = load_db(a.data / "afdb", "qrs", DASH_EXCLUDED)
    X, y, S, naf = windows(recs, 128)
    F = int_features(X)
    p = np.zeros_like(y)
    for s in np.unique(S):
        tr, te = S != s, S == s
        p[te] = r1_predict(F[te], fit_and2(F[tr], y[tr]))
    summ = full_summary(y, p, S, naf, 128)
    summ["wording_vs_published"] = wording(summ)
    r1 = {"kind": "and2", "f1": 14, "t1": 94, "f2": 21, "t2": 72}
    r2 = json.loads((Path(__file__).resolve().parents[2] / "models" / "r1_and2_n128.json").read_text())
    same: dict = {}
    for db, ext, exc in (("afdb", "qrs", set()), ("ltafdb", "atr", set())):
        Xd, _, _, _ = windows(load_db(a.data / db, ext, exc), 128)
        a1 = r1_predict(int_features(Xd), r1)
        a2 = predict(segment_features(Xd, r2["feats"]), r2, r2["feats"])
        same[db] = {"segments": int(len(Xd)), "mismatches": int((a1 != a2).sum())}
    out = {"r1_and2_n128_afdb_loso_recomputed": summ, "r1_vs_r2_feature_code_same_decisions": same}
    a.out.write_text(json.dumps(out, indent=1))
    se, sp = summ["sens"], summ["spec"]
    print(f"r1 and2 LOSO se {se['k']}/{se['n']} mean {se['per_subject_mean']:.4f} boot {se['subject_boot95']} "
          f"sp {sp['k']}/{sp['n']} mean {sp['per_subject_mean']:.4f} boot {sp['subject_boot95']} "
          f"wording {summ['wording_vs_published']} same {same}", flush=True)


if __name__ == "__main__":
    main()
