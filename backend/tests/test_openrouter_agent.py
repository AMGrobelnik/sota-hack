"""The ``openrouter`` agent backend: model ids, MCP filtering and event translation.

Event translation is checked on stand-ins named like the OpenHands SDK events,
so these tests run without the ``openhands`` extra; the live test needs it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from chipmonk_backend.agents import AgentSpec, backend_for
from chipmonk_backend.agents.openrouter_agent import mcp_servers_for, normalize_model, translate_event
from chipmonk_backend.config import BackendConfig


@dataclass
class TextContent:
    text: str


@dataclass
class Message:
    content: list[TextContent]
    reasoning_content: str | None = None


@dataclass
class MessageEvent:
    llm_message: Message
    source: str = "agent"


@dataclass
class TerminalAction:
    command: str
    kind: str = "TerminalAction"

    def model_dump(self, exclude: set[str] | None = None) -> dict[str, Any]:
        return {k: v for k, v in vars(self).items() if k not in (exclude or set())}


@dataclass
class ActionEvent:
    tool_name: str
    tool_call_id: str
    action: TerminalAction
    thought: list[TextContent] = field(default_factory=list)
    reasoning_content: str | None = None


@dataclass
class Observation:
    text: str
    is_error: bool = False


@dataclass
class ObservationEvent:
    tool_call_id: str
    observation: Observation


@dataclass
class AgentErrorEvent:
    tool_call_id: str
    error: str


@dataclass
class ConversationErrorEvent:
    code: str
    detail: str


def test_normalize_model() -> None:
    assert normalize_model("deepseek/deepseek-v4-flash") == "openrouter/deepseek/deepseek-v4-flash"
    assert normalize_model("openrouter/openai/gpt-5-nano") == "openrouter/openai/gpt-5-nano"
    with pytest.raises(ValueError, match="not an OpenRouter model id"):
        normalize_model("gpt-5-nano")


def test_mcp_servers_drop_browser_logins() -> None:
    raw = {
        "mcpServers": {
            "local": {"command": "srv"},
            "web": {"url": "https://x", "auth": "oauth"},
            "web2": {"url": "https://y", "auth": {"strategy": "OAuth"}},
            "keyed": {"url": "https://z", "headers": {"X": "1"}},
        }
    }
    assert sorted(mcp_servers_for(raw)) == ["keyed", "local"]
    assert mcp_servers_for({"local": {"command": "srv"}}) == {"local": {"command": "srv"}}


def test_translate_event_kinds() -> None:
    message = MessageEvent(Message([TextContent("hello")], reasoning_content="thinking..."))
    assert [(e.kind, e.data) for e in translate_event(message, "a")] == [
        ("thinking", {"text": "thinking..."}),
        ("text", {"text": "hello"}),
    ]
    assert translate_event(MessageEvent(Message([TextContent("task")]), source="user"), "a") == []
    action = ActionEvent("terminal", "c1", TerminalAction("ls"), thought=[TextContent("look")])
    assert [(e.kind, e.data) for e in translate_event(action, "a")] == [
        ("text", {"text": "look"}),
        ("tool_call", {"tool": "terminal", "input": {"command": "ls"}, "call_id": "c1"}),
    ]
    [obs] = translate_event(ObservationEvent("c1", Observation("a.txt")), "a")
    assert obs.data == {"call_id": "c1", "output": "a.txt", "is_error": False}
    [err] = translate_event(AgentErrorEvent("c2", "bad args"), "a")
    assert err.data == {"call_id": "c2", "output": "bad args", "is_error": True}
    [conv] = translate_event(ConversationErrorEvent("LLMRateLimitError", "429"), "a")
    assert conv.kind == "error" and conv.data["message"] == "LLMRateLimitError: 429"


async def test_run_without_a_key_is_a_setup_error(config: BackendConfig, tmp_path: Path) -> None:
    pytest.importorskip("openhands.sdk")
    from chipmonk_backend.llm.keys import MissingKeyError

    spec = AgentSpec(name="a", prompts=["hi"], workdir=tmp_path)
    with pytest.raises(MissingKeyError, match="OPENROUTER_API_KEY"):
        await backend_for("openrouter", config.agents).run(spec, _NullSink())


class _NullSink:
    def emit(self, event: Any) -> None:
        return None


@pytest.mark.live
async def test_live_openrouter_agent_run(config: BackendConfig, tmp_path: Path) -> None:
    """A real OpenHands run on the configured cheap model (needs the extra and the key)."""
    pytest.importorskip("openhands.sdk")
    from chipmonk_backend.llm.keys import has_openrouter_key

    if not has_openrouter_key():
        pytest.skip("OPENROUTER_API_KEY is not set")
    spec = AgentSpec(
        name="live",
        prompts=["Create hello.txt containing exactly the line: hello chipmonk. Then finish."],
        output_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]},
        expected_files=["hello.txt"],
        workdir=tmp_path / "work",
        timeout_s=600,
    )
    result = await backend_for("openrouter", config.agents).run(spec, _NullSink())
    assert not result.failed, result.error
    assert (tmp_path / "work" / "hello.txt").read_text().strip() == "hello chipmonk"
    assert result.cost_usd > 0
