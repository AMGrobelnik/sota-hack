"""``local`` mode: run the agent in this process, on whatever machine this is.

The same three lines as AI Inventor's ``LocalEnv``: pick the backend, run it.
Also what a RunPod worker pod uses to run the job it was sent.
"""

from __future__ import annotations

from dataclasses import replace
from typing import ClassVar

from chipmonk_backend.agents.base import backend_for
from chipmonk_backend.agents.types import AgentResult, AgentSpec
from chipmonk_backend.compute.base import Runner
from chipmonk_backend.config import ComputeTier, RunMode
from chipmonk_backend.runs import RunDir


class LocalRunner(Runner):
    """In-process; ``tier`` is ignored because the hardware is what it is."""

    mode: ClassVar[RunMode] = "local"

    async def run(self, spec: AgentSpec, run: RunDir, *, tier: ComputeTier | None = None) -> AgentResult:
        """Resolve the workdir, then run the spec's backend to completion."""
        del tier  # no machine to size here
        workdir = spec.workdir or run.workspace
        workdir.mkdir(parents=True, exist_ok=True)
        backend = backend_for(spec.backend, self.config.agents)
        try:
            return await backend.run(replace(spec, workdir=workdir), run.event_sink())
        finally:
            await backend.close()


__all__ = ["LocalRunner"]
