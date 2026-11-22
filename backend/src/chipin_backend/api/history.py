"""Recorded runs for playback: the facts a run picker needs and a run's whole event history.

A dashboard plays an old run back from its ``events.jsonl`` (every event has a
``seq`` and a ``ts``). Two routes serve it, next to the live stream:

    GET /api/history                          -> {"runs": [facts, ...]} newest first
    GET /api/runs/{id}/history?from=&limit=   -> {"events": [...], "next", "total", ...}

The facts are computed from the event log already in memory, so listing many
runs reads no file. :func:`run_facts` is shared with the static export
(``export.py``), so a run looks the same served or exported, and so is
:func:`with_summaries`, which adds the summaries written after the run.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from chipin_backend.api.events import FINISHED, STAGES
from chipin_backend.api.summaries import SUMMARY

#: The longest title shown in a picker; the full brief stays in ``prompt``.
TITLE_CHARS = 90
#: Largest page ``GET /api/runs/{id}/history`` returns when ``limit`` is given.
MAX_PAGE = 5000


def _ms(ts: Any) -> float | None:
    """Epoch milliseconds of an ISO time, or ``None``."""
    if not isinstance(ts, str) or not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp() * 1000
    except ValueError:
        return None


def title_of(prompt: str) -> str:
    """The brief's first line, cut at :data:`TITLE_CHARS` on a word boundary."""
    line = (prompt or "").strip().splitlines()[0] if (prompt or "").strip() else ""
    if len(line) <= TITLE_CHARS:
        return line
    cut = line[: TITLE_CHARS - 1].rsplit(" ", 1)[0].rstrip(",;:. ")
    return cut + "…"


def _design_ids(events: Sequence[Mapping[str, Any]]) -> list[str]:
    """Design ids in arrival order, counted as ``designs.json`` keeps them.

    A record with ``previous_id`` (``prev_id`` in older runs) takes over the design of
    that id, as :func:`chipin_backend.api.designs.emit_design` does: a candidate renamed
    to the lab's ``design_id`` once compiled counts once, not twice.
    """
    order: list[str] = []
    for ev in events:
        if ev.get("type") != "design":
            continue
        d = ev.get("design") or ev.get("record")
        if not isinstance(d, Mapping) or not isinstance(d.get("id"), str):
            continue
        new = d["id"]
        prev = d.get("previous_id") or d.get("prev_id")
        if isinstance(prev, str) and prev in order and prev != new:
            if new in order:
                order.remove(prev)
            else:
                order[order.index(prev)] = new
        elif new not in order:
            order.append(new)
    return order


