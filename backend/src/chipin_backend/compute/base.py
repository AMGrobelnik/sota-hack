"""The one interface every place-to-run implements."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from chipin_backend.agents.types import AgentResult, AgentSpec
from chipin_backend.config import BackendConfig, ComputeTier, RunMode
from chipin_backend.runs import RunDir


class Runner(ABC):
    """Runs one :class:`AgentSpec` somewhere and returns its result.

    The runner owns the machine: it resolves ``spec.workdir`` (default
    ``run.workspace``), puts the agent's events into ``run.event_sink()``,
    and may record machine facts in ``run.json`` (``RunRecord.compute``). It
    returns ``AgentResult(failed=True)`` for an agent that failed and raises
    only when the machine itself could not be had (no stock, no key, wrong OS).
    """

    #: The mode this runner serves.
    mode: ClassVar[RunMode]

    def __init__(self, config: BackendConfig) -> None:
        self.config = config

    @abstractmethod
    async def run(self, spec: AgentSpec, run: RunDir, *, tier: ComputeTier | None = None) -> AgentResult:
        """Run ``spec`` for ``run`` on hardware of ``tier`` (default ``config.compute.tier``)."""

    async def close(self) -> None:
        """Release every machine this runner holds (terminate pods). Idempotent."""
        return None


__all__ = ["Runner"]
