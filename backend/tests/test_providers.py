"""Model providers: each request goes to its own base URL with its own key, an
unconfigured provider is refused, a missing key names its variable, health lists them."""

from __future__ import annotations

import functools
from pathlib import Path
from typing import Any

import httpx
import pytest
from aiohttp.test_utils import TestClient, TestServer

from chipin_backend import cli
from chipin_backend.agents import AgentSpec, backend_for
from chipin_backend.agents.openrouter_agent import normalize_model
from chipin_backend.api.config import ApiConfig
from chipin_backend.api.server import TOKEN_HEADER, create_app
from chipin_backend.config import BackendConfig
from chipin_backend.llm import client as client_mod
from chipin_backend.llm.client import OpenRouterClient
from chipin_backend.llm.keys import MissingKeyError
from chipin_backend.llm.providers import ProviderError, provider_status, resolve_provider

TOKEN = "test-token"
ANSWER = {"model": "m", "choices": [{"message": {"content": "hi"}, "finish_reason": "stop"}]}


def _record(monkeypatch: pytest.MonkeyPatch) -> list[httpx.Request]:
    """Send every client's HTTP call to a mock that records the request."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=ANSWER)

    monkeypatch.setattr(
        client_mod.httpx,
        "AsyncClient",
        functools.partial(httpx.AsyncClient, transport=httpx.MockTransport(handler)),
    )
    return seen


async def test_each_provider_calls_its_own_url_with_its_own_key(
    config: BackendConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    monkeypatch.setenv("TINKER_API_KEY", "tk-key")
    seen = _record(monkeypatch)
    for name, model in (("openrouter", "vendor/x"), ("tinker", "thinkingmachines/Inkling-2-Mini")):
        endpoint = resolve_provider(config.providers, name)
        async with OpenRouterClient(config.llm, endpoint=endpoint) as client:
            result = await client.chat([{"role": "user", "content": "hi"}], model=model)
        assert result.provider == name
    or_req, tk_req = seen
    assert str(or_req.url) == "https://openrouter.ai/api/v1/chat/completions"
    assert or_req.headers["Authorization"] == "Bearer or-key"
    assert str(tk_req.url) == config.providers["tinker"].base_url + "/chat/completions"
    assert tk_req.headers["Authorization"] == "Bearer tk-key"
    assert b"thinkingmachines/Inkling-2-Mini" in tk_req.content


async def test_tinker_uses_its_default_model(config: BackendConfig, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TINKER_API_KEY", "tk-key")
    seen = _record(monkeypatch)
    endpoint = resolve_provider(config.providers, "tinker")
    async with OpenRouterClient(config.llm, endpoint=endpoint) as client:
        await client.chat([{"role": "user", "content": "hi"}])
    assert b'"model": "thinkingmachines/Inkling-2-Mini"' in seen[0].content.replace(b'":"', b'": "')


def test_unconfigured_and_unknown_providers_are_refused(config: BackendConfig) -> None:
    with pytest.raises(ProviderError, match=r"callosum.*not configured.*no public endpoint"):
        resolve_provider(config.providers, "callosum")
    with pytest.raises(ProviderError, match="unknown provider 'nope'"):
        resolve_provider(config.providers, "nope")


async def test_agent_backend_refuses_callosum(config: BackendConfig, tmp_path: Path) -> None:
    backend = backend_for("openrouter", config.agents, config.providers)
    spec = AgentSpec(name="a", prompts=["x"], provider="callosum", workdir=tmp_path)
    with pytest.raises(ProviderError, match="not configured"):
        await backend.run(spec, sink=None)  # type: ignore[arg-type]


async def test_missing_key_names_the_variable(config: BackendConfig, tmp_path: Path) -> None:
    backend = backend_for("openrouter", config.agents, config.providers)
    spec = AgentSpec(name="a", prompts=["x"], provider="tinker", workdir=tmp_path)
    with pytest.raises(MissingKeyError, match="TINKER_API_KEY"):
        await backend.run(spec, sink=None)  # type: ignore[arg-type]


def test_cli_missing_key_is_one_clear_line_not_a_trace(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    env = tmp_path / "e.env"
    env.write_text("", encoding="utf-8")
    code = cli.main(["--env-file", str(env), "ask", "--provider", "tinker", "hi"])
    assert code == 2


def test_cli_unconfigured_provider_exits_2(tmp_path: Path) -> None:
    assert cli.main(["ask", "--provider", "callosum", "hi"]) == 2
    assert cli.main(["run", "--provider", "callosum", "--prompt", "x"]) == 2


def test_cli_provider_needs_the_openrouter_backend() -> None:
    assert cli.main(["run", "--backend", "stub", "--provider", "tinker", "--prompt", "x"]) == 2


def test_model_ids() -> None:
    assert normalize_model("vendor/slug") == "openrouter/vendor/slug"
    assert (
        normalize_model("thinkingmachines/Inkling-2-Mini", "tinker")
        == "openai/thinkingmachines/Inkling-2-Mini"
    )


def test_status_lists_names_only(config: BackendConfig, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TINKER_API_KEY", "secret-value")
    monkeypatch.setenv("CALLOSUM_API_KEY", "x")
    status = provider_status(config.providers)
    assert status == [
        {"name": "openrouter", "configured": True, "key_present": False},
        {"name": "tinker", "configured": True, "key_present": True},
        {"name": "callosum", "configured": False, "key_present": False},  # no endpoint: never ready
    ]
    assert "secret-value" not in repr(status)


async def _server(config: BackendConfig) -> TestClient:
    api = ApiConfig(keepalive_s=0.2, progress_poll_s=0.02, stub_step_s=0.01, run_timeout_s=60)
    app = create_app(config, api, token=TOKEN, agent="openrouter")
    return TestClient(TestServer(app))


async def test_health_lists_providers_by_name(config: BackendConfig, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TINKER_API_KEY", "secret-value")
    async with await _server(config) as c:
        resp = await c.get("/api/health")
        text = await resp.text()
        body: dict[str, Any] = await resp.json()
    assert {p["name"]: p["key_present"] for p in body["providers"]} == {
        "openrouter": False,
        "tinker": True,
        "callosum": False,
    }
    assert "secret-value" not in text


async def test_post_run_refuses_bad_provider_before_starting(config: BackendConfig) -> None:
    headers = {TOKEN_HEADER: TOKEN}
    async with await _server(config) as c:
        for provider, expect in (("callosum", "not configured"), ("tinker", "TINKER_API_KEY")):
            resp = await c.post("/api/runs", json={"prompt": "p", "provider": provider}, headers=headers)
            assert resp.status == 400
            assert expect in (await resp.json())["error"]
        assert (await (await c.get("/api/runs", headers=headers)).json())["runs"] == []
