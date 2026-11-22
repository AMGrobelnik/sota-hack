"""Talking to a run's agent: messages during a run, follow-ups after it, per harness, no model calls."""

from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from aiohttp import ClientResponse
from aiohttp.test_utils import TestClient, TestServer

from chipin_backend.agents import AgentEvent, AgentSpec, backend_for
from chipin_backend.api.config import ApiConfig
from chipin_backend.api.events import EventLog
from chipin_backend.api.manager import API_RECORD_FILE, ApiRun, RequestError, RunManager
from chipin_backend.api.server import TOKEN_HEADER, create_app
from chipin_backend.api.steer import DELIVERED_TEXT, MAX_MESSAGE_CHARS, Steering
from chipin_backend.api.translate import Translator
from chipin_backend.config import BackendConfig
from chipin_backend.runs import JsonlEventSink, RunDir

TOKEN = "steer-test-token"
AUTH = {TOKEN_HEADER: TOKEN}
FAKE_CLI = Path(__file__).with_name("fake_claude_cli.py")


def _config(config: BackendConfig) -> BackendConfig:
    flex = config.compute.flex.model_copy(update={"require_macos": False})
    return config.model_copy(update={"compute": config.compute.model_copy(update={"flex": flex})})


def _client(config: BackendConfig, step_s: float) -> TestClient:
    api = ApiConfig(keepalive_s=0.2, progress_poll_s=0.02, stub_step_s=step_s, run_timeout_s=60)
    return TestClient(TestServer(create_app(_config(config), api, token=TOKEN, agent="stub")))


@pytest.fixture
async def fast(config: BackendConfig) -> AsyncIterator[TestClient]:
    async with _client(config, 0.01) as c:
        yield c


@pytest.fixture
async def paced(config: BackendConfig) -> AsyncIterator[TestClient]:
    """Steps of 0.5 s: long enough to message the stub between them."""
    async with _client(config, 0.5) as c:
        yield c


async def _start(client: TestClient) -> str:
    resp = await client.post("/api/runs", json={"prompt": "A ring that counts breaths"}, headers=AUTH)
    assert resp.status == 201
    return str((await resp.json())["id"])


async def _read(resp: ClientResponse, until: str = "run.finished") -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    async with asyncio.timeout(30):
        async for raw in resp.content:
            line = raw.decode().rstrip("\n")
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
                if events[-1]["type"] == until:
                    break
    return events


async def _stream(client: TestClient, run_id: str, start: int = 1) -> ClientResponse:
    return await client.get(f"/api/runs/{run_id}/events", params={"token": TOKEN, "from": str(start)})


async def _say(client: TestClient, run_id: str, text: str) -> dict[str, Any]:
    resp = await client.post(f"/api/runs/{run_id}/messages", json={"text": text}, headers=AUTH)
    assert resp.status == 202, await resp.text()
    return dict(await resp.json())


def _seq(events: list[dict[str, Any]], pred: Any) -> int:
    return next(e["seq"] for e in events if pred(e))


# ---- through the API, on the scripted stub ----


async def test_messages_during_a_run_are_recorded_delivered_answered_in_order(
    paced: TestClient, config: BackendConfig
) -> None:
    run_id = await _start(paced)
    resp = await _stream(paced, run_id)
    await _read(resp, until="stage")
    first = await _say(paced, run_id, "use 8-bit weights")
    second = await _say(paced, run_id, "name the chosen design X")
    assert (first["id"], first["delivery"]) == ("m1", "live")
    assert (second["id"], second["delivery"]) == ("m2", "live")
    events = await _read(resp)

    users = [e for e in events if e["type"] == "message" and e.get("role") == "user"]
    assert [(e["message_id"], e["text"]) for e in users] == [
        ("m1", "use 8-bit weights"),
        ("m2", "name the chosen design X"),
    ]
    delivered = [e for e in events if e["type"] == "status" and e.get("text") == DELIVERED_TEXT]
    assert [e["message_id"] for e in delivered] == ["m1", "m2"]
    for message_id, text in (("m1", "use 8-bit weights"), ("m2", "name the chosen design X")):
        sent = _seq(events, lambda e, m=message_id: e.get("message_id") == m and e["type"] == "message")
        got = _seq(events, lambda e, m=message_id: e.get("message_id") == m and e["type"] == "status")
        answer = _seq(events, lambda e, t=text: e.get("role") == "agent" and t in e.get("text", ""))
        assert sent < got < answer
    assert events[-1]["status"] == "succeeded"
    report = (config.resolved_runs_dir() / run_id / "workspace" / "report.md").read_text()
    assert "use 8-bit weights" in report and "name the chosen design X" in report, "the change was made"


