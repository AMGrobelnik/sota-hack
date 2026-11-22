"""The command line end to end with the stub backend, and ``ask`` with a fake OpenRouter."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from chipin_backend import cli
from chipin_backend.llm.client import ChatResult
from chipin_backend.orchestrate import LLM_CALLS_ENV
from chipin_backend.runs import RunDir


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    path = tmp_path / "cfg.yaml"
    data = {
        "runs_dir": str(tmp_path / "runs"),
        "log_dir": str(tmp_path / "logs"),
        "agents": {"default_backend": "stub", "openrouter_tool": True},
    }
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def test_run_writes_a_full_record(
    config_file: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("Propose three seizure detectors.\n", encoding="utf-8")
    code = cli.main(["run", "--config", str(config_file), "--prompt-file", str(prompt)])

    assert code == 0
    run_dir = Path(json.loads(capsys.readouterr().out)["run_dir"])
    record = json.loads((run_dir / "run.json").read_text())
    assert record["status"] == "succeeded"
    assert record["agent"]["prompts"] == ["Propose three seizure detectors."]
    assert "chipin_backend ask" in record["agent"]["system_prompt"]
    assert record["agent"]["env"][LLM_CALLS_ENV] == str(run_dir / "llm_calls.jsonl")
    assert record["config"]["agents"]["openrouter_tool"] is True
    assert record["finished_at"] and record["duration_s"] >= 0
    assert record["result"]["agent"] == "agent"
    assert (run_dir / "events.jsonl").is_file()


def test_run_without_a_prompt_is_a_usage_error(config_file: Path) -> None:
    assert cli.main(["run", "--config", str(config_file)]) == 2


def test_ask_prints_and_records_the_call(
    config_file: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_chat(self: Any, messages: list[dict[str, str]], **kwargs: Any) -> ChatResult:
        return ChatResult(model="openai/gpt-5-nano", text="use line length", cost_usd=0.00002)

    monkeypatch.setattr(cli.OpenRouterClient, "chat", fake_chat)
    run = RunDir.create(tmp_path / "runs")
    monkeypatch.setenv(LLM_CALLS_ENV, str(run.llm_calls_path))

    assert cli.main(["ask", "--config", str(config_file), "--model", "cheap", "one feature?"]) == 0
    assert capsys.readouterr().out.strip() == "use line length"
    calls = run.read_llm_calls()
    assert len(calls) == 1 and calls[0]["cost_usd"] == pytest.approx(0.00002)
