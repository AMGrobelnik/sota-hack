"""Event-level scoring of a per-window decision stream against consensus seizure seconds.

Rules (stated in README.md and in the published notes):
- events: runs of consensus seizure seconds; runs separated by gaps under MERGE_GAP_S are one event;
  events shorter than MIN_EVENT_S are not scored as events, but alarms over them are not false alarms;
- decision k is made at the end of its window, time t = k + WIN_S seconds;
- an event [on, off) is caught when any positive decision falls in [on, off + MARGIN_S];
  delay = first such decision time minus onset;
- alarms: runs of positive decisions, merged when the gap between them is under REFRACTORY_S;
  an alarm that overlaps no [on, off + MARGIN_S] of any labelled run is one false alarm.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from neonatal_eeg.data import WIN_S

MERGE_GAP_S = 10
MIN_EVENT_S = 10
MARGIN_S = 30
REFRACTORY_S = 60


def runs(b: np.ndarray) -> list[tuple[int, int]]:
    """[start, end) index pairs of the runs of ones in a 0/1 vector."""
    d = np.diff(np.concatenate([[0], b.astype(np.int8), [0]]))
    return list(zip(np.flatnonzero(d == 1).tolist(), np.flatnonzero(d == -1).tolist()))


def merge(rs: list[tuple[int, int]], gap: int) -> list[tuple[int, int]]:
    out: list[list[int]] = []
    for s, e in rs:
        if out and s - out[-1][1] < gap:
            out[-1][1] = e
        else:
            out.append([s, e])
    return [(s, e) for s, e in out]


def events_of(cons: np.ndarray) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    """(scored events, all labelled runs after merging) in seconds."""
    allr = merge(runs(cons), MERGE_GAP_S)
    return [r for r in allr if r[1] - r[0] >= MIN_EVENT_S], allr


@dataclass
class BabyScore:
    caught: int
    total: int
    false_alarms: int
    hours: float
    delays: list[float]


def score_baby(dec: np.ndarray, cons: np.ndarray) -> BabyScore:
    """dec: 0/1 per window (window k decided at time k + WIN_S)."""
    ev, allr = events_of(cons)
    t = np.arange(len(dec)) + WIN_S
    pos_t = t[dec.astype(bool)]
    caught, delays = 0, []
    for on, off in ev:
        hit = pos_t[(pos_t >= on) & (pos_t <= off + MARGIN_S)]
        if hit.size:
            caught += 1
            delays.append(float(hit[0] - on))
    alarms = merge([(int(t[s]), int(t[e - 1]) + 1) for s, e in runs(dec)], REFRACTORY_S)
    fa = 0
    for a0, a1 in alarms:
        if not any(a0 <= off + MARGIN_S and a1 > on for on, off in allr):
            fa += 1
    return BabyScore(caught, len(ev), fa, len(dec) / 3600.0, delays)


def pooled(scores: list[BabyScore]) -> dict:
    c = sum(s.caught for s in scores)
    n = sum(s.total for s in scores)
    fa = sum(s.false_alarms for s in scores)
    h = sum(s.hours for s in scores)
    d = [x for s in scores for x in s.delays]
    return {"caught": c, "total": n, "false_alarms": fa, "hours": h,
            "sens": c / n if n else float("nan"), "fah": fa / h if h else float("nan"),
            "delay_med": float(np.median(d)) if d else None}


def worst_sens(scores: list[BabyScore], min_events: int) -> float | None:
    v = [s.caught / s.total for s in scores if s.total >= min_events]
    return min(v) if v else None
