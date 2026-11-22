"""``local`` mode: run the agent in this process, on whatever machine this is.

Pick the agent backend, prepare its working folder (the chip-lab skill when
the lab is on) and run it.
Also what a RunPod worker pod uses to run the job it was sent.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import replace
from typing import ClassVar

from loguru import logger

from chipin_backend.agents.base import AgentBackend, backend_for
from chipin_backend.agents.types import AgentEvent, AgentResult, AgentSpec
from chipin_backend.chiplab import install_skill
from chipin_backend.compute.base import Runner
from chipin_backend.config import ComputeTier, RunMode
from chipin_backend.runs import RunDir


class LocalRunner(Runner):
    """In-process; ``tier`` is ignored because the hardware is what it is.

    ``spec.timeout_s`` is enforced here as a wall clock over the whole agent:
    past it the backend is cancelled and closed (which stops its child
    processes) and the result is a failed one.
    """

    mode: ClassVar[RunMode] = "local"
    _backend: AgentBackend | None = None

    async def run(self, spec: AgentSpec, run: RunDir, *, tier: ComputeTier | None = None) -> AgentResult:
        """Resolve the workdir, install the chip-lab skill into it when the lab is on
        (:func:`~chipin_backend.chiplab.install_skill`; only inside the run folder),
        then run the spec's backend to completion or its timeout."""
        del tier  # no machine to size here
        workdir = spec.workdir or run.workspace
        workdir.mkdir(parents=True, exist_ok=True)
        backend = backend_for(spec.backend, self.config.agents, self.config.providers)
        if workdir.resolve().is_relative_to(run.path.resolve()):
            await asyncio.to_thread(install_skill, workdir, backend.name)
        else:
            logger.info("agent {}: working folder outside the run folder; no chip-lab skill", spec.name)
        sink = run.event_sink()
        started = time.monotonic()
        self._backend = backend
        deadline = _deadline(spec.timeout_s)
        try:
            async with deadline:
                return await backend.run(replace(spec, workdir=workdir), sink)
        except TimeoutError:
            if not deadline.expired():
                raise  # the backend's own TimeoutError, not our wall clock
            error = f"timed out after {spec.timeout_s}s"
            logger.warning("agent {} {}", spec.name, error)
            sink.emit(AgentEvent("error", spec.name, {"message": error}))
            return AgentResult(
                agent=spec.name, failed=True, error=error, duration_s=time.monotonic() - started
            )
        finally:
            self._backend = None
            await backend.close()

    async def inject(self, message: str) -> None:
        """Queue a user message into the running agent; ``RuntimeError`` when none runs."""
        if self._backend is None:
            raise RuntimeError("no agent is running")
        await self._backend.inject(message)


def _deadline(timeout_s: int | None) -> asyncio.Timeout:
    """``asyncio.timeout`` for a positive ``timeout_s``, else no limit."""
    return asyncio.timeout(timeout_s if timeout_s and timeout_s > 0 else None)


__all__ = ["LocalRunner"]
