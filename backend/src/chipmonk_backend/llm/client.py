"""OpenRouter client for direct chat calls (no agent loop) and the model catalogue.

STUB: port the request shape and cost reading from AI Inventor's
``.claude/skills/aii-openrouter-llms/scripts/aii_or_call_llms.py``
(``core_openrouter_call``: cost from the response's ``usage.cost``) and
``aii_or_search_llms.py`` (catalogue via ``/models``), on async ``httpx``,
with :func:`chipmonk_backend.llm.retry.retry_paid_call` around each paid call.
Drop the metering-proxy route, the key file and the ability-server wrapper.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from chipmonk_backend.config import LlmConfig

Message = dict[str, Any]  # {"role": "system" | "user" | "assistant", "content": ...}
ReasoningEffort = Literal["minimal", "low", "medium", "high"]


@dataclass(frozen=True)
class ChatResult:
    """One completed chat call."""

    model: str  # the model that actually served the call
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0  # from usage.cost; 0.0 when the provider gives none
    finish_reason: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelInfo:
    """One catalogue entry."""

    id: str
    name: str
    context_length: int | None
    prompt_usd_per_mtok: float | None
    completion_usd_per_mtok: float | None
    supported_parameters: tuple[str, ...] = ()


class OpenRouterClient:
    """Async OpenRouter client. Use as ``async with OpenRouterClient(cfg) as client:``.

    ``api_key`` ``None`` = :func:`chipmonk_backend.llm.keys.openrouter_api_key`
    at first use. The key is sent only in the ``Authorization`` header and is
    never logged.
    """

    def __init__(self, config: LlmConfig, *, api_key: str | None = None) -> None:
        self.config = config
        self._api_key = api_key

    async def __aenter__(self) -> OpenRouterClient:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close the HTTP connection pool."""
        return None

    async def chat(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float | None = None,
        reasoning_effort: ReasoningEffort | None = None,
        response_format: dict[str, Any] | None = None,
        provider: dict[str, Any] | None = None,
    ) -> ChatResult:
        """One chat completion. ``model`` may be a preset name or an id
        (default ``config.default_model``); ``response_format`` is passed
        through for JSON-schema output; ``provider`` is OpenRouter's routing
        preference (``order``, ``allow_fallbacks``)."""
        raise NotImplementedError("OpenRouterClient.chat: port core_openrouter_call")

    async def list_models(self) -> list[ModelInfo]:
        """The live catalogue from ``/models``."""
        raise NotImplementedError("OpenRouterClient.list_models: port aii_or_search_llms")

    async def key_info(self) -> dict[str, Any]:
        """The key's limits and usage from ``/key``; spends nothing (auth check)."""
        raise NotImplementedError("OpenRouterClient.key_info")


__all__ = ["ChatResult", "Message", "ModelInfo", "OpenRouterClient", "ReasoningEffort"]