def counts_of(events: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    """How much the run did: events, designs, stages done, messages, tools, files, subagents."""
    by_type: dict[str, int] = {}
    tools: set[str] = set()
    stages_done: set[str] = set()
    for ev in events:
        kind = str(ev.get("type"))
        by_type[kind] = by_type.get(kind, 0) + 1
        if kind == "tool" and ev.get("call_id"):
            tools.add(str(ev["call_id"]))
        if kind == "stage" and ev.get("state") == "done":
            stages_done.add(str(ev.get("stage") or ev.get("name")))
    return {
        "events": len(events),
        "designs": len(_design_ids(events)),
        "stages_done": len(stages_done & set(STAGES)),
        "messages": by_type.get("message", 0),
        "tools": len(tools),
        "artifacts": by_type.get("artifact", 0),
        "metrics": by_type.get("metric", 0),
        "subagents": by_type.get("subagent.started", 0),
    }


def run_facts(record: Mapping[str, Any], events: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """What a run picker shows for one run, from its ``api.json`` record and its events.

    ``duration_s`` is first event to last event (to the last event so far for a
    run still going); ``chosen`` is the latest ``chosen`` event's chip, if any.
    """
    prompt = str(record.get("prompt") or "")
    if not prompt:
        started = next((e for e in events if e.get("type") == "run.started"), None)
        prompt = str((started or {}).get("prompt") or "")
    times = [t for t in (_ms(e.get("ts")) for e in events) if t is not None]
    chosen = None
    for ev in events:
        if ev.get("type") == "chosen" and isinstance(ev.get("chip"), str) and ev["chip"]:
            chosen = ev["chip"]
    finished = next((e for e in reversed(events) if e.get("type") == FINISHED), None)
    state = str(
        record.get("status") or (finished or {}).get("status") or ("running" if events else "unknown")
    )
    cost = record.get("cost") if isinstance(record.get("cost"), Mapping) else None
    facts: dict[str, Any] = {
        "id": str(record.get("id") or (events[0].get("run_id") if events else "")),
        "title": title_of(prompt),
        "prompt": prompt,
        "started_at": record.get("started_at") or (events[0].get("ts") if events else None),
        "finished_at": record.get("finished_at") or ((finished or {}).get("ts")),
        "duration_s": round((max(times) - min(times)) / 1000, 3) if times else 0.0,
        "state": state,
        "preset": record.get("preset"),
        "agent": record.get("agent"),
        "model": record.get("model"),
        "chosen": chosen,
        "counts": counts_of(events),
        "cost_usd": cost.get("usd") if cost else None,
        "last_seq": events[-1].get("seq") if events else 0,
    }
    return {k: v for k, v in facts.items() if v is not None}


def _anchor(cover: str, at: Mapping[str, int]) -> int:
    """The seq a covered id stands at: ``e<seq>`` and ``i<seq>`` name it, a summary id was resolved."""
    if cover in at:
        return at[cover]
    if cover[:1] in ("e", "i") and cover[1:].isdigit():
        return int(cover[1:])
    return 0


def with_summaries(
    events: Sequence[Mapping[str, Any]], summaries: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """``events`` plus the summaries written after the run (``chipin-backend summarise``).

    Summaries written live are already events (they carry a ``seq``) and are
    left as they are. Those of a replay have no ``seq``: they follow the last
    event, numbered on from it, with its ``ts`` (so the run's length does not
    change) and ``at``, the seq of the newest event each one covers, so a
    player can show it where it belongs. A later line with the same ``id``
    replaces an earlier one, as on the live stream.
    """
    out = [dict(e) for e in events]
    replayed = [
        s
        for s in summaries
        if isinstance(s, Mapping) and str(s.get("type", "")).startswith(SUMMARY) and "seq" not in s
    ]
    if not out or not replayed:
        return out
    last = out[-1]
    end = seq = int(last.get("seq", len(out)))
    at: dict[str, int] = {}
    for s in replayed:
        seq += 1
        covers = s.get("covers") if isinstance(s.get("covers"), list) else []
        anchor = max((_anchor(str(c), at) for c in covers), default=0) or end
        if isinstance(s.get("id"), str):
            at[s["id"]] = anchor
        out.append({"seq": seq, "ts": last.get("ts"), "run_id": last.get("run_id"), **s, "at": anchor})
    return out


def _finished(events: Sequence[Mapping[str, Any]]) -> bool:
    """Whether the run has ended: its last event, summaries written after it aside, is ``run.finished``."""
    for event in reversed(events):
        if not str(event.get("type", "")).startswith(SUMMARY):
            return event.get("type") == FINISHED
    return False


def history_page(
    events: Sequence[Mapping[str, Any]], *, start: int = 1, limit: int | None = None
) -> dict[str, Any]:
    """Events with ``seq >= start``, at most ``limit`` of them, and where the next page starts.

    ``next`` is the ``from`` of the following page, ``None`` when this page
    reaches the newest event.
    """
    rest = [e for e in events if int(e.get("seq", 0)) >= start]
    page = rest if limit is None else rest[:limit]
    more = limit is not None and len(rest) > limit
    return {
        "from": start,
        "events": list(page),
        "next": int(page[-1]["seq"]) + 1 if more and page else None,
        "total": len(events),
        "last_seq": int(events[-1]["seq"]) if events else 0,
        "finished": _finished(events),
    }


__all__ = [
    "MAX_PAGE",
    "TITLE_CHARS",
    "counts_of",
    "history_page",
    "run_facts",
    "title_of",
    "with_summaries",
]
