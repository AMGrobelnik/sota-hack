"""Statistics fixed by protocol.md: pooled counts, Wilson 95 % (segments), subject-bootstrap 95 % (2000 resamples
of subjects, seed 0), per-subject mean, worst subject; and the wording rule against the published chip."""
from __future__ import annotations

import numpy as np

from afchip.stats import summarize

BASE_SE, BASE_SP = 0.949, 0.958  # Andersson et al. 2015, Table III, MIT-BIH AF, present implementation PrecSeg


def per_subject(y: np.ndarray, p: np.ndarray, subj: np.ndarray) -> dict[str, dict[str, int]]:
    out = {}
    for s in np.unique(subj):
        i = subj == s
        out[str(s)] = {"tp": int(((y == 1) & (p == 1) & i).sum()), "pos": int(((y == 1) & i).sum()),
                       "tn": int(((y == 0) & (p == 0) & i).sum()), "neg": int(((y == 0) & i).sum())}
    return out


def full_summary(y: np.ndarray, p: np.ndarray, subj: np.ndarray, naf: np.ndarray | None = None, n: int = 0) -> dict:
    s = summarize(y, p, subj)
    ps = per_subject(y, p, subj)
    se = [v["tp"] / v["pos"] for v in ps.values() if v["pos"] > 0]
    sp = [v["tn"] / v["neg"] for v in ps.values() if v["neg"] > 0]
    s["sens"]["per_subject_mean"] = float(np.mean(se)) if se else None
    s["spec"]["per_subject_mean"] = float(np.mean(sp)) if sp else None
    s["per_subject"] = ps
    if naf is not None:
        tp = int((p * naf).sum()); pos = int(naf.sum())
        tn = int(((1 - p) * (n - naf)).sum()); neg = int((n - naf).sum())
        s["interval_level"] = {"sens": [tp, pos], "spec": [tn, neg]}
    return s


def wording(s: dict, base_se: float = BASE_SE, base_sp: float = BASE_SP) -> str:
    """protocol.md, decision rule. BEATS: both point estimates >= baseline and at least one subject-bootstrap
    interval lies entirely above its baseline. MATCHES: not BEATS, and neither subject-bootstrap interval lies
    entirely below its baseline (the baseline is inside, or below, each interval). BELOW otherwise."""
    se, sp = s["sens"], s["spec"]
    lo_se, hi_se = se["subject_boot95"]
    lo_sp, hi_sp = sp["subject_boot95"]
    if se["value"] >= base_se and sp["value"] >= base_sp and (lo_se > base_se or lo_sp > base_sp):
        return "BEATS"
    if hi_se >= base_se and hi_sp >= base_sp:
        return "MATCHES"
    return "BELOW"
