"""Summaries on OpenRouter: the tier walk against a faked OpenRouter, the run digest,
the record the ``run`` command writes, and one live call (``-m live``)."""

from __future__ import annotations

import functools
import json
from pathlib import Path
from typing import Any

import httpx
import pytest
import yaml

from chipin_backend import cli
from chipin_backend.agents.types import AgentEvent, AgentResult
from chipin_backend.llm import summarise as summarise_mod
from chipin_backend.llm.client import ChatResult
from chipin_backend.llm.summarise import (
    build_run_digest,
    label_output,
    load_summary_settings,
    summarise,
    summarise_run,
)

FAKE_KEY = "fake-openrouter-key-for-summary-tests"
BULLETS = "- Task: design an EEG seizure detector.\n- Trained 2 models, F1 0.91.\n- Run done, report written."


def _reply(text: str, *, cost: float = 1e-5, finish: str = "stop", provider: str = "X") -> httpx.Response:
    body = {
        "model": "openai/gpt-oss-120b",
        "provider": provider,
        "choices": [{"message": {"role": "assistant", "content": text}, "finish_reason": finish}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 20, "cost": cost},
    }
    return httpx.Response(200, json=body)


class FakeOpenRouter:
    """Answers chat calls in turn from ``replies``, recording every request body."""

    def __init__(self, replies: list[httpx.Response]) -> None:
        self.replies = list(replies)
        self.requests: list[dict[str, Any]] = []
        self.auth: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(json.loads(request.content))
        self.auth.append(request.headers.get("Authorization", ""))
        return self.replies.pop(0)

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self))

    def providers(self) -> list[str]:
        return [r["provider"]["only"][0] for r in self.requests]


@pytest.fixture
def key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", FAKE_KEY)


def test_settings_are_paid_openrouter_only() -> None:
    settings = load_summary_settings()
    assert settings.model == "openai/gpt-oss-120b"
    assert settings.providers and settings.background_providers
    raw = yaml.safe_load(summarise_mod.SETTINGS_PATH.read_text())
    assert not any("free" in str(k).lower() for k in raw)


async def test_walk_falls_over_and_bills_every_attempt(key: None) -> None:
    fake = FakeOpenRouter(
        [
            httpx.Response(503, json={"error": {"message": "busy"}}),
            _reply("", cost=2e-5),  # empty: retried on the same tier
            _reply("", cost=2e-5),
            _reply("cut off mid", finish="length", cost=3e-5),
            _reply("Short answer here.", cost=4e-5, provider="Sambanova"),
        ]
    )
    async with fake.client() as client:
        result = await summarise(prompt="p", system="s", client=client)
    settings = load_summary_settings()
    assert fake.providers() == [settings.providers[0], *[settings.providers[1]] * 2, *settings.providers[2:4]]
    assert result.text == "Short answer here." and result.provider == "Sambanova"
    assert result.cost_usd == pytest.approx(11e-5) and result.input_tokens == 400
    first = fake.requests[0]
    assert first["model"] == "openai/gpt-oss-120b"
    assert first["provider"]["allow_fallbacks"] is False
    assert first["reasoning"] == {"effort": "low"} and first["max_tokens"] >= 4096
    assert fake.auth[0] == f"Bearer {FAKE_KEY}"


async def test_used_up_key_stops_the_walk(key: None) -> None:
    fake = FakeOpenRouter([httpx.Response(402, json={"error": {"message": "Insufficient credits"}})])
    async with fake.client() as client:
        result = await summarise(prompt="p", system="s", client=client)
    assert result.text == "" and "HTTP 402" in result.error and len(fake.requests) == 1


async def test_no_key_sends_nothing() -> None:
    fake = FakeOpenRouter([])
    async with fake.client() as client:
        result = await summarise(prompt="p", system="s", client=client)
    assert result.error == "OPENROUTER_API_KEY is not set" and fake.requests == []


def _events() -> list[AgentEvent]:
    return [
        AgentEvent("agent_start", "a", {"model": "m"}),
        AgentEvent("text", "a", {"text": "I will train a detector."}),
        AgentEvent("tool_call", "a", {"tool": "Bash", "input": {"command": "python train.py"}}),
        AgentEvent("tool_result", "a", {"output": "F1 0.91 " + "x" * 1000, "is_error": False}),
        AgentEvent("error", "a", {"message": "rate limited once"}),
    ]


