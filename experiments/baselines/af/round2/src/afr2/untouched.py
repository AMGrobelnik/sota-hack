"""The one run on the untouched MIT-BIH Arrhythmia database (and the secondary Long-Term AF check), as fixed in
protocol.md: two frozen designs, N = 128, segments from each record start, AF if more than half the intervals
are (AFIB. Refuses to run twice.

Usage: python -I -m afr2.untouched --data DATA_ROOT --chip MODEL.json --r1 MODEL.json --out FILE
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from afchip.run_eval import load_db, windows
from afr2.fit import predict, used
from afr2.seqfeat import segment_features
from afr2.stats2 import full_summary

N = 128
PUBLISHED = {
    "andersson2015_precseg": {"mitdb_100": {"spec": 0.970}, "mitdb_200": {"sens": 0.988, "spec": 0.790},
                              "unit": "segments (AF episodes), N = 128, ectopic preprocessing"},
    "dash2009_with_ectopy": {"mitdb_100": {"spec": 0.962}, "mitdb_200": {"sens": 0.965, "spec": 0.694},
                             "unit": "AF beats, l = 128, PercThresh 50 %"},
    "dash2009_without_ectopy": {"mitdb_100": {"spec": 0.995}, "mitdb_200": {"sens": 0.902, "spec": 0.912},
                                "unit": "AF beats, after removal of all PVCs"},
}


def score(model: dict, X: np.ndarray, y: np.ndarray, S: np.ndarray, naf: np.ndarray) -> dict:
    f = used(model)
    p = predict(segment_features(X, f), model, f)
    out = full_summary(y, p, S, naf, N)
    out["sens"]["defined"] = bool((y == 1).any())
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--chip", type=Path, required=True)
    ap.add_argument("--r1", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    if a.out.exists():
        raise SystemExit(f"{a.out} exists: the untouched test runs once")
    designs = {"r2_chip": json.loads(a.chip.read_text()), "r1_and2_n128": json.loads(a.r1.read_text())}
    res: dict = {"published": PUBLISHED, "designs": designs, "n": N}
    mit = load_db(a.data / "mitdb", "atr", set())
    X, y, S, naf = windows(mit, N)
    series = np.asarray(["100" if s.startswith("1") else "200" for s in S])
    res["mitdb"] = {"records": len(mit), "records_100": sum(r.name.startswith("1") for r in mit),
                    "records_200": sum(r.name.startswith("2") for r in mit), "segments": int(len(y)),
                    "af_segments": int(y.sum()),
                    "af_segments_by_record": {str(s): int(y[S == s].sum()) for s in np.unique(S) if y[S == s].any()}}
    for name, m in designs.items():
        res["mitdb"][name] = {"pooled": score(m, X, y, S, naf)}
        for ser in ("100", "200"):
            i = series == ser
            res["mitdb"][name][ser] = score(m, X[i], y[i], S[i], naf[i])
    lt = load_db(a.data / "ltafdb", "atr", set())
    Xl, yl, Sl, nl = windows(lt, N)
    res["ltafdb"] = {"records": len(lt), "segments": int(len(yl)), "af_segments": int(yl.sum())}
    for name, m in designs.items():
        res["ltafdb"][name] = score(m, Xl, yl, Sl, nl)
    a.out.write_text(json.dumps(res, indent=1))
    for name in designs:
        for part in ("100", "200", "pooled"):
            r = res["mitdb"][name][part]
            print(name, "mitdb", part, "se", r["sens"]["k"], r["sens"]["n"], "sp", r["spec"]["k"], r["spec"]["n"],
                  "beats", r["interval_level"], flush=True)
        r = res["ltafdb"][name]
        print(name, "ltafdb se", r["sens"]["k"], r["sens"]["n"], "sp", r["spec"]["k"], r["spec"]["n"], flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
