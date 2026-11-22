"""Chippy's model: one streamed completion, walked over pinned OpenRouter tiers.

The design follows the helper agent of the product this backend came from:
a first paid model pinned to a short list of providers, each attempt pinned
to one provider with fallbacks off (so a failure is visible, not silently
re-routed), then a different paid model on different providers, so one
model's or one host's outage does not take the helper down. Every attempt
streams, asks for usage on the last chunk (``usage.include``), and stops the
walk once words have reached the user: a second provider would write a
different answer under them. ChipIn routes to paid OpenRouter models only,
so there is no free pool behind the two rungs.

The model is a seam: anything with :meth:`HelperModel.stream` will do, which
is how the tests drive whole turns with scripted replies and no network.
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from chipin_backend.llm.endpoints import CHAT_COMPLETIONS_URL
from chipin_backend.scrub import scrub_value


class Rung(BaseModel):
    """One model and the providers it is pinned to, in order."""

    model_config = ConfigDict(extra="forbid")

    model: str
    providers: list[str] = Field(default_factory=list)
    budget_s: float = 30.0
    usd_per_m_in: float = 0.0  # used only when the provider reports no cost
    usd_per_m_out: float = 0.0


@dataclass
class ToolCall:
    """One tool call the model asked for."""

    id: str
    name: str
    arguments: Any

    def signature(self) -> str:
        return f"{self.name}:{json.dumps(self.arguments, sort_keys=True, default=str)}"


@dataclass
class ModelReply:
    """A finished completion, or the reason there is none."""

    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    model: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    cost_usd: float = 0.0
    error: str = ""


class HelperModel(Protocol):
    """Yields ``{"type": "delta", "text"}`` events, then one ``{"type": "reply", "reply"}``."""

    def stream(
        self, *, messages: list[dict[str, Any]], tools: Sequence[dict[str, Any]], tool_choice: str
    ) -> AsyncIterator[dict[str, Any]]: ...


class _Accumulator:
    """Builds one assistant message from OpenAI-style stream chunks."""

    def __init__(self) -> None:
        self.text = ""
        self.calls: dict[int, dict[str, str]] = {}
        self.usage: dict[str, Any] = {}

    def feed(self, chunk: dict[str, Any]) -> str:
        if isinstance(chunk.get("usage"), dict):
            self.usage = chunk["usage"]
        choices = chunk.get("choices") or []
        if not choices:
            return ""
        delta = choices[0].get("delta") or {}
        for part in delta.get("tool_calls") or []:
            slot = self.calls.setdefault(int(part.get("index", 0)), {"id": "", "name": "", "arguments": ""})
            fn = part.get("function") or {}
            slot["id"] = part.get("id") or slot["id"]
            slot["name"] += fn.get("name") or ""
            slot["arguments"] += fn.get("arguments") or ""
        text = delta.get("content") or ""
        self.text += text
        return text

    def reply(self, model: str, rung: Rung) -> ModelReply:
        calls = []
        for index, slot in sorted(self.calls.items()):
            try:
                args = json.loads(slot["arguments"] or "{}")
            except json.JSONDecodeError:
                args = {"_unparsed": slot["arguments"][:500]}
            calls.append(ToolCall(id=slot["id"] or f"call_{index}", name=slot["name"], arguments=args))
        tokens_in = int(self.usage.get("prompt_tokens") or 0)
        tokens_out = int(self.usage.get("completion_tokens") or 0)
        cost = self.usage.get("cost")
        if not isinstance(cost, int | float):
            cost = (tokens_in * rung.usd_per_m_in + tokens_out * rung.usd_per_m_out) / 1e6
        return ModelReply(
            text=self.text,
            tool_calls=calls,
            model=model,
            usage={"tokens_in": tokens_in, "tokens_out": tokens_out},
            cost_usd=float(cost),
        )


class OpenRouterLadder:
    """The production model: rungs walked in order, each provider pinned."""

    def __init__(
        self,
        rungs: Sequence[Rung],
        *,
        api_key: str,
        attempt_timeout_s: float = 30.0,
        url: str = CHAT_COMPLETIONS_URL,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.transport = transport
        self.rungs = list(rungs)
        self.api_key = api_key
        self.attempt_timeout_s = attempt_timeout_s
        self.url = url

    def _payload(
        self,
        rung: Rung,
        provider: str,
        messages: list[dict[str, Any]],
        tools: Sequence[dict[str, Any]],
        tool_choice: str,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": rung.model,
            "messages": scrub_value(messages),  # nothing private leaves the machine
            "tools": list(tools),
            "tool_choice": tool_choice,
            "stream": True,
            "usage": {"include": True},
        }
        if provider:
            payload["provider"] = {"order": [provider], "allow_fallbacks": False}
        return payload

    async def stream(
        self, *, messages: list[dict[str, Any]], tools: Sequence[dict[str, Any]], tool_choice: str
    ) -> AsyncIterator[dict[str, Any]]:
        errors: list[str] = []
        headers = {"Authorization": f"Bearer {self.api_key}", "X-Title": "ChipIn Chippy"}
        for rung in self.rungs:
            deadline = time.monotonic() + rung.budget_s
            for provider in rung.providers or [""]:
                remaining = deadline - time.monotonic()
                if remaining < 3:
                    errors.append(f"{rung.model}: out of time")
                    break
                acc, spoke, failure = _Accumulator(), False, ""
                payload = self._payload(rung, provider, messages, tools, tool_choice)
                try:
                    async with (
                        httpx.AsyncClient(
                            timeout=min(self.attempt_timeout_s, remaining), transport=self.transport
                        ) as client,
                        client.stream("POST", self.url, json=payload, headers=headers) as response,
                    ):
                        if response.status_code != 200:
                            body = (await response.aread())[:300].decode("utf-8", "replace")
                            failure = f"HTTP {response.status_code}"
                            logger.warning(
                                "chippy: {} via {} {}: {}", rung.model, provider or "any", failure, body
                            )
                        else:
                            async for line in response.aiter_lines():
                                if not line.startswith("data:"):
                                    continue
                                data = line[5:].strip()
                                if data == "[DONE]":
                                    break
                                try:
                                    chunk = json.loads(data)
                                except json.JSONDecodeError:
                                    continue
                                if chunk.get("error"):
                                    failure = "upstream error"
                                    break
                                text = acc.feed(chunk)
                                if text:
                                    spoke = True
                                    yield {"type": "delta", "text": text}
                except httpx.HTTPError as exc:
                    failure = type(exc).__name__
                reply = acc.reply(f"{rung.model} via {provider or 'openrouter'}", rung)
                if not failure and not reply.text and not reply.tool_calls:
                    failure = "empty reply"
                if not failure:
                    yield {"type": "reply", "reply": reply}
                    return
                errors.append(f"{rung.model} via {provider or 'any'}: {failure}")
                if spoke:
                    cut = ModelReply(
                        text=reply.text, model=reply.model, cost_usd=reply.cost_usd, error="cut off"
                    )
                    yield {"type": "reply", "reply": cut}
                    return
        yield {"type": "reply", "reply": ModelReply(error="no model answered (" + "; ".join(errors) + ")")}


__all__ = ["HelperModel", "ModelReply", "OpenRouterLadder", "Rung", "ToolCall"]
