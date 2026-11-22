"""Test vectors for the lab's bit-exact check: integer features of held-out windows and the integer model's
decision on each. Written next to the run's outputs (never committed: they are derived from recordings).

usage: python -I -m neonatal_eeg.vectors --stage-dir DIR --cache DIR --ids a,b --out vectors.json [--n 1024]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from neonatal_eeg import data as D
from neonatal_eeg import models as M


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage-dir", type=Path, required=True)
    ap.add_argument("--cache", type=Path, required=True)
    ap.add_argument("--ids", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--n", type=int, default=1024)
    a = ap.parse_args()
    d = json.loads((a.stage_dir / "designs.json").read_text())
    q = d["meta"]["quantiser"]
    lo, hi = np.array(q["lo"]), np.array(q["hi"])
    feats = np.concatenate([M.quantise(np.load(a.cache / f"b{b:02d}.npz")["feats"], lo, hi)
                            for b in d["meta"]["split"]["test"]])
    by_id = {x["id"]: x for x in d["designs"]}
    by_id[d["baseline"]["id"]] = d["baseline"]
    rng = np.random.default_rng(1)
    out = {}
    for i in a.ids.split(","):
        x = by_id[i]
        if "spec" in x:
            didx = [D.ALL_DERIVS.index(dd) for dd in D.BUDGETS[x["spec"]["channels"]]]
            flat = feats[:, didx, :].reshape(len(feats), -1)
        else:   # baseline: C3-C4 line length only
            flat = feats[:, D.ALL_DERIVS.index(D.BUDGETS[1][0]), :1]
        dec = M.eval_ir(x["ir"], flat)
        pos, neg = np.flatnonzero(dec == 1), np.flatnonzero(dec == 0)
        k = min(len(pos), a.n // 2)
        pick = np.concatenate([rng.choice(pos, k, replace=False), rng.choice(neg, a.n - k, replace=False)])
        out[i] = {"x": flat[pick].tolist(), "expected": dec[pick].tolist()}
        print(i, "vectors", len(pick), "positives", int(dec[pick].sum()))
    a.out.write_text(json.dumps(out))


if __name__ == "__main__":
    main()
