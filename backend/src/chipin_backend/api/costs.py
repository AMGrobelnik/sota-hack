"""One meaning for every ``cost`` event: the run's running total, and this agent's own part.

A run's ``cost`` events come from several places and their ``usd`` has meant
different things: a subagent's event (with ``agent``) carries that subagent's
own spend so far; the orchestrator's carries its own spend; the closing event
of a fan-out run carries the total with ``subagents_usd``; a follow-up's
carries the total so far; ``summaries_usd`` is the level summaries' spend,
never inside ``usd``. Summing ``usd`` over the events therefore counts most of
the run several times. :class:`CostLedger` reads them in order and gives every
event two fields that need no interpretation:

- ``run_total_usd``: what the whole run has cost so far (orchestrator,
  every subagent and the level summaries). The newest event's value is the
  run's cost; never add these up.
- ``agent_usd``: the spend so far of the agent the event is about (the
  subagent named by ``agent``, else the orchestrator).

The old fields stay as they were. The event log adds both fields as each
event is written, and to events of older runs as they are read back.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

COST = "cost"
FINISHED = "run.finished"


def _usd(value: Any) -> float:
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else 0.0


@dataclass
class CostLedger:
    """Running cost of one run, fed its events in ``seq`` order."""

    agents: dict[str, float] = field(default_factory=dict)
    subagents_reported: float = 0.0
    orchestrator: float = 0.0
    summaries: float = 0.0
    finished: bool = False

    @property
    def subagents(self) -> float:
        """The subagents' spend: their own events, or the closing event's sum when larger."""
        return max(sum(self.agents.values()), self.subagents_reported)

    @property
    def total(self) -> float:
        return self.orchestrator + self.subagents + self.summaries

    def fields(self, event: Mapping[str, Any]) -> dict[str, float]:
        """Take one event; for a ``cost`` event, its ``run_total_usd`` and ``agent_usd``."""
        kind = event.get("type")
        if kind == FINISHED:
            self.finished = True
            return {}
        if kind != COST:
            return {}
        usd = _usd(event.get("usd"))
        agent = event.get("agent")
        if isinstance(agent, str) and agent:
            self.agents[agent] = usd
            own = usd
        else:
            if "subagents_usd" in event:
                self.subagents_reported = _usd(event.get("subagents_usd"))
                self.orchestrator = max(0.0, usd - self.subagents_reported)
            elif self.finished:
                # A follow-up's event carries the run's total so far (subagents inside).
                self.orchestrator = max(0.0, usd - self.subagents)
            else:
                self.orchestrator = usd
            if "summaries_usd" in event:
                self.summaries = _usd(event.get("summaries_usd"))
            own = self.orchestrator
        return {"run_total_usd": round(self.total, 6), "agent_usd": round(own, 6)}


def annotate_costs(events: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """``events`` with ``run_total_usd`` and ``agent_usd`` on every ``cost`` event (copies)."""
    ledger = CostLedger()
    out: list[dict[str, Any]] = []
    for event in events:
        extra = ledger.fields(event)
        out.append({**event, **extra} if extra else dict(event))
    return out


__all__ = ["CostLedger", "annotate_costs"]
