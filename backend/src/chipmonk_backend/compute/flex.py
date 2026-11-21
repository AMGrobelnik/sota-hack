"""``flex`` mode: run agents on a Mac the team owns, at no rental cost.

Today Flex runs the agent directly on the Mac host as the logged-in user
(``compute.flex.isolation: host``), with the ``claude`` CLI logged in there.
Running each agent inside a macOS VM on the Mac is not built; a ``vm``
isolation value would be added here, behind the same
:class:`~chipmonk_backend.compute.base.Runner` interface.
"""

from __future__ import annotations

import sys
from typing import ClassVar

from chipmonk_backend.agents.types import AgentResult, AgentSpec
from chipmonk_backend.compute.local import LocalRunner
from chipmonk_backend.config import ComputeTier, RunMode
from chipmonk_backend.runs import RunDir


class FlexUnavailableError(RuntimeError):
    """Flex was selected on a machine that cannot serve it."""


class FlexRunner(LocalRunner):
    """In-process on a Mac host."""

    mode: ClassVar[RunMode] = "flex"

    def check_host(self) -> None:
        """``FlexUnavailableError`` unless this is macOS (when ``require_macos``)."""
        if self.config.compute.flex.require_macos and sys.platform != "darwin":
            raise FlexUnavailableError(f"flex needs a Mac host; this is {sys.platform}")

    async def run(self, spec: AgentSpec, run: RunDir, *, tier: ComputeTier | None = None) -> AgentResult:
        """Check the host, then run like :class:`LocalRunner`."""
        self.check_host()
        return await super().run(spec, run, tier=tier)


__all__ = ["FlexRunner", "FlexUnavailableError"]
