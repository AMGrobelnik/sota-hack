"""Integer, multiplier-free features over a window of quantised RR intervals (exactly what the chip computes),
plus float reference statistics (Dash 2009 TPR, RMSSD/meanRR, Shannon entropy) for the plain reference model."""
from __future__ import annotations

import numpy as np

ABS_T = (0, 1, 2, 3, 4, 6, 8, 12, 16, 24, 32)  # |dRR| thresholds in 8 ms units
REL_K = (2, 3, 4, 5)  # |dRR| > RR >> k, i.e. 25%, 12.5%, 6.25%, 3.1% of the interval
# v2 (added after the first results, see notes.md): lag-2 and lag-3 relative differences, which stay small in
# bigeminy / trigeminy (period-2 or period-3 regular rhythms) but not in AF, and runs of two irregular steps.
LAG_K = ((2, 3), (2, 4), (3, 3), (3, 4))
_FS = {"name": "v2"}


def set_featureset(name: str) -> None:
    if name not in ("v1", "v2"):
        raise ValueError(name)
    _FS["name"] = name


def featureset() -> str:
    return _FS["name"]


def int_feature_names() -> list[str]:
    v1 = [f"abs_gt{t}" for t in ABS_T] + [f"rel_k{k}" for k in REL_K] + ["tp", "sum_abs", "sum_rr"]
    if _FS["name"] == "v1":
        return v1
    return v1 + [f"lag{lag}_k{k}" for lag, k in LAG_K] + ["run2_k3"]


def int_features(x: np.ndarray) -> np.ndarray:
    """x: [m, n] int RR (8 ms units). Returns [m, F] int64 features, all counts or sums."""
    x = x.astype(np.int64)
    d = x[:, 1:] - x[:, :-1]
    a = np.abs(d)
    cols = [(a > t).sum(axis=1) for t in ABS_T]
    cols += [(a > (x[:, :-1] >> k)).sum(axis=1) for k in REL_K]
    pos, neg = d > 0, d < 0
    tp = ((pos[:, :-1] & neg[:, 1:]) | (neg[:, :-1] & pos[:, 1:])).sum(axis=1)
    cols += [tp, a.sum(axis=1), x.sum(axis=1)]
    if _FS["name"] == "v2":
        for lag, k in LAG_K:
            e = np.abs(x[:, lag:] - x[:, :-lag])
            cols.append((e > (x[:, :-lag] >> k)).sum(axis=1))
        b = a > (x[:, :-1] >> 3)
        cols.append((b[:, :-1] & b[:, 1:]).sum(axis=1))
    return np.stack(cols, axis=1).astype(np.int64)


def dash_stats(x: np.ndarray) -> np.ndarray:
    """Float Dash 2009 statistics per window, without ectopic filtering: TPR, RMSSD/meanRR, Shannon entropy
    (16 bins after removing the 8 longest and 8 shortest intervals)."""
    x = x.astype(np.float64)
    n = x.shape[1]
    d = np.diff(x, axis=1)
    tp = ((d[:, :-1] * d[:, 1:]) < 0).sum(axis=1)
    tpr = tp / max(n - 2, 1)
    rmssd = np.sqrt((d**2).mean(axis=1)) / np.maximum(x.mean(axis=1), 1e-9)
    no = min(8, max(n // 16, 1))
    r = np.sort(x, axis=1)[:, no : n - no]
    lo, hi = r[:, :1], r[:, -1:]
    span = np.where(hi > lo, hi - lo, 1.0)
    b = np.clip(np.floor((r - lo) / span * 16), 0, 15).astype(np.int64)
    cnt = np.zeros((len(x), 16))
    np.add.at(cnt, (np.repeat(np.arange(len(x)), r.shape[1]), b.ravel()), 1)
    p = cnt / r.shape[1]
    with np.errstate(divide="ignore", invalid="ignore"):
        se = -np.where(p > 0, p * np.log(p), 0.0).sum(axis=1) / np.log(16.0)
    se = np.where(hi[:, 0] > lo[:, 0], se, 0.0)
    return np.stack([tpr, rmssd, se], axis=1)


def dash_rule(stats: np.ndarray) -> np.ndarray:
    """Dash 2009 published thresholds (Table 1): 0.54 < TPR < 0.77, RMSSD > 0.1 meanRR, SE > 0.7."""
    tpr, rm, se = stats[:, 0], stats[:, 1], stats[:, 2]
    return ((tpr > 0.54) & (tpr < 0.77) & (rm > 0.1) & (se > 0.7)).astype(np.int64)
