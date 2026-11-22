"""Proportions with Wilson intervals, subject-level bootstrap, worst subject."""
from __future__ import annotations

import math

import numpy as np


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, c - h), min(1.0, c + h))


def _se_sp(tp: np.ndarray, pos: np.ndarray, tn: np.ndarray, neg: np.ndarray) -> tuple[float, float]:
    return (tp.sum() / max(pos.sum(), 1), tn.sum() / max(neg.sum(), 1))


def _worst(k: np.ndarray, n: np.ndarray, subs: np.ndarray, m: int) -> dict | None:
    """Worst subject among those with at least m windows of the class."""
    ok = n >= m
    if not ok.any():
        return None
    rate = np.where(ok, k / np.maximum(n, 1), np.inf)
    w = int(np.argmin(rate))
    return {"id": str(subs[w]), "k": int(k[w]), "n": int(n[w])}


def summarize(y: np.ndarray, p: np.ndarray, subj: np.ndarray, *, n_boot: int = 2000, seed: int = 0) -> dict:
    """Window-level sensitivity and specificity, pooled over subjects, with Wilson and subject-bootstrap
    95% intervals and the worst subject for each."""
    subs = np.unique(subj)
    tp = np.array([((y == 1) & (p == 1) & (subj == s)).sum() for s in subs])
    pos = np.array([((y == 1) & (subj == s)).sum() for s in subs])
    tn = np.array([((y == 0) & (p == 0) & (subj == s)).sum() for s in subs])
    neg = np.array([((y == 0) & (subj == s)).sum() for s in subs])
    rng = np.random.default_rng(seed)
    bs = []
    for _ in range(n_boot):
        i = rng.integers(0, len(subs), len(subs))
        bs.append(_se_sp(tp[i], pos[i], tn[i], neg[i]))
    bs_arr = np.asarray(bs)
    out: dict = {}
    for name, k, n, col in (("sens", tp, pos, 0), ("spec", tn, neg, 1)):
        K, N = int(k.sum()), int(n.sum())
        lo, hi = wilson(K, N)
        have = n > 0
        rate = np.where(have, k / np.maximum(n, 1), np.inf)
        w = int(np.argmin(rate))
        out[name] = {
            "k": K, "n": N, "value": K / N if N else float("nan"),
            "wilson95": [lo, hi],
            "subject_boot95": [float(np.nanpercentile(bs_arr[:, col], 2.5)), float(np.nanpercentile(bs_arr[:, col], 97.5))],
            "worst_subject": {"id": str(subs[w]), "k": int(k[w]), "n": int(n[w])} if have.any() else None,
            "subjects_with_class": int(have.sum()),
            "worst_subject_min10": _worst(k, n, subs, 10),
        }
    return out
