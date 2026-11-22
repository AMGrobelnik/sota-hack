"""Round-two candidate features: integer counts that a clocked circuit computes one RR interval at a time.

Every feature is a count over one segment of n intervals r_0 .. r_(n-1) (8 ms units, 8 bit). Each count needs at
most the last four intervals, one counter and the position inside the segment; the running-mean counts also need
one 12-bit mean register. Pairs never cross a segment boundary, so the counts depend on the segment alone.

    rel{L}_{k}  #{i >= L : |r_i - r_(i-L)| > r_(i-L) >> k}          L = 1..4, k = 3..6
    abs_{t}     #{i >= 1 : |r_i - r_(i-1)| > t}                      t = 2, 4, 8, 16 (16 to 128 ms)
    tp          #{i >= 2 : r_(i-1) is a strict turning point}       sign(d_(i-1)) = -sign(d_i) != 0
    run_{k}     #{i >= 2 : both steps into and out of r_(i-1) are rel1_k irregular}   k = 3, 4
    dev_{k}     #{i >= 1 : |16 r_i - m| > m >> k}, m the running mean x16      k = 3, 4, 5
                m <- 16 r_0 at i = 0; then m <- clip(m + ((16 r_i - m) >> 3), 0, 4095) after each test

`segment_features` is the vectorised definition used for fitting; `GoldenStep` is an independent
one-interval-at-a-time model of the clocked circuit, written from the same definitions, used to check the chip.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

REL = [(lag, k) for lag in (1, 2, 3, 4) for k in (3, 4, 5, 6)]
ABS_T = (2, 4, 8, 16)
RUN_K = (3, 4)
DEV_K = (3, 4, 5)
MEAN_SHIFT = 3
MEAN_SCALE = 16
MEAN_MAX = 4095

NAMES: list[str] = ([f"rel{lag}_{k}" for lag, k in REL] + [f"abs_{t}" for t in ABS_T] + ["tp"]
                    + [f"run_{k}" for k in RUN_K] + [f"dev_{k}" for k in DEV_K])
INDEX = {n: i for i, n in enumerate(NAMES)}


def lag_of(name: str) -> int:
    """How far back the feature looks (the first position where its bit can be 1)."""
    if name.startswith("rel"):
        return int(name[3:].split("_")[0])
    if name.startswith(("abs_", "dev_")):
        return 1
    return 2  # tp, run


def history_needed(names: list[str]) -> int:
    """Stored past intervals the circuit needs for these features."""
    h = 0
    for n in names:
        h = max(h, lag_of(n) if n.startswith("rel") else (2 if n in ("tp",) or n.startswith("run_") else 1))
    return h


def _mean_trace(x: np.ndarray, ks: list[int]) -> dict[int, np.ndarray]:
    m = MEAN_SCALE * x[:, 0]
    cnt = {k: np.zeros(len(x), dtype=np.int64) for k in ks}
    for i in range(1, x.shape[1]):
        v = MEAN_SCALE * x[:, i]
        dev = np.abs(v - m)
        for k in ks:
            cnt[k] += dev > (m >> k)
        m = np.clip(m + ((v - m) >> MEAN_SHIFT), 0, MEAN_MAX)
    return cnt


def segment_features(X: np.ndarray, names: list[str] | None = None) -> np.ndarray:
    """X [m, n] int RR in 8 ms units -> [m, len(names)] int64 counts (all features when names is None)."""
    names = NAMES if names is None else names
    x = X.astype(np.int64)
    d = x[:, 1:] - x[:, :-1]
    a = np.abs(d)
    cache: dict[str, np.ndarray] = {}
    dev_ks = [int(n[4:]) for n in names if n.startswith("dev_")]
    dev = _mean_trace(x, dev_ks) if dev_ks else {}
    cols = []
    for n in names:
        if n.startswith("rel"):
            lag, k = (int(v) for v in n[3:].split("_"))
            e = cache.setdefault(f"e{lag}", np.abs(x[:, lag:] - x[:, :-lag]))
            cols.append((e > (x[:, :-lag] >> k)).sum(axis=1))
        elif n.startswith("abs_"):
            cols.append((a > int(n[4:])).sum(axis=1))
        elif n == "tp":
            cols.append((((d[:, :-1] > 0) & (d[:, 1:] < 0)) | ((d[:, :-1] < 0) & (d[:, 1:] > 0))).sum(axis=1))
        elif n.startswith("run_"):
            b = a > (x[:, :-1] >> int(n[4:]))
            cols.append((b[:, :-1] & b[:, 1:]).sum(axis=1))
        elif n.startswith("dev_"):
            cols.append(dev[int(n[4:])])
        else:
            raise ValueError(n)
    return np.stack(cols, axis=1).astype(np.int64)


def feature_bit(name: str, x: int, h: list[int], m: int) -> int:
    """The 0/1 increment of one feature for the new interval x, given past intervals h[0] = r_(i-1), h[1] = r_(i-2)
    and the mean register m (before its update). Validity by position is applied by the caller."""
    if name.startswith("rel"):
        lag, k = (int(v) for v in name[3:].split("_"))
        o = h[lag - 1]
        return int(abs(x - o) > (o >> k))
    if name.startswith("abs_"):
        return int(abs(x - h[0]) > int(name[4:]))
    if name == "tp":
        d1, d2 = h[0] - h[1], x - h[0]
        return int((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0))
    if name.startswith("run_"):
        k = int(name[4:])
        return int(abs(h[0] - h[1]) > (h[1] >> k) and abs(x - h[0]) > (h[0] >> k))
    if name.startswith("dev_"):
        v = MEAN_SCALE * x
        return int(abs(v - m) > (m >> int(name[4:])))
    raise ValueError(name)


@dataclass
class GoldenStep:
    """Independent step model of the clocked detector: one call per arriving interval.

    State: position p in the segment, the last `hist` intervals, one counter per feature, the mean register.
    step(x) returns (af, done, counts_before_this_interval). af is the rule applied to the final counts on the
    last interval of a segment (done = 1), else 0; the counters restart for the next segment.
    """

    names: list[str]
    n: int
    rule: object  # callable: dict name -> count  ->  0/1
    hist: int = 0
    p: int = 0
    h: list[int] = field(default_factory=list)
    c: list[int] = field(default_factory=list)
    m: int = 0

    def __post_init__(self) -> None:
        self.hist = max(history_needed(self.names), 1)
        self.reset()

    def reset(self) -> None:
        self.p, self.h, self.c, self.m = 0, [0] * self.hist, [0] * len(self.names), 0

    def step(self, x: int) -> tuple[int, int, list[int]]:
        before = list(self.c)
        hh = self.h + [0] * (4 - len(self.h))
        fin = []
        for j, nm in enumerate(self.names):
            b = feature_bit(nm, x, hh, self.m) if self.p >= lag_of(nm) else 0
            fin.append(self.c[j] + b)
        done = int(self.p == self.n - 1)
        af = int(done and self.rule(dict(zip(self.names, fin))))
        if self.p == 0:
            m_next = MEAN_SCALE * x
        else:
            m_next = min(max(self.m + ((MEAN_SCALE * x - self.m) >> MEAN_SHIFT), 0), MEAN_MAX)
        self.c = [0] * len(self.names) if done else fin
        self.m = m_next
        self.h = ([x] + self.h)[: self.hist]
        self.p = 0 if done else self.p + 1
        return af, done, before