async def test_a_message_after_the_end_continues_the_same_run(
    fast: TestClient, config: BackendConfig
) -> None:
    run_id = await _start(fast)
    first = await _read(await _stream(fast, run_id))
    assert first[-1]["type"] == "run.finished" and first[-1]["status"] == "succeeded"
    folder = config.resolved_runs_dir() / run_id
    session = json.loads((folder / "run.json").read_text())["result"]["session_id"]

    answer = await _say(fast, run_id, "why only three candidates?")
    assert answer["delivery"] == "follow_up"
    detail = await (await fast.get(f"/api/runs/{run_id}", headers=AUTH)).json()
    assert detail["status"] == "running"
    rest = await _read(await _stream(fast, run_id, first[-1]["seq"] + 1))

    assert rest[0]["type"] == "message" and rest[0]["role"] == "user"
    assert rest[0]["message_id"] == "m1" and rest[0]["seq"] == first[-1]["seq"] + 1
    got = _seq(rest, lambda e: e["type"] == "status" and e.get("message_id") == "m1")
    reply = _seq(rest, lambda e: e.get("role") == "agent" and "Follow-up answer" in e.get("text", ""))
    assert got < reply
    assert "why only three candidates?" in next(e for e in rest if e["seq"] == reply)["text"]
    assert rest[-1]["type"] == "run.finished" and rest[-1]["status"] == "succeeded"
    assert rest[-1]["follow_up"] == 1
    record = json.loads((folder / API_RECORD_FILE).read_text())
    assert record["status"] == "succeeded" and record["follow_ups"] == 1
    result = json.loads((folder / "run.json").read_text())["result"]
    assert result["session_id"] == session, "the same session"
    assert [f["status"] for f in result["follow_ups"]] == ["succeeded"]
    again = await _read(await _stream(fast, run_id))
    assert [e["seq"] for e in again] == list(range(1, len(again) + 1)), "one stream, numbered on"


async def test_bad_messages(fast: TestClient) -> None:
    run_id = await _start(fast)
    await _read(await _stream(fast, run_id))
    unknown = await fast.post("/api/runs/no-such-run/messages", json={"text": "hi"}, headers=AUTH)
    assert unknown.status == 404 and "no run" in (await unknown.json())["error"]
    big = await fast.post(
        f"/api/runs/{run_id}/messages", json={"text": "x" * (MAX_MESSAGE_CHARS + 1)}, headers=AUTH
    )
    assert big.status == 413 and str(MAX_MESSAGE_CHARS) in (await big.json())["error"]
    blank = await fast.post(f"/api/runs/{run_id}/messages", json={"text": "  "}, headers=AUTH)
    assert blank.status == 400
    no_token = await fast.post(f"/api/runs/{run_id}/messages", json={"text": "hi"})
    assert no_token.status == 401
    events = await _read(await _stream(fast, run_id))
    assert not any(e["type"] == "message" and e.get("role") == "user" for e in events), "nothing recorded"


async def test_a_failed_run_takes_no_message(config: BackendConfig, tmp_path: Path) -> None:
    manager = RunManager(_config(config), ApiConfig(), agent="stub")
    run = RunDir(tmp_path / "run")
    run.path.mkdir()
    item = ApiRun(
        run, {"status": "failed"}, EventLog(run.path / "events.jsonl", "run", asyncio.get_running_loop())
    )
    manager.runs["run"] = item
    with pytest.raises(RequestError, match="failed") as caught:
        await manager.message("run", "try again")
    assert caught.value.status == 409


async def test_stop_then_follow_up(paced: TestClient) -> None:
    run_id = await _start(paced)
    resp = await _stream(paced, run_id)
    await _read(resp, until="stage")
    stop = await paced.post(f"/api/runs/{run_id}/stop", headers=AUTH)
    assert stop.status == 202
    events = await _read(resp)
    assert events[-1]["status"] == "stopped"
    answer = await _say(paced, run_id, "what did you get done?")
    assert answer["delivery"] == "follow_up"
    rest = await _read(await _stream(paced, run_id, events[-1]["seq"] + 1))
    assert rest[-1]["type"] == "run.finished" and rest[-1]["status"] == "succeeded"


