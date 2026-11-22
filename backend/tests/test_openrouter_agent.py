"""The ``openrouter`` agent backend: model ids, MCP filtering and event translation.

Event translation is checked on stand-ins named like the OpenHands SDK events,
so these tests run without the ``openhands`` extra; the live test needs it.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from chipin_backend.agents import AgentSpec, backend_for
from chipin_backend.agents.openrouter_agent import mcp_servers_for, normalize_model, translate_event
from chipin_backend.config import BackendConfig


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
    from chipin_backend.llm.keys import MissingKeyError

    spec = AgentSpec(name="a", prompts=["hi"], workdir=tmp_path)
    with pytest.raises(MissingKeyError, match="OPENROUTER_API_KEY"):
        await backend_for("openrouter", config.agents).run(spec, _NullSink())


class _NullSink:
    def emit(self, event: Any) -> None:
        return None


FAKE_KEY = "fake-openrouter-key-for-the-leak-test"


async def test_faked_run_never_writes_the_key(
    config: BackendConfig, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A whole run on a scripted model: it finishes, and the key appears in no workspace file."""
    pytest.importorskip("openhands.sdk")
    from openhands.sdk.llm import Message as SdkMessage
    from openhands.sdk.llm import MessageToolCall
    from openhands.sdk.llm import TextContent as SdkText
    from openhands.sdk.testing import TestLLM
    from pydantic import SecretStr

    from chipin_backend.agents.openrouter_agent import OpenRouterAgentBackend

    def scripted_llm(
        self: Any, model: str, key: str, provider: Any, *, usage_id: str, fallback: Any = None
    ) -> Any:
        finish = MessageToolCall(
            id="call_1", name="finish", arguments=json.dumps({"message": "all done"}), origin="completion"
        )
        reply = SdkMessage(role="assistant", content=[SdkText(text="")], tool_calls=[finish])
        return TestLLM.from_messages([reply], usage_id=usage_id, api_key=SecretStr(key))

    monkeypatch.setenv("OPENROUTER_API_KEY", FAKE_KEY)
    monkeypatch.setattr(OpenRouterAgentBackend, "_build_llm", scripted_llm)
    workdir = tmp_path / "work"
    spec = AgentSpec(name="a", prompts=["say done"], workdir=workdir, timeout_s=60)
    result = await backend_for("openrouter", config.agents).run(spec, _NullSink())

    assert not result.failed, result.error
    assert result.final_text == "all done"
    leaked = [p for p in workdir.rglob("*") if p.is_file() and FAKE_KEY.encode() in p.read_bytes()]
    assert leaked == []
    assert not (workdir / ".chipin" / "openhands").exists()


