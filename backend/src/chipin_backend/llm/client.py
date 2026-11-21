"""OpenRouter client for direct chat calls (no agent loop) and the model catalogue.

Built on async ``httpx``: the cost of a call is the response's own ``usage.cost``, and every
paid call goes through :func:`chipin_backend.llm.retry.retry_paid_call`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import httpx

from chipin_backend.config import LlmConfig
from chipin_backend.llm.endpoints import BASE_URL
from chipin_backend.llm.keys import is_key_exhausted, openrouter_api_key
from chipin_backend.llm.presets import resolve_model
from chipin_backend.llm.providers import Provider
from chipin_backend.llm.retry import retry_paid_call

Message = dict[str, Any]  # {"role": "system" | "user" | "assistant", "content": ...}
ReasoningEffort = Literal["minimal", "low", "medium", "high"]

#: Longest slice of an error body kept in an exception message.
_BODY_SNIPPET = 500


class OpenRouterError(RuntimeError):
    """OpenRouter refused or failed a call.

    ``status_code`` is the HTTP status (or the ``error.code`` of a 200 answer
    that carries an error); ``key_exhausted`` says the key is out of credit,
    which no retry fixes.
    """

    def __init__(self, status_code: int | None, body: str) -> None:
        self.status_code = status_code
        self.body = body[:_BODY_SNIPPET]
        self.key_exhausted = is_key_exhausted(status_code, body)
        super().__init__(f"OpenRouter error {status_code}: {self.body}")


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
    provider: str = "openrouter"  # the provider that served the call


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

    ``api_key`` ``None`` = :func:`chipin_backend.llm.keys.openrouter_api_key`
    at first use. The key is sent only in the ``Authorization`` header and is
    never logged.
    """

    def __init__(
        self, config: LlmConfig, *, api_key: str | None = None, endpoint: Provider | None = None
    ) -> None:
        self.config = config
        self.endpoint = endpoint  # None = OpenRouter as configured in ``llm``
        self._api_key = api_key
        self._http: httpx.AsyncClient | None = None

    async def __aenter__(self) -> OpenRouterClient:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close the HTTP connection pool."""
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    def _client(self) -> httpx.AsyncClient:
        """The pooled HTTP client, created on first use (the key is read then)."""
        if self._http is None:
            if self.endpoint is not None:
                key = self._api_key or self.endpoint.api_key()
                base_url = self.endpoint.base_url
            else:
                key = self._api_key or openrouter_api_key()
                base_url = self.config.base_url or BASE_URL
            self._http = httpx.AsyncClient(
                base_url=base_url.rstrip("/") + "/",
                headers={"Authorization": f"Bearer {key}"},
                timeout=self.config.timeout_s,
            )
        return self._http

    async def _request(self, method: str, path: str, *, json: dict[str, Any] | None = None) -> Any:
        """One request, retried on transient faults; the decoded JSON body."""

        async def call() -> Any:
            response = await self._client().request(method, path, json=json)
            if response.is_error:
                raise httpx.HTTPStatusError(
                    f"OpenRouter {response.status_code}: {response.text[:_BODY_SNIPPET]}",
                    request=response.request,
                    response=response,
                )
            return response.json()

        try:
            return await retry_paid_call(call, attempts=self.config.max_attempts, idempotent=method == "GET")
        except httpx.HTTPStatusError as err:
            raise OpenRouterError(err.response.status_code, err.response.text) from err

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
        if self.endpoint is not None and self.endpoint.name != "openrouter":
            model_id = self.endpoint.model_for(model)
        else:
            model_id = resolve_model(model or self.config.default_model, self.config.presets)
        payload: dict[str, Any] = {"model": model_id, "messages": messages, "max_tokens": max_tokens}
        if temperature is not None:
            payload["temperature"] = temperature
        if reasoning_effort is not None:
            payload["reasoning"] = {"effort": reasoning_effort}
        if response_format is not None:
            payload["response_format"] = response_format
        if provider is not None:
            payload["provider"] = provider
        data = await self._request("POST", "chat/completions", json=payload)
        return _chat_result(data, model_id, self.endpoint.name if self.endpoint else "openrouter")

    async def list_models(self) -> list[ModelInfo]:
        """The live catalogue from ``/models``."""
        data = await self._request("GET", "models")
        return [_model_info(entry) for entry in data.get("data", [])]

    async def key_info(self) -> dict[str, Any]:
        """The key's limits and usage from ``/key``; spends nothing (auth check)."""
        data = await self._request("GET", "key")
        return dict(data.get("data", data))


def _chat_result(data: dict[str, Any], requested_model: str, provider: str = "openrouter") -> ChatResult:
    """A :class:`ChatResult` from a chat/completions body; an error body raises."""
    choices = data.get("choices") or []
    if not choices:
        error = data.get("error") or {}
        code = error.get("code") if isinstance(error, dict) else None
        raise OpenRouterError(code if isinstance(code, int) else None, str(error or data))
    choice = choices[0]
    message = choice.get("message") or {}
    usage = data.get("usage") or {}
    return ChatResult(
        model=data.get("model") or requested_model,
        provider=provider,
        text=message.get("content") or "",
        input_tokens=int(usage.get("prompt_tokens") or 0),
        output_tokens=int(usage.get("completion_tokens") or 0),
        cost_usd=float(usage.get("cost") or 0.0),
        finish_reason=choice.get("finish_reason"),
        raw=data,
    )


def _per_mtok(price: Any) -> float | None:
    """A per-token price string as US dollars per million tokens."""
    try:
        return float(price) * 1e6
    except (TypeError, ValueError):
        return None


def _model_info(entry: dict[str, Any]) -> ModelInfo:
    """A :class:`ModelInfo` from one ``/models`` entry."""
    pricing = entry.get("pricing") or {}
    return ModelInfo(
        id=entry["id"],
        name=entry.get("name") or entry["id"],
        context_length=entry.get("context_length"),
        prompt_usd_per_mtok=_per_mtok(pricing.get("prompt")),
        completion_usd_per_mtok=_per_mtok(pricing.get("completion")),
        supported_parameters=tuple(entry.get("supported_parameters") or ()),
    )


__all__ = [
    "ChatResult",
    "Message",
    "ModelInfo",
    "OpenRouterClient",
    "OpenRouterError",
    "ReasoningEffort",
]