async def test_a_run_without_messages_is_unchanged(fast: TestClient, config: BackendConfig) -> None:
    run_id = await _start(fast)
    events = await _read(await _stream(fast, run_id))
    assert not any("message_id" in e or e.get("text") == DELIVERED_TEXT for e in events)
    assert events[-1]["type"] == "run.finished" and "follow_up" not in events[-1]
    record = json.loads((config.resolved_runs_dir() / run_id / API_RECORD_FILE).read_text())
    assert "follow_ups" not in record
    result = json.loads((config.resolved_runs_dir() / run_id / "run.json").read_text())["result"]
    assert "follow_ups" not in result


async def test_follow_up_costs_add_up(tmp_path: Path) -> None:
    log = EventLog(tmp_path / "events.jsonl", "run", asyncio.get_running_loop())
    translator = Translator(log, JsonlEventSink(tmp_path / "raw.jsonl"))
    steering = Steering(cost_base={"usd": 0.5, "tokens_in": 100, "tokens_out": 10})
    sink = steering.sink(translator, log)
    sink.emit(AgentEvent("cost", "a", {"usd": 0.25, "input_tokens": 50, "output_tokens": 5}))
    assert translator.cost == {"usd": 0.75, "tokens_in": 150, "tokens_out": 15}
    steering.in_agent.append(("m3", "x"))
    sink.emit(AgentEvent("status", "a", {"message": DELIVERED_TEXT, "user_message_delivered": True}))
    assert log.since(1)[-1] == {**log.since(1)[-1], "type": "status", "message_id": "m3"}


# ---- the claude_cli harness, against the fake CLI ----


@pytest.fixture
def fake_cli(tmp_path: Path) -> Path:
    wrapper = tmp_path / "bin" / "claude"
    wrapper.parent.mkdir()
    wrapper.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{FAKE_CLI}" "$@"\n')
    wrapper.chmod(0o755)
    return wrapper


class _Sink:
    def __init__(self) -> None:
        self.events: list[AgentEvent] = []
        self.seen = asyncio.Event()

    def emit(self, event: AgentEvent) -> None:
        self.events.append(event)


