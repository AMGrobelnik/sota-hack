"""Nested leave-one-subject-out on AFDB: inside every outer fold, the design (feature set v1 or v2, and family)
is chosen by an inner leave-one-subject-out on the 22 training subjects only (highest pooled sens + spec), then
refit on those 22 and applied to the held-out subject. This removes the choice of the reported design from the
test subjects.

Usage: python -I -m afchip.run_nested --afdb <dir> --out <dir> --n 128 --part i --parts k
       python -I -m afchip.run_nested --out <dir> --n 128 --combine
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from afchip.features import int_features, set_featureset
from afchip.models import FAMILIES, predict
from afchip.run_eval import DASH_EXCLUDED, load_db, windows
from afchip.stats import summarize

CANDIDATES = [(fs, fam) for fs in ("v1", "v2") for fam in ("thr1", "and2", "tree3", "lin")]


def feats(X: np.ndarray, fs: str) -> np.ndarray:
    set_featureset(fs)
    return int_features(X)


def youden(y: np.ndarray, p: np.ndarray) -> float:
    return float(p[y == 1].mean() + (1 - p[y == 0]).mean())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--afdb", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--n", type=int, default=128)
    ap.add_argument("--part", type=int, default=0)
    ap.add_argument("--parts", type=int, default=1)
    ap.add_argument("--combine", action="store_true")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    if a.combine:
        y, p, s, chosen = [], [], [], {}
        for f in sorted(a.out.glob(f"nested_n{a.n}_part*.json")):
            d = json.loads(f.read_text())
            for subj, r in d.items():
                y += r["y"]; p += r["p"]; s += [subj] * len(r["y"]); chosen[subj] = r["chosen"]
        res = summarize(np.asarray(y), np.asarray(p), np.asarray(s)) | {"chosen_per_fold": chosen}
        (a.out / f"nested_n{a.n}_summary.json").write_text(json.dumps(res, indent=1))
        print(json.dumps({c: (res[c]["k"], res[c]["n"], round(res[c]["value"], 4)) for c in ("sens", "spec")}))
        print(json.dumps(chosen))
        return
    recs = load_db(a.afdb, "qrs", DASH_EXCLUDED)
    X, y, S, _ = windows(recs, a.n)
    F = {fs: feats(X, fs) for fs in ("v1", "v2")}
    subs = list(np.unique(S))
    out: dict = {}
    for s in subs[a.part :: a.parts]:
        tr = S != s
        inner_subs = [u for u in subs if u != s]
        score = {}
        for fs, fam in CANDIDATES:
            set_featureset(fs)
            pin = np.zeros(tr.sum(), dtype=np.int64)
            Ftr, ytr, Str = F[fs][tr], y[tr], S[tr]
            for u in inner_subs:
                itr, ite = Str != u, Str == u
                m = FAMILIES[fam](Ftr[itr], ytr[itr], a.n)
                pin[ite] = predict(Ftr[ite], m)
            score[f"{fs}:{fam}"] = youden(ytr, pin)
        best = max(score, key=score.get)
        fs, fam = best.split(":")
        set_featureset(fs)
        m = FAMILIES[fam](F[fs][tr], y[tr], a.n)
        te = S == s
        out[str(s)] = {"chosen": best, "inner_scores": score, "y": y[te].tolist(), "p": predict(F[fs][te], m).tolist()}
        print(s, best, round(score[best], 4), flush=True)
        (a.out / f"nested_n{a.n}_part{a.part}.json").write_text(json.dumps(out))
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
