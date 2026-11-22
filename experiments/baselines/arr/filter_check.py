"""Choose the band-pass variant on VALIDATION patients only (the baseline's PTA_1 file is not
published). For each variant and fold: a float model on the baseline's 372 input bits, trained on
the fold's training patients, scored on its validation patients (AUC and sensitivity at
specificity 0.998 on validation). Test patients are never touched.

Usage: python -I filter_check.py <folds.json> <out json> <variant>=<beats.npz> ...
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

from arrlib import load_beats, threshold_for_spec

FOLDS = (18, 0, 5, 10, 25, 40)


def main(folds_p: Path, out: Path, variants: dict[str, Path]) -> None:
    folds = json.loads(folds_p.read_text())
    res: dict = {}
    for name, path in variants.items():
        B = load_beats(path)
        X = B.bits[:, :372].astype(np.float32)
        y = (B.y5 > 0).astype(np.int64)
        res[name] = {}
        for fo in FOLDS:
            f = folds[fo]
            tr = np.flatnonzero(np.isin(B.rec, f["train"]))
            va = np.isin(B.rec, f["val"])
            w = np.where(y[tr] == 1, 0.5 / y[tr].mean(), 0.5 / (1 - y[tr].mean()))
            clf = HistGradientBoostingClassifier(max_iter=40, early_stopping=False, random_state=0)
            clf.fit(X[tr], y[tr], sample_weight=w)
            s = clf.decision_function(X[va])
            t = threshold_for_spec(np.round(s[y[va] == 0] * 1e6).astype(np.int64), 0.998)
            sens = float((np.round(s[y[va] == 1] * 1e6) > t).mean())
            res[name][fo] = {"val_auc": float(roc_auc_score(y[va], s)), "val_sens_at_val_spec0998": sens}
            print(name, fo, res[name][fo], flush=True)
        res[name]["mean_val_auc"] = float(np.mean([res[name][fo]["val_auc"] for fo in FOLDS]))
        res[name]["mean_val_sens"] = float(np.mean([res[name][fo]["val_sens_at_val_spec0998"] for fo in FOLDS]))
    out.write_text(json.dumps(res, indent=1))
    print({k: (v["mean_val_auc"], v["mean_val_sens"]) for k, v in res.items()})


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), {a.split("=")[0]: Path(a.split("=")[1]) for a in sys.argv[3:]})
