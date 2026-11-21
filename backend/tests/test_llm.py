"""OpenRouter client, retry policy and key checks, against a mocked HTTP transport."""

from __future__ import annotations

import functools
import json
from typing import Any

import httpx
import pytest

from chipmonk_backend.config import LlmConfig
from chipmonk_backend.llm import client as client_mod
from chipmonk_backend.llm import retry as retry_mod
from chipmonk_backend.llm.client import OpenRouterClient, OpenRouterError
from chipmonk_backend.llm.keys import is_key_exhausted
from chipmonk_backend.llm.retry import is_retryable, retry_paid_call

CHAT_OK = {
    "id": "gen-1",
    "model": "openai/gpt-5-nano",
    "choices": [{"message": {"role": "assistant", "content": "pong"}, "finish_reason": "stop"}],
    "usage": {"prompt_tokens": 13, "completion_tokens": 9, "cost": 4.4e-05},
}


@pytest.fixture(autouse=True)
def _no_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(retry_mod, "BACKOFF_S", (0.0, 0.0, 0.0, 0.0))


def _status_error(status: int, headers: dict[str, str] | None = None) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    response = httpx.Response(status, headers=headers, request=request)
    return httpx.HTTPStatusError("err", request=request, response=response)


def _mock_client(
    monkeypatch: pytest.MonkeyPatch, handler: Any, *, presets: dict[str, str] | None = None
) -> OpenRouterClient:
    """A client whose HTTP calls go to ``handler`` instead of the network."""
    monkeypatch.setattr(
        client_mod.httpx,
        "AsyncClient",
        functools.partial(httpx.AsyncClient, transport=httpx.MockTransport(handler)),
    )
    return OpenRouterClient(LlmConfig(presets=presets or {}, max_attempts=3), api_key="test-key")


@pytest.mark.parametrize(
    ("err", "expected"),
    [
        (_status_error(429), (True, None)),
        (_status_error(503, {"Retry-After": "3"}), (True, 3.0)),
        (_status_error(524), (True, None)),
        (_status_error(429, {"Retry-After": "3600"}), (True, retry_mod.RETRY_AFTER_CAP_S)),
        (_status_error(400), (False, None)),
        (_status_error(402), (False, None)),
        (httpx.ConnectError("refused"), (True, None)),
        (httpx.ReadTimeout("slow"), (False, None)),
        (ValueError("bug"), (False, None)),
    ],
)
def test_is_retryable(err: BaseException, expected: tuple[bool, float | None]) -> None:
    assert is_retryable(err) == expected


async def test_retry_paid_call_retries_transient_then_succeeds() -> None:
    calls = 0

    async def call() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise _status_error(502)
        return "ok"

    assert await retry_paid_call(call, attempts=5) == "ok"
    assert calls == 3


async def test_retry_paid_call_reraises_original_errors() -> None:
    calls = 0

    async def transient() -> None:
        nonlocal calls
        calls += 1
        raise _status_error(429)

    with pytest.raises(httpx.HTTPStatusError):
        await retry_paid_call(transient, attempts=2)
    assert calls == 2

    async def fatal() -> None:
        raise ValueError("not transient")

    with pytest.raises(ValueError, match="not transient"):
        await retry_paid_call(fatal, attempts=5)


@pytest.mark.parametrize(
    ("status", "body", "expected"),
    [
        (402, "", True),
        (403, '{"error":{"message":"Key limit exceeded (daily limit)"}}', True),
        (401, "key LIMIT exceeded", True),
        (403, "forbidden", False),
        (401, "No auth credentials found", False),
        (429, "Key limit exceeded", False),
        (None, None, False),
    ],
)
def test_is_key_exhausted(status: int | None, body: str | None, expected: bool) -> None:
    assert is_key_exhausted(status, body) is expected


async def test_chat_request_shape_and_cost(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=CHAT_OK)

    async with _mock_client(monkeypatch, handler, presets={"cheap": "openai/gpt-5-nano"}) as client:
        result = await client.chat(
            [{"role": "user", "content": "ping"}],
            model="cheap",
            max_tokens=50,
            reasoning_effort="low",
            provider={"order": ["openai"]},
        )
    assert result.text == "pong"
    assert result.cost_usd == pytest.approx(4.4e-05)
    assert (result.input_tokens, result.output_tokens, result.finish_reason) == (13, 9, "stop")
    request = seen[0]
    assert request.url.path == "/api/v1/chat/completions"
    assert request.headers["Authorization"] == "Bearer test-key"
    payload = json.loads(request.content)
    assert payload["model"] == "openai/gpt-5-nano"
    assert payload["reasoning"] == {"effort": "low"}
    assert payload["provider"] == {"order": ["openai"]}
    assert "temperature" not in payload


async def test_chat_retries_a_429_then_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    answers = iter([httpx.Response(429, json={"error": "busy"}), httpx.Response(200, json=CHAT_OK)])
    async with _mock_client(monkeypatch, lambda _r: next(answers)) as client:
        result = await client.chat([{"role": "user", "content": "ping"}], model="openai/gpt-5-nano")
    assert result.text == "pong"


async def test_chat_out_of_credit_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(402, json={"error": {"message": "Insufficient credits"}})

    async with _mock_client(monkeypatch, handler) as client:
        with pytest.raises(OpenRouterError) as info:
            await client.chat([{"role": "user", "content": "ping"}], model="openai/gpt-5-nano")
    assert info.value.key_exhausted and info.value.status_code == 402
    assert calls == 1


async def test_chat_error_inside_a_200_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    body = {"error": {"code": 502, "message": "upstream failed"}}
    async with _mock_client(monkeypatch, lambda _r: httpx.Response(200, json=body)) as client:
        with pytest.raises(OpenRouterError, match="upstream failed"):
            await client.chat([{"role": "user", "content": "ping"}], model="openai/gpt-5-nano")


async def test_list_models_and_key_info(monkeypatch: pytest.MonkeyPatch) -> None:
    models = {
        "data": [
            {
                "id": "openai/gpt-5-nano",
                "name": "GPT-5 Nano",
                "context_length": 400000,
                "pricing": {"prompt": "0.00000005", "completion": "0.0000004"},
                "supported_parameters": ["reasoning", "tools"],
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json=models)
        return httpx.Response(200, json={"data": {"label": "k", "usage": 1.5, "limit": None}})

    async with _mock_client(monkeypatch, handler) as client:
        [info] = await client.list_models()
        key = await client.key_info()
    assert info.prompt_usd_per_mtok == pytest.approx(0.05)
    assert info.completion_usd_per_mtok == pytest.approx(0.4)
    assert info.supported_parameters == ("reasoning", "tools")
    assert key["usage"] == 1.5


@pytest.mark.live
async def test_live_openrouter_chat(config: Any) -> None:
    """One real call to the cheap preset (needs ``OPENROUTER_API_KEY``)."""
    from chipmonk_backend.llm.keys import has_openrouter_key

    if not has_openrouter_key():
        pytest.skip("OPENROUTER_API_KEY is not set")
    async with OpenRouterClient(config.llm) as client:
        result = await client.chat(
            [{"role": "user", "content": "Reply with the single word: pong"}], model="cheap", max_tokens=200
        )
    assert "pong" in result.text.lower()
    assert result.cost_usd > 0