async def test_claude_takes_messages_mid_turn_without_a_restart(
    config: BackendConfig, tmp_path: Path, fake_cli: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_CLAUDE_TOOL_S", "3")
    cli = config.agents.claude_cli.model_copy(
        update={"cli_path": str(fake_cli), "config_dir": tmp_path / "claude-config"}
    )
    agents = config.agents.model_copy(update={"claude_cli": cli})
    backend = backend_for("claude_cli", agents)
    spec = AgentSpec(
        name="fake", prompts=["SLOW work"], workdir=tmp_path / "work", timeout_s=60, system_prompt="rules"
    )
    sink = _Sink()
    run = asyncio.create_task(backend.run(spec, sink))
    async with asyncio.timeout(20):
        while not any(e.kind == "tool_call" for e in sink.events):
            await asyncio.sleep(0.05)
    await backend.inject("A message from the user (message 1): one")
    await backend.inject("A message from the user (message 2): two")
    result = await run

    assert not result.failed, result.error
    kinds = [(e.kind, e.data.get("message") or e.data.get("text") or "") for e in sink.events]
    delivered = [i for i, (k, t) in enumerate(kinds) if k == "status" and t == DELIVERED_TEXT]
    heard = next(i for i, (k, t) in enumerate(kinds) if k == "text" and "heard:" in t)
    assert len(delivered) == 2 and delivered[-1] < heard
    text = next(t for k, t in kinds if k == "text" and "heard:" in t)
    assert text.index("(message 1)") < text.index("(message 2)"), "in the order sent"
    assert not any("restart" in t or "resuming" in t for _, t in kinds), "the turn was not cut"
    transcript = next((tmp_path / "claude-config" / "projects").rglob(f"{result.session_id}.jsonl"))
    prompts = [r for r in map(json.loads, transcript.read_text().splitlines()) if r.get("type") == "user"]
    assert sum(1 for r in prompts if isinstance(r["message"]["content"], str)) == 1, "one typed turn"

    follow = AgentSpec(
        name="fake",
        prompts=["and the next step?"],
        workdir=tmp_path / "work",
        timeout_s=60,
        system_prompt="rules",
        resume_session=result.session_id,
    )
    again = await backend_for("claude_cli", agents).run(follow, _Sink())
    assert not again.failed, again.error
    assert again.session_id == result.session_id
    assert again.cost_usd == pytest.approx(0.0), "only this turn's share of the session's totals"
    records = [json.loads(line) for line in transcript.read_text().splitlines()]
    typed = [r["message"]["content"] for r in records if r.get("type") == "user"]
    typed = [t for t in typed if isinstance(t, str)]
    assert len(typed) == 2 and "and the next step?" in typed[1]
    assert "<system-prompt>" in typed[0] and "<system-prompt>" not in typed[1], "rules typed once"


# ---- the openrouter harness, on a scripted model ----


async def test_openrouter_reads_a_message_at_its_next_step(
    config: BackendConfig, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("openhands.sdk")
    from openhands.sdk.llm import Message as SdkMessage
    from openhands.sdk.llm import MessageToolCall
    from openhands.sdk.llm import TextContent as SdkText
    from openhands.sdk.testing import TestLLM
    from pydantic import SecretStr

    from chipin_backend.agents.openrouter_agent import _PARKED, OpenRouterAgentBackend

    seen: list[str] = []

    class Recording(TestLLM):
        def completion(self, messages: Any, *args: Any, **kwargs: Any) -> Any:
            seen.append(json.dumps([str(m) for m in messages]))
            return super().completion(messages, *args, **kwargs)

    def scripted(
        self: Any, model: str, key: str, provider: Any, *, usage_id: str, fallback: Any = None
    ) -> Any:
        sleep = MessageToolCall(
            id="c1", name="terminal", arguments=json.dumps({"command": "sleep 2"}), origin="completion"
        )
        finish = MessageToolCall(
            id="c2", name="finish", arguments=json.dumps({"message": "done"}), origin="completion"
        )
        replies = [
            SdkMessage(role="assistant", content=[SdkText(text="")], tool_calls=[sleep]),
            SdkMessage(role="assistant", content=[SdkText(text="")], tool_calls=[finish]),
            SdkMessage(role="assistant", content=[SdkText(text="")], tool_calls=[finish]),
            SdkMessage(role="assistant", content=[SdkText(text="")], tool_calls=[finish]),
        ]
        return Recording.from_messages(replies, usage_id=usage_id, api_key=SecretStr(key))

    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-key")
    monkeypatch.setattr(OpenRouterAgentBackend, "_build_llm", scripted)
    backend = backend_for("openrouter", config.agents)
    spec = AgentSpec(name="a", prompts=["work"], workdir=tmp_path / "w", timeout_s=60)
    sink = _Sink()
    run = asyncio.create_task(backend.run(spec, sink))
    async with asyncio.timeout(30):
        while not any(e.kind == "tool_call" for e in sink.events):
            await asyncio.sleep(0.05)
    await backend.inject("STEER-ONE")
    await backend.inject("STEER-TWO")
    result = await run

    assert not result.failed, result.error
    delivered = [e for e in sink.events if e.kind == "status" and e.data.get("user_message_delivered")]
    assert len(delivered) == 2
    both = [s for s in seen[1:] if "STEER-TWO" in s]
    assert both, "the model read the second message"
    assert both[0].index("STEER-ONE") < both[0].index("STEER-TWO"), "in the order sent"
    assert result.session_id in _PARKED, "kept for a follow-up"
    follow = AgentSpec(
        name="a",
        prompts=["FOLLOW-UP?"],
        workdir=tmp_path / "w",
        timeout_s=60,
        resume_session=result.session_id,
    )
    again = await backend_for("openrouter", config.agents).run(follow, _Sink())
    assert not again.failed, again.error
    assert again.session_id == result.session_id, "the same conversation"
    assert "FOLLOW-UP?" in seen[-1] and "STEER-ONE" in seen[-1], "with the earlier turns in it"
    for conversation, _ in _PARKED.values():
        conversation.close()
    _PARKED.clear()
