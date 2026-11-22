"""Nested leave-one-subject-out on the MIT-BIH AF database, exactly as protocol.md fixes it.

For every outer subject: an inner leave-one-subject-out over the training subjects scores all seven families
(each fitted at the operating rule on the inner-training subjects); the selection rule picks one family; that
family is refitted on all training subjects and applied to the held-out subject. The 'final' job runs the same
procedure with every subject as training data: that design is for the chip and the untouched test only.

Usage: python -I -m afr2.nested --afdb D --recs 23|25 --n 128 --out DIR [--workers 12]
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import time
from pathlib import Path

import numpy as np

from afchip.run_eval import DASH_EXCLUDED, load_db, windows
from afr2.fit import FAMILIES, fit_all, predict, size_key, used
from afr2.seqfeat import segment_features
from afr2.stats2 import full_summary, wording

SEL_MIN_SENS = 0.95
SEL_TIE = 0.002

_G: dict = {}


def _init(F: np.ndarray, y: np.ndarray, S: np.ndarray, n: int) -> None:
    _G.update(F=F, y=y, S=S, n=n)


def _rates(y: np.ndarray, p: np.ndarray) -> tuple[float, float]:
    return float(p[y == 1].mean()) if (y == 1).any() else float("nan"), float(1 - p[y == 0].mean()) if (y == 0).any() else float("nan")


def select(inner: dict[str, tuple[float, float]], fitted: dict[str, dict]) -> str:
    ok = [f for f in FAMILIES if inner[f][0] >= SEL_MIN_SENS]
    if ok:
        best = max(inner[f][1] for f in ok)
        tied = [f for f in ok if inner[f][1] >= best - SEL_TIE]
    else:
        best = max(inner[f][0] + inner[f][1] for f in FAMILIES)
        tied = [f for f in FAMILIES if inner[f][0] + inner[f][1] >= best - 1e-12]
    return min(tied, key=lambda f: size_key(fitted[f]))


def run_fold(held: str | None) -> dict:
    """held = subject id for an outer fold, or None for the final all-subject design."""
    F, y, S, n = _G["F"], _G["y"], _G["S"], _G["n"]
    tr = S != held if held is not None else np.ones(len(S), dtype=bool)
    Ftr, ytr, Str = F[tr], y[tr], S[tr]
    pin = {f: np.zeros(tr.sum(), dtype=np.int64) for f in FAMILIES}
    for u in np.unique(Str):
        a, b = Str != u, Str == u
        ms = fit_all(Ftr[a], ytr[a], n)
        for f in FAMILIES:
            pin[f][b] = predict(Ftr[b], ms[f])
    inner = {f: _rates(ytr, pin[f]) for f in FAMILIES}
    fitted = fit_all(Ftr, ytr, n)
    chosen = select(inner, fitted)
    out = {"held": held, "inner": inner, "chosen": chosen, "models": fitted,
           "sizes": {f: list(size_key(fitted[f])) for f in FAMILIES}}
    if held is not None:
        te = S == held
        out["pred"] = {f: predict(F[te], fitted[f]).tolist() for f in FAMILIES}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--afdb", type=Path, required=True)
    ap.add_argument("--recs", choices=["23", "25"], required=True)
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=12)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    recs = load_db(a.afdb, "qrs", DASH_EXCLUDED if a.recs == "23" else set())
    X, y, S, naf = windows(recs, a.n)
    F = segment_features(X)
    subs = [str(s) for s in np.unique(S)]
    print(f"records {len(recs)} segments {len(y)} AF {int(y.sum())} subjects {len(subs)}", flush=True)
    jobs: list[str | None] = [None] + subs
    res: dict = {}
    with mp.get_context("spawn").Pool(a.workers, initializer=_init, initargs=(F, y, S, a.n)) as pool:
        for r in pool.imap_unordered(run_fold, jobs):
            res["final" if r["held"] is None else r["held"]] = r
            print(f"done {r['held']} chosen {r['chosen']} {time.time() - t0:.0f}s", flush=True)
    p = np.zeros_like(y)
    pf = {f: np.zeros_like(y) for f in FAMILIES}
    for s in subs:
        te = S == s
        p[te] = res[s]["pred"][res[s]["chosen"]]
        for f in FAMILIES:
            pf[f][te] = res[s]["pred"][f]
    nested = full_summary(y, p, S, naf, a.n)
    nested["wording_vs_published"] = wording(nested)
    fin = res["final"]
    out = {
        "config": {"n": a.n, "records": [r.name for r in recs], "record_set": a.recs, "segments": int(len(y)),
                   "af_segments": int(y.sum()), "subjects": len(subs)},
        "nested": nested,
        "chosen_per_fold": {s: res[s]["chosen"] for s in subs},
        "inner_per_fold": {s: res[s]["inner"] for s in subs},
        "models_per_fold": {s: res[s]["models"][res[s]["chosen"]] for s in subs},
        "per_family_loso_descriptive": {f: full_summary(y, pf[f], S, naf, a.n) for f in FAMILIES},
        "final": {"chosen": fin["chosen"], "model": fin["models"][fin["chosen"]], "inner": fin["inner"],
                  "all_models": fin["models"], "sizes": fin["sizes"], "used": used(fin["models"][fin["chosen"]])},
        "seconds": round(time.time() - t0, 1),
    }
    (a.out / "nested.json").write_text(json.dumps(out, indent=1))
    np.savez_compressed(a.out / "preds.npz", y=y, p=p, S=S, naf=naf, **{f"p_{f}": pf[f] for f in FAMILIES})
    ns, nsp = nested["sens"], nested["spec"]
    print(f"NESTED se {ns['k']}/{ns['n']} sp {nsp['k']}/{nsp['n']} wording {nested['wording_vs_published']} "
          f"final {fin['chosen']} {used(fin['models'][fin['chosen']])}", flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
