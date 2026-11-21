"""The one interface every agent backend implements, and the name -> class registry."""

from __future__ import annotations

import importlib
from abc import ABC, abstractmethod
from typing import ClassVar

from chipmonk_backend.agents.types import AgentResult, AgentSpec, EventSink
from chipmonk_backend.config import AgentsConfig


class AgentBackend(ABC):
    """Runs one agent to completion in this process.

    A backend owns its loop (CLI under a PTY, OpenHands SDK, ...), its own
    retries, structured-output validation against ``spec.output_schema`` and
    the expected-files check. It never raises for an agent that merely failed:
    it returns ``AgentResult(failed=True, error=...)``. It raises only for a
    programming or configuration error (missing CLI, missing key).
    """

    #: Registry name, the value of ``AgentSpec.backend``.
    name: ClassVar[str]

    def __init__(self, config: AgentsConfig) -> None:
        self.config = config

    @abstractmethod
    async def run(self, spec: AgentSpec, sink: EventSink) -> AgentResult:
        """Run ``spec.prompts`` in order in one session inside ``spec.workdir``.

        ``spec.workdir`` is always set by the caller (a runner). Every event
        goes to ``sink`` as it happens, starting with ``agent_start`` and
        ending with ``agent_end``.
        """

    async def inject(self, message: str) -> None:
        """Queue a user message into the running session (optional)."""
        raise NotImplementedError(f"{self.name} does not support mid-run messages")

    async def close(self) -> None:
        """Stop the agent and every child process it started. Idempotent."""
        return None


#: name -> "module:Class", imported only when selected, so the OpenHands extra
#: is needed only by runs that use it.
BACKENDS: dict[str, str] = {
    "claude_cli": "chipmonk_backend.agents.claude_cli:ClaudeCliBackend",
    "openrouter": "chipmonk_backend.agents.openrouter_agent:OpenRouterAgentBackend",
    "stub": "chipmonk_backend.agents.stub:StubBackend",
}


def backend_class(name: str) -> type[AgentBackend]:
    """The backend class registered under ``name``; ``ValueError`` if none."""
    try:
        target = BACKENDS[name]
    except KeyError:
        raise ValueError(f"unknown agent backend {name!r}; known: {sorted(BACKENDS)}") from None
    module_name, class_name = target.split(":")
    cls = getattr(importlib.import_module(module_name), class_name)
    if not (isinstance(cls, type) and issubclass(cls, AgentBackend)):
        raise TypeError(f"{target} is not an AgentBackend")
    return cls


def backend_for(name: str | None, config: AgentsConfig) -> AgentBackend:
    """A new backend instance for ``name`` (``None`` = ``config.default_backend``)."""
    return backend_class(name or config.default_backend)(config)


__all__ = ["BACKENDS", "AgentBackend", "backend_class", "backend_for"]
