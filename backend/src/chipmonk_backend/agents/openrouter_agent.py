"""``openrouter`` backend: an agent loop on any OpenRouter model.

Uses the OpenHands Agent SDK (LiteLLM underneath) with terminal, file-editor
and task-tracker tools; install with ``uv pip install -e '.[openhands]'`` and
have ``tmux`` on PATH. Import the SDK inside :meth:`run` only, so the base
install keeps working without the extra. Unlike ``claude_cli`` it needs only
``OPENROUTER_API_KEY``, which makes it the easy backend on RunPod pods.

STUB: port from AI Inventor's ``aii_lib/src/aii_lib/agent_backend/
sdk_openhands_agent/``: ``agent.py``, ``config.py``
(``build_run_config``, ``_normalize_openrouter_model``: LiteLLM ``openrouter/``
prefix), ``_agent/{_llm,_build,_turn,_struct_out,_fallback,_retry,_result,
_mcp}.py``, ``paid_retry.py``, ``session_store.py``,
``openhands_tel_adapter.py`` (cost from LiteLLM ``accumulated_cost``). Leave
out ``_capacity.py``, ``_free_signal.py``, ``_model_unavailable.py`` and every
``free_router`` / ``openrouter_meter`` / DBOS use.
"""

from __future__ import annotations

from typing import ClassVar

from chipmonk_backend.agents.base import AgentBackend
from chipmonk_backend.agents.types import AgentResult, AgentSpec, EventSink
from chipmonk_backend.config import OpenRouterAgentConfig


class OpenRouterAgentBackend(AgentBackend):
    """One OpenHands conversation per :meth:`run`."""

    name: ClassVar[str] = "openrouter"

    @property
    def openrouter(self) -> OpenRouterAgentConfig:
        """This backend's config section."""
        return self.config.openrouter

    async def run(self, spec: AgentSpec, sink: EventSink) -> AgentResult:
        """Build the LLM (``num_retries=0``; retries live in ``llm.retry``),
        the tools and the conversation in ``spec.workdir``; send every prompt;
        emit events per tick; validate ``spec.output_schema``; fall back to
        ``fallback_model`` once on a model-level failure."""
        raise NotImplementedError("openrouter agent backend: port from sdk_openhands_agent")


__all__ = ["OpenRouterAgentBackend"]