def test_digest_pins_the_end_and_clips_long_output() -> None:
    result = AgentResult(agent="a", final_text="done", files=["report.md"])
    digest = build_run_digest(_events(), result, line_chars=100)
    lines = digest.splitlines()
    assert lines[0] == "PINNED RUN ENDED (done); files: report.md; final answer: done"
    assert lines[1] == "PINNED error: rate limited once"
    assert "tool call Bash" in digest and max(len(line) for line in lines) < 140


async def test_run_summary_walks_the_background_tiers_and_keeps_three_bullets(key: None) -> None:
    long_bullets = "Here you go:\n" + BULLETS + "\n- " + "y" * 400
    fake = FakeOpenRouter([_reply(long_bullets)])
    async with fake.client() as client:
        summary = await summarise_run(_events(), AgentResult(agent="a"), client=client)
    settings = load_summary_settings()
    assert fake.providers() == [settings.background_providers[0]]
    bullets = summary.text.splitlines()
    assert len(bullets) == 3 and all(b.startswith("- ") for b in bullets)
    assert all(len(b) <= settings.bullet_max_chars for b in bullets)
    assert "RUN ENDED (done)" in fake.requests[0]["messages"][1]["content"]


async def test_label_needs_three_words(key: None) -> None:
    fake = FakeOpenRouter([_reply("README"), _reply("README"), _reply("3 designs, best F1 0.91")])
    async with fake.client() as client:
        label = await label_output("long answer " * 400, client=client)
    assert label.text == "3 designs, best F1 0.91"
    assert fake.requests[0]["reasoning"] == {"effort": "medium"}
    assert fake.requests[0]["messages"][1]["content"].endswith("... [truncated]")


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    path = tmp_path / "cfg.yaml"
    data = {"runs_dir": str(tmp_path / "runs"), "log_dir": str(tmp_path / "logs")}
    data["agents"] = {"default_backend": "stub"}
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def test_run_command_writes_the_summary_into_the_record(
    config_file: Path, key: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = FakeOpenRouter([_reply(BULLETS, cost=5e-5)])
    monkeypatch.setattr(
        summarise_mod.httpx,
        "AsyncClient",
        functools.partial(httpx.AsyncClient, transport=httpx.MockTransport(fake)),
    )
    assert cli.main(["run", "--config", str(config_file), "--prompt", "hello"]) == 0
    run_dir = Path(json.loads(capsys.readouterr().out)["run_dir"])
    record = json.loads((run_dir / "run.json").read_text())
    summary = record["result"]["summary"]["run"]
    assert summary["text"] == BULLETS and summary["cost_usd"] == pytest.approx(5e-5)
    assert "output_label" not in record["result"]["summary"]  # the stub's answer is short
    assert record["llm_cost_usd"] == pytest.approx(5e-5)
    assert FAKE_KEY not in (run_dir / "run.json").read_text()


def test_run_without_a_key_skips_the_summary(config_file: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["run", "--config", str(config_file), "--prompt", "hello"]) == 0
    run_dir = Path(json.loads(capsys.readouterr().out)["run_dir"])
    record = json.loads((run_dir / "run.json").read_text())
    assert record["result"]["summary"] is None and record["llm_cost_usd"] is None


def test_no_summary_flag_makes_no_call(
    config_file: Path, key: None, capsys: pytest.CaptureFixture[str]
) -> None:
    """With a key but ``--no-summary``, no summary is made."""
    assert cli.main(["run", "--config", str(config_file), "--prompt", "hi", "--no-summary"]) == 0
    run_dir = Path(json.loads(capsys.readouterr().out)["run_dir"])
    assert json.loads((run_dir / "run.json").read_text())["result"]["summary"] is None


def test_ask_fails_on_an_empty_answer_cut_at_the_limit(
    config_file: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    async def fake_chat(self: Any, messages: list[dict[str, str]], **kwargs: Any) -> ChatResult:
        return ChatResult(model="openai/gpt-oss-120b", text="", finish_reason="length")

    monkeypatch.setattr(cli.OpenRouterClient, "chat", fake_chat)
    assert cli.main(["ask", "--config", str(config_file), "--max-tokens", "16", "q?"]) == 1


@pytest.mark.live
async def test_live_run_summary() -> None:
    """One real, cheap summary call (needs ``OPENROUTER_API_KEY``)."""
    from chipin_backend.llm.keys import has_openrouter_key

    if not has_openrouter_key():
        pytest.skip("OPENROUTER_API_KEY is not set")
    result = AgentResult(agent="a", final_text="Wrote report.md: detector F1 0.91", files=["report.md"])
    summary = await summarise_run(_events(), result)
    assert summary.text.startswith("- "), summary.error
    assert summary.cost_usd > 0 and summary.model