async def test_a_cancelled_run_still_reports_its_cost(
    config: BackendConfig, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A run cancelled from outside (a timeout, a stop) emits its cost before it goes."""
    pytest.importorskip("openhands.sdk")
    from openhands.sdk.testing import TestLLM
    from pydantic import SecretStr

    from chipin_backend.agents.openrouter_agent import OpenRouterAgentBackend

    def idle_llm(
        self: Any, model: str, key: str, provider: Any, *, usage_id: str, fallback: Any = None
    ) -> Any:
        return TestLLM.from_messages([], usage_id=usage_id, api_key=SecretStr(key))

    async def hang(self: Any, *args: Any) -> None:
        await asyncio.sleep(60)

    events: list[Any] = []

    class Sink:
        def emit(self, event: Any) -> None:
            events.append(event)

    monkeypatch.setenv("OPENROUTER_API_KEY", FAKE_KEY)
    monkeypatch.setattr(OpenRouterAgentBackend, "_build_llm", idle_llm)
    monkeypatch.setattr(OpenRouterAgentBackend, "_turn", hang)
    spec = AgentSpec(name="a", prompts=["wait"], workdir=tmp_path / "work", timeout_s=60)
    task = asyncio.create_task(backend_for("openrouter", config.agents).run(spec, Sink()))
    async with asyncio.timeout(30):
        while not any(e.kind == "agent_start" for e in events):
            await asyncio.sleep(0.05)
    await asyncio.sleep(0.1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert events[-1].kind == "cost" and events[-1].data["usd"] == 0.0


def test_a_long_single_line_command_runs_whole(tmp_path: Path) -> None:
    """A one-line command far past the tty's ~1 KiB input queue reaches bash whole and runs.

    The stock subprocess terminal writes it in one go, the tty drops the tail
    (closing quote and Enter) and the command hangs until the tool times out:
    a long ``./subagent start`` brief stalled a run that way.
    """
    pytest.importorskip("openhands.sdk")
    from openhands.tools.terminal.definition import TerminalAction

    from chipin_backend.agents.paced_terminal import PacedTerminalExecutor

    executor = PacedTerminalExecutor(str(tmp_path))
    try:
        arg = "x" * 6000
        obs = executor(TerminalAction(command=f'printf "%s" "{arg}" | wc -c', timeout=20))
    finally:
        executor.close()
    assert obs.exit_code == 0, obs.text[-300:]
    assert "6000" in obs.text


def test_the_agent_gets_the_paced_terminal(config: BackendConfig, tmp_path: Path) -> None:
    """The backend's agent asks the registry for the paced terminal, not the stock one."""
    pytest.importorskip("openhands.sdk")
    from chipin_backend.agents.openrouter_agent import OpenRouterAgentBackend
    from chipin_backend.agents.paced_terminal import PACED_TERMINAL
    from chipin_backend.llm.providers import resolve_provider

    backend = OpenRouterAgentBackend(config.agents)
    provider = resolve_provider(backend.providers, None)
    spec = AgentSpec(name="a", prompts=["x"], workdir=tmp_path)
    agent = backend._build_agent(spec, "openrouter/openai/gpt-5-nano", FAKE_KEY, provider)
    assert [t.name for t in agent.tools] == [PACED_TERMINAL, "file_editor", "task_tracker"]


async def test_cost_is_reported_while_the_agent_works(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each model step with new spend emits the run's spend so far, less a continued run's earlier part."""
    from chipin_backend.agents import openrouter_agent

    monkeypatch.setattr(openrouter_agent, "LIVE_COST_INTERVAL_S", 0.0)

    @dataclass
    class Usage:
        prompt_tokens: int
        completion_tokens: int

    @dataclass
    class Metrics:
        accumulated_cost: float
        accumulated_token_usage: Usage

    class Stats:
        def __init__(self) -> None:
            self.metrics = Metrics(1.0, Usage(100, 10))

        def get_combined_metrics(self) -> Metrics:
            return self.metrics

    class Conversation:
        conversation_stats = Stats()

    emitted: list[tuple[str, dict[str, Any]]] = []
    live = openrouter_agent._LiveCost()
    live.conversation, live.before = Conversation(), (1.0, 100, 10)
    step = ActionEvent(tool_call_id="c", tool_name="terminal", action=TerminalAction("ls"))

    def emit(kind: str, data: dict[str, Any]) -> None:
        emitted.append((kind, data))

    stats = Conversation.conversation_stats
    live.after_step(step, emit)  # nothing spent yet in this run
    stats.metrics = Metrics(1.25, Usage(300, 30))
    live.after_step(ObservationEvent(tool_call_id="c", observation=Observation("ok")), emit)  # not a step
    live.after_step(step, emit)
    stats.metrics = Metrics(1.5, Usage(500, 50))
    live.after_step(MessageEvent(source="agent", llm_message=Message(content=[])), emit)
    assert emitted == [
        ("cost", {"usd": 0.25, "input_tokens": 200, "output_tokens": 20}),
        ("cost", {"usd": 0.5, "input_tokens": 400, "output_tokens": 40}),
    ]


async def test_a_cancelled_wait_pauses_the_conversation() -> None:
    """Cancelling the wait (a stop) pauses the SDK run, whose thread would otherwise go on."""
    import threading

    from chipin_backend.agents.openrouter_agent import _Activity, _run_until_idle

    class Conversation:
        def __init__(self) -> None:
            self.paused = threading.Event()

        def run(self) -> None:
            self.paused.wait(30)

        def pause(self) -> None:
            self.paused.set()

    conversation = Conversation()
    task = asyncio.create_task(_run_until_idle(conversation, _Activity(), None))
    await asyncio.sleep(0.2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert await asyncio.to_thread(conversation.paused.wait, 5)


@pytest.mark.live
async def test_live_openrouter_agent_run(config: BackendConfig, tmp_path: Path) -> None:
    """A real OpenHands run on the configured cheap model (needs the extra and the key)."""
    pytest.importorskip("openhands.sdk")
    from chipin_backend.llm.keys import has_openrouter_key

    if not has_openrouter_key():
        pytest.skip("OPENROUTER_API_KEY is not set")
    spec = AgentSpec(
        name="live",
        prompts=["Create hello.txt containing exactly the line: hello chipin. Then finish."],
        output_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]},
        expected_files=["hello.txt"],
        workdir=tmp_path / "work",
        timeout_s=600,
    )
    result = await backend_for("openrouter", config.agents).run(spec, _NullSink())
    assert not result.failed, result.error
    assert (tmp_path / "work" / "hello.txt").read_text().strip() == "hello chipin"
    assert result.cost_usd > 0
