"""The dashboard's playback clock, so the backend can name a moment the way the page does.

The page (``dashboard/i1-playback.js`` on the site) plays a recorded run on
an active-time clock: events in ``seq`` order, those without a readable
``ts`` left out, time zero at the first event, 1x is real time between
events, and every silence longer than :data:`IDLE_GAP_S` is stepped over in
zero seconds. An event at wall time ``w`` therefore sits at
``max(0, w - w0 - skipped)`` seconds, ``skipped`` being the silences before it.
:class:`PlaybackClock` computes the same numbers, so ``?t=`` and Chippy's
``set_playback`` land on the moment a tool result names.
"""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

#: Silences longer than this are idle, not work (the page's ``IDLE_GAP_MS``).
IDLE_GAP_S = 30 * 60


def wall_s(ts: Any) -> float | None:
    """Epoch seconds of an ISO time (``Z`` allowed), or ``None`` when unreadable."""
    if not isinstance(ts, str) or not ts:
        return None
    try:
        when = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    if when.tzinfo is None:  # the page's Date.parse reads a zone-less time as local time
        return when.astimezone().timestamp()
    return when.timestamp()


def _seq(event: Mapping[str, Any]) -> int:
    value = event.get("seq")
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


@dataclass
class PlaybackClock:
    """Active seconds for every event of one run, as the dashboard's player counts them."""

    seqs: list[int] = field(default_factory=list)
    walls: list[float] = field(default_factory=list)
    active: list[float] = field(default_factory=list)
    gaps: list[dict[str, float]] = field(default_factory=list)

    @classmethod
    def from_events(cls, events: Iterable[Mapping[str, Any]]) -> PlaybackClock:
        timed: list[tuple[int, float]] = []
        for event in events:
            w = wall_s(event.get("ts")) if isinstance(event, Mapping) else None
            if w is not None:
                timed.append((_seq(event), w))
        timed.sort(key=lambda p: p[0])  # stable, as the page's sort by seq
        clock = cls()
        w0 = timed[0][1] if timed else 0.0
        prev: float | None = None
        skipped = 0.0
        for seq, w in timed:
            if prev is not None and w - prev > IDLE_GAP_S:
                clock.gaps.append({"t": round(prev - w0 - skipped, 3), "idle_s": round(w - prev, 3)})
                skipped += w - prev
            clock.seqs.append(seq)
            clock.walls.append(w)
            clock.active.append(max(0.0, w - w0 - skipped))
            prev = w
        return clock

    @property
    def total_s(self) -> float:
        """The finished run's length on the bar: its last event's active time."""
        return round(self.active[-1], 3) if self.active else 0.0

    def at_seq(self, seq: int) -> float | None:
        """Active seconds of the event ``seq``; between events, the last one at or before it."""
        if not self.seqs or isinstance(seq, bool) or not isinstance(seq, int):
            return None
        if seq in self.seqs:  # seqs are sorted but may repeat; take the first match
            return round(self.active[self.seqs.index(seq)], 3)
        at = bisect_right(self.seqs, seq) - 1
        return round(self.active[at], 3) if at >= 0 else 0.0

    def at_ts(self, ts: Any) -> float | None:
        """Active seconds of the wall time ``ts`` (ISO text or epoch seconds).

        Before the first event is 0; inside a skipped silence is the moment the
        silence starts (the clock steps over it); after the last event the clock
        runs on unless that stretch is itself a silence.
        """
        w = float(ts) if isinstance(ts, int | float) and not isinstance(ts, bool) else wall_s(ts)
        if w is None or not self.walls:
            return None
        indices = range(len(self.walls))
        prev = max((i for i in indices if self.walls[i] <= w), key=self.walls.__getitem__, default=None)
        if prev is None:
            return 0.0
        nxt = min((i for i in indices if self.walls[i] > w), key=self.walls.__getitem__, default=None)
        span = (self.walls[nxt] - self.walls[prev]) if nxt is not None else None
        delta = w - self.walls[prev]
        if (span is not None and span > IDLE_GAP_S) or (span is None and delta > IDLE_GAP_S):
            return round(self.active[prev], 3)
        moved = self.active[prev] + delta
        if nxt is not None:
            moved = min(moved, self.active[nxt])
        return round(moved, 3)

    def at(self, event: Mapping[str, Any]) -> float | None:
        """Active seconds of one event: by its ``seq``, else by its ``ts``."""
        seq = event.get("seq")
        if isinstance(seq, int) and not isinstance(seq, bool) and seq in self.seqs:
            return self.at_seq(seq)
        return self.at_ts(event.get("ts"))


def playback_time(
    events: Iterable[Mapping[str, Any]], *, seq: int | None = None, ts: Any = None
) -> float | None:
    """Where the dashboard's playback clock shows event ``seq`` or wall time ``ts`` of a run."""
    clock = PlaybackClock.from_events(events)
    if seq is not None:
        return clock.at_seq(seq)
    return clock.at_ts(ts)


__all__ = ["IDLE_GAP_S", "PlaybackClock", "playback_time", "wall_s"]
