"""The ``claude_cli`` backend: argv, transcript parsing, the PTY helpers, and a whole
run against a fake ``claude`` (``fake_claude_cli.py``) under a real PTY."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

from chipin_backend.agents import AgentEvent, AgentSpec, backend_for
from chipin_backend.agents._claude.background import BackgroundWork
from chipin_backend.agents._claude.config_dir import pretrust, project_slug, revoke_trust
from chipin_backend.agents._claude.cost import TranscriptUsage, cost_from_state, parse_cost_output
from chipin_backend.agents._claude.delivery import (
    PromptNotDeliveredError,
    bracketed_paste,
    check_delivery,
    typeable,
)
from chipin_backend.agents._claude.screen import DOWN, ENTER, ESCAPE, DialogPilot, submit_held
from chipin_backend.agents.claude_cli import build_argv, transcript_path, translate_record
from chipin_backend.agents.mailbox import InjectMailbox
from chipin_backend.agents.output import STRUCT_OUT_FILENAME, review_output
from chipin_backend.config import BackendConfig, ClaudeCliConfig

FAKE_CLI = Path(__file__).with_name("fake_claude_cli.py")


class ListSink:
    """Collects events in order."""

    def __init__(self) -> None:
        self.events: list[AgentEvent] = []

    def emit(self, event: AgentEvent) -> None:
        self.events.append(event)

    def kinds(self) -> list[str]:
        return [e.kind for e in self.events]


def _flag(argv: list[str], name: str) -> str:
    return argv[argv.index(name) + 1]


def test_build_argv_fresh_and_resume() -> None:
    cli = ClaudeCliConfig()
    spec = AgentSpec(
        name="a",
        prompts=["p"],
        model="sonnet",
        allowed_tools=["Read", "Bash"],
        mcp_servers={"x": {"command": "x-server"}},
    )
    argv = build_argv(spec, cli, session_id="sid", resume=False)
    assert _flag(argv, "--session-id") == "sid" and "--resume" not in argv
    assert _flag(argv, "--model") == "sonnet"
    assert _flag(argv, "--effort") == cli.effort
    assert _flag(argv, "--permission-mode") == "bypassPermissions"
    assert "--dangerously-skip-permissions" in argv
    assert _flag(argv, "--setting-sources") == ""
    assert _flag(argv, "--allowed-tools") == "Read,Bash"
    assert json.loads(_flag(argv, "--mcp-config")) == {"mcpServers": {"x": {"command": "x-server"}}}
    settings = json.loads(_flag(argv, "--settings"))
    assert settings["skipDangerousModePermissionPrompt"] is True
    assert settings["switchModelsOnFlag"] is True
    resumed = build_argv(spec, cli, session_id="sid", resume=True)
    assert _flag(resumed, "--resume") == "sid" and "--session-id" not in resumed


def test_transcript_path_uses_the_cli_slug(tmp_path: Path) -> None:
    workdir = tmp_path / "my_work.dir"
    workdir.mkdir()
    path = transcript_path(tmp_path / "cfg", workdir, "abc")
    assert path.name == "abc.jsonl"
    assert path.parent.name == project_slug(workdir.resolve())
    assert set(path.parent.name) <= set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-")
    assert len(project_slug("/x" * 300)) < 220  # long paths are truncated and hashed


ASSISTANT = {
    "type": "assistant",
    "message": {
        "id": "m1",
        "content": [
            {"type": "thinking", "thinking": "plan it"},
            {"type": "text", "text": "Writing the file."},
            {"type": "tool_use", "id": "t1", "name": "Write", "input": {"file_path": "a.txt"}},
        ],
        "usage": {"input_tokens": 5, "cache_read_input_tokens": 100, "output_tokens": 7},
    },
}
TOOL_RESULT = {
    "type": "user",
    "message": {
        "content": [
            {"type": "tool_result", "tool_use_id": "t1", "content": [{"type": "text", "text": "written"}]},
            {"type": "tool_result", "tool_use_id": "t2", "content": "boom", "is_error": True},
        ]
    },
}


def test_translate_record_assistant_and_tool_results() -> None:
    events = translate_record(ASSISTANT, "agent")
    assert [(e.kind, e.data) for e in events] == [
        ("thinking", {"text": "plan it"}),
        ("text", {"text": "Writing the file."}),
        ("tool_call", {"tool": "Write", "input": {"file_path": "a.txt"}, "call_id": "t1"}),
    ]
    results = translate_record(TOOL_RESULT, "agent")
    assert [e.data for e in results] == [
        {"call_id": "t1", "output": "written", "is_error": False},
        {"call_id": "t2", "output": "boom", "is_error": True},
    ]


def test_translate_record_sidechain_skips_and_status() -> None:
    sub = translate_record({**ASSISTANT, "isSidechain": True, "agentId": "a7"}, "agent")
    assert all(e.data["subagent"] == "a7" for e in sub)
    api_error = {**ASSISTANT, "isApiErrorMessage": True, "apiErrorStatus": 529}
    assert translate_record(api_error, "agent") == []
    typed = {"type": "user", "message": {"content": "<prompt>hi</prompt>"}}
    assert translate_record(typed, "agent") == []
    assert translate_record({"type": "system", "subtype": "turn_duration"}, "agent") == []
    [compact] = translate_record({"type": "system", "subtype": "compact_boundary"}, "agent")
    assert compact.kind == "status"


def test_transcript_usage_counts_each_message_once() -> None:
    usage = TranscriptUsage()
    for _ in range(3):  # the CLI repeats a message's usage on each of its blocks
        usage.add(ASSISTANT)
    assert (usage.input_tokens, usage.output_tokens) == (105, 7)


def test_typeable_and_delivery_check() -> None:
    assert typeable("a\u2061b\r\nc\x1b") == "ab\nc"
    typed = "<prompt>\nline one\nline two\n</prompt>"
    assert bracketed_paste(typed).startswith("\x1b[200~")
    assert check_delivery([{"type": "assistant"}], typed) is False
    whole = {"type": "user", "message": {"content": "<prompt> line one\n\nline two </prompt>"}}
    assert check_delivery([whole], typed) is True
    pasted = {
        "type": "user",
        "message": {
            "content": '\n\n<pasted_content id="p1">\n<prompt>\nline one\n\n</pasted_content id="p1">\n'
            '\n\n<pasted_content id="p1">\nline two\n</prompt>\n</pasted_content id="p1">\n'
        },
    }
    assert check_delivery([pasted], typed) is True
    with pytest.raises(PromptNotDeliveredError):
        check_delivery([{"type": "user", "message": {"content": "line two </prompt>"}}], typed)


def test_dialog_pilot_accepts_bypass_by_label() -> None:
    pilot = DialogPilot()
    frame = "WARNING Bypass Permissions mode\n\u276f 1. No, exit\n  2. Yes, I accept\nEnter to confirm"
    assert pilot.reply(frame, now=0.0) == DOWN
    frame2 = frame + "\n  1. No, exit\n\u276f 2. Yes, I accept"
    assert pilot.reply(frame2, now=1.0) == ENTER
    assert pilot.blocker(frame2 + "\n\u23f5\u23f5 bypass permissions on") is None


def test_dialog_pilot_escapes_auto_mode_offer_and_blocks_unknown() -> None:
    pilot = DialogPilot()
    assert pilot.reply("Make auto mode default? No, keep bypass permissions", now=0.0) == ESCAPE
    unknown = DialogPilot()
    assert unknown.reply("Pick a theme\nEnter to confirm", now=0.0) is None
    assert "does not know" in (unknown.blocker("Pick a theme\nEnter to confirm") or "")


def test_submit_held_reads_the_hint() -> None:
    assert submit_held("Removed 1 invisible character \u00b7 review and press Enter to send")
    assert submit_held("all good") is None


COST_CAPTURE = (
    "Session\nEstimated cost:         $0.0488\nTotal duration (API):   3s\n"
    "Usage by model:\n"
    "claude-sonnet-5-5:4input,168output,62.5kcacheread,10.2kcachewrite($0.0485)\n"
    "claude-haiku-5-5:1.4kinput,240output,0cacheread,0cachewrite($0.0003)\n"
)


def test_parse_cost_output_and_cost_state() -> None:
    report = parse_cost_output("\x1b[1m" + COST_CAPTURE)
    assert report.read and report.usd == pytest.approx(0.0488)
    assert report.input_tokens == 4 + 62_500 + 10_200 + 1_400
    assert report.output_tokens == 408
    no_label = parse_cost_output(COST_CAPTURE.replace("Estimated cost:", ""))
    assert no_label.usd == pytest.approx(0.0488)
    assert not parse_cost_output("nothing here").read
    state = cost_from_state(
        {
            "type": "cost-state",
            "totalCostUSD": 0.05,
            "modelUsage": {"m": {"inputTokens": 4, "cacheReadInputTokens": 6, "outputTokens": 2}},
        }
    )
    assert state is not None and (state.usd, state.input_tokens, state.output_tokens) == (0.05, 10, 2)
    assert cost_from_state({"type": "user"}) is None


def test_background_work_holds_the_turn_until_notified() -> None:
    work = BackgroundWork()
    work.observe(
        {
            "type": "assistant",
            "message": {"content": [{"type": "tool_use", "id": "t1", "name": "Bash", "input": {}}]},
        }
    )
    work.observe(
        {
            "type": "user",
            "toolUseResult": {"backgroundTaskId": "b1"},
            "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "content": "started"}]},
        }
    )
    assert work.holds_turn_open()
    note = "<task-notification><task-id>b1</task-id><status>completed</status></task-notification>"
    work.observe({"type": "user", "message": {"content": note}})
    assert not work.holds_turn_open()


def test_pretrust_marks_the_folder_trusted_then_revokes(tmp_path: Path) -> None:
    config_dir = tmp_path / "cfg"
    (config_dir).mkdir()
    path = config_dir / ".claude.json"
    path.write_text(json.dumps({"keep": 1, "projects": {"/other": {"hasTrustDialogAccepted": True}}}))
    path.chmod(0o640)
    inode = path.stat().st_ino
    grant = pretrust(tmp_path, config_dir)
    data = json.loads(path.read_text())
    assert data["keep"] == 1 and data["hasCompletedOnboarding"] is True
    assert data["projects"][str(tmp_path.resolve())]["hasTrustDialogAccepted"] is True
    # Replaced by rename, never rewritten in place; mode kept; no temp file left.
    assert path.stat().st_ino != inode and path.stat().st_mode & 0o777 == 0o640
    assert sorted(p.name for p in config_dir.iterdir()) == [".claude.json", ".claude.json.chipin.lock"]
    revoke_trust(grant)
    data = json.loads(path.read_text())
    assert data["projects"] == {"/other": {"hasTrustDialogAccepted": True}} and data["keep"] == 1


def test_revoke_restores_an_entry_that_existed(tmp_path: Path) -> None:
    path = tmp_path / ".claude.json"
    cwd = str(tmp_path.resolve())
    path.write_text(json.dumps({"projects": {cwd: {"allowedTools": ["x"]}}}))
    grant = pretrust(tmp_path, tmp_path)
    assert json.loads(path.read_text())["projects"][cwd]["hasTrustDialogAccepted"] is True
    revoke_trust(grant)
    assert json.loads(path.read_text())["projects"][cwd] == {"allowedTools": ["x"]}
    # Trusted by the person already: nothing to undo.
    path.write_text(json.dumps({"projects": {cwd: {"hasTrustDialogAccepted": True}}}))
    revoke_trust(pretrust(tmp_path, tmp_path))
    assert json.loads(path.read_text())["projects"][cwd] == {"hasTrustDialogAccepted": True}


def test_pretrust_leaves_a_malformed_file_alone(tmp_path: Path) -> None:
    path = tmp_path / ".claude.json"
    path.write_text("{not json")
    revoke_trust(pretrust(tmp_path, tmp_path))
    assert path.read_text() == "{not json"


def test_review_output_schema_then_files(tmp_path: Path) -> None:
    schema = {"type": "object", "properties": {"n": {"type": "integer"}}, "required": ["n"]}
    data, fix = review_output(tmp_path, schema, ["a.txt"], attempt=1, output_file="./out.json")
    assert data is None and fix is not None and "does not exist yet" in fix
    (tmp_path / STRUCT_OUT_FILENAME).write_text('{"n": "x"}')
    _, fix = review_output(tmp_path, schema, ["a.txt"], attempt=2, output_file="./out.json")
    assert fix is not None and "<validation-feedback>" in fix and "Attempt 2" in fix
    (tmp_path / STRUCT_OUT_FILENAME).write_text('{"n": 3}')
    _, fix = review_output(tmp_path, schema, ["a.txt"], attempt=3, output_file="./out.json")
    assert fix is not None and "- a.txt" in fix
    (tmp_path / "a.txt").write_text("x")
    assert review_output(tmp_path, schema, ["a.txt"], attempt=4, output_file="./out.json") == ({"n": 3}, None)


def test_mailbox_refuses_when_closed() -> None:
    box = InjectMailbox()
    assert not box.try_put("early")
    box.open()
    assert box.try_put("one") and box.try_put("two") and box.pending()
    assert box.drain() == ["one", "two"] and not box.pending()
    box.try_put("late")
    assert box.close() == ["late"] and not box.try_put("after")


@pytest.fixture
def fake_cli(tmp_path: Path) -> Path:
    """An executable ``claude`` that runs ``fake_claude_cli.py`` with this interpreter."""
    wrapper = tmp_path / "bin" / "claude"
    wrapper.parent.mkdir()
    wrapper.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{FAKE_CLI}" "$@"\n')
    wrapper.chmod(0o755)
    return wrapper


async def test_run_against_fake_cli(config: BackendConfig, tmp_path: Path, fake_cli: Path) -> None:
    cli = config.agents.claude_cli.model_copy(
        update={"cli_path": str(fake_cli), "config_dir": tmp_path / "claude-config"}
    )
    agents = config.agents.model_copy(update={"claude_cli": cli})
    spec = AgentSpec(
        name="fake",
        prompts=["write hello.txt", "now report"],
        output_schema={
            "type": "object",
            "properties": {"file": {"type": "string"}, "ok": {"type": "boolean"}},
            "required": ["file", "ok"],
        },
        expected_files=["hello.txt"],
        workdir=tmp_path / "work",
        timeout_s=120,
    )
    sink = ListSink()
    backend = backend_for("claude_cli", agents)
    result = await backend.run(spec, sink)

    assert not result.failed, result.error
    assert result.structured_output == {"file": "hello.txt", "ok": True}
    assert result.final_text == "done 2"
    assert result.cost_usd == pytest.approx(0.0456)  # from the cost-state record at /quit
    assert result.files == ["hello.txt"]
    kinds = sink.kinds()
    assert kinds[0] == "agent_start" and kinds[-2:] == ["cost", "agent_end"]
    assert kinds.count("tool_call") == 2 and kinds.count("tool_result") == 2
    cost = sink.events[-2].data
    assert cost == {"usd": pytest.approx(0.0456), "input_tokens": 0, "output_tokens": 0}
    # The run's folder was trusted only while it ran.
    trusted: dict[str, Any] = json.loads((tmp_path / "claude-config" / ".claude.json").read_text())
    assert str(spec.workdir.resolve()) not in trusted["projects"]
    assert trusted["hasCompletedOnboarding"] is True


async def test_run_fails_cleanly_when_output_never_validates(
    config: BackendConfig, tmp_path: Path, fake_cli: Path
) -> None:
    cli = config.agents.claude_cli.model_copy(
        update={"cli_path": str(fake_cli), "config_dir": tmp_path / "claude-config"}
    )
    agents = config.agents.model_copy(update={"claude_cli": cli})
    spec = AgentSpec(
        name="fake",
        prompts=["write hello.txt"],
        expected_files=["missing.txt"],
        output_retries=1,
        workdir=tmp_path / "work",
        timeout_s=120,
    )
    sink = ListSink()
    result = await backend_for("claude_cli", agents).run(spec, sink)
    assert result.failed and "missing.txt" in (result.error or "")
    assert "error" in sink.kinds() and sink.kinds()[-1] == "agent_end"


@pytest.mark.live
async def test_live_claude_cli_run(config: BackendConfig, tmp_path: Path) -> None:
    """A real ``claude`` run with this machine's login: write a file, report as JSON."""
    import shutil

    if shutil.which(config.agents.claude_cli.cli_path) is None:
        pytest.skip("the claude CLI is not installed")
    spec = AgentSpec(
        name="live",
        prompts=["Create hello.txt containing exactly the line: hello chipin. Then say done."],
        model="sonnet",
        effort="low",
        output_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]},
        expected_files=["hello.txt"],
        workdir=tmp_path / "work",
        timeout_s=600,
    )
    sink = ListSink()
    result = await backend_for("claude_cli", config.agents).run(spec, sink)
    assert not result.failed, result.error
    assert (tmp_path / "work" / "hello.txt").read_text().strip() == "hello chipin"
    assert "tool_call" in sink.kinds()
    assert result.cost_usd > 0
