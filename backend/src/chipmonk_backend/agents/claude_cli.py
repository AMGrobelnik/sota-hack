"""``claude_cli`` backend: drives the interactive ``claude`` CLI under a PTY.

This is NOT the Claude Agent SDK. As in AI Inventor's ``terminal_claude_agent``,
the backend spawns ``claude`` with ``pexpect``, types the prompts into its REPL,
and reads the CLI's own session transcript
(``$CLAUDE_CONFIG_DIR/projects/<cwd-slug>/<session-id>.jsonl``) to turn each
record into :class:`~chipmonk_backend.agents.types.AgentEvent`. A turn ends at
the transcript's ``turn_duration`` record. It authenticates with the CLI's own
subscription login (``claude`` logged in on the machine); ``ANTHROPIC_API_KEY``
is scrubbed from the agent env (:mod:`chipmonk_backend.agents.env`).

The PTY driver lives in :mod:`chipmonk_backend.agents._claude`; this module
holds the run loop: prompts in order, stall recovery (kill, then ``--resume``
the same session), API-error retries, injected messages, output checks and the
``/cost`` read at the end.
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
import subprocess
import threading
import time
from collections import deque
from typing import Any, ClassVar

from loguru import logger

from chipmonk_backend.agents._claude.config_dir import resolve_config_dir
from chipmonk_backend.agents._claude.cost import (
    CostReport,
    TranscriptUsage,
    cost_from_state,
    parse_cost_output,
)
from chipmonk_backend.agents._claude.repl import (
    ReplSession,
    RunDeadlineError,
    TurnResult,
    transcript_path,
)
from chipmonk_backend.agents.base import AgentBackend
from chipmonk_backend.agents.env import build_agent_env
from chipmonk_backend.agents.mailbox import InjectMailbox
from chipmonk_backend.agents.output import (
    STRUCT_OUT_FILENAME,
    review_output,
    struct_out_instruction,
    written_files,
)
from chipmonk_backend.agents.types import AgentEvent, AgentResult, AgentSpec, EventSink
from chipmonk_backend.config import AgentsConfig, ClaudeCliConfig

#: API-error statuses worth another turn (auth blips, rate limits, overload).
RETRYABLE_API_STATUSES = frozenset({401, 429, 500, 502, 503, 529})
#: Consecutive API-error retries before the agent fails.
MAX_API_RETRIES = 5
#: Back-off between API-error retries, by attempt.
API_RETRY_BACKOFF_S = (5.0, 15.0, 30.0, 60.0, 120.0)

#: Sent after a stall restart that resumed the session with the prompt already in it.
STALL_NUDGE = (
    "continue where you left off. The previous session stalled and was restarted; "
    "reuse any partial work already written to disk. Do NOT start over."
)
#: Sent after an API error ended a turn early.
API_ERROR_NUDGE = "continue where you left off (the last request failed with a temporary API error)."

_VERSION_RE = re.compile(r"(\d+(?:\.\d+)*)")


def _parse_version(text: str) -> tuple[int, ...]:
    """The leading dotted version in ``text`` as a comparable tuple."""
    m = _VERSION_RE.search(text)
    if not m:
        raise ValueError(f"unparseable version: {text!r}")
    return tuple(int(p) for p in m.group(1).split("."))


class ClaudeCliBackend(AgentBackend):
    """One ``claude`` REPL session per :meth:`run`; prompts are sent in order."""

    name: ClassVar[str] = "claude_cli"

    def __init__(self, config: AgentsConfig) -> None:
        super().__init__(config)
        self._mailbox = InjectMailbox()
        self._session: ReplSession | None = None
        self._lock = threading.Lock()

    @property
    def cli(self) -> ClaudeCliConfig:
        """This backend's config section."""
        return self.config.claude_cli

    async def run(self, spec: AgentSpec, sink: EventSink) -> AgentResult:
        """Spawn ``claude`` in ``spec.workdir``, drive every prompt, validate, close.

        Steps: check the CLI version (:meth:`check_cli`); pre-trust the workdir;
        spawn with :func:`build_argv` and the env from
        :func:`~chipmonk_backend.agents.env.build_agent_env`; per prompt, write
        it to the PTY and tail the transcript, emitting
        :func:`translate_record` events until the turn ends; on a stall,
        ``--resume`` the same session up to ``spec.retries`` times; validate
        ``spec.output_schema`` and ``spec.expected_files`` with up to
        ``spec.output_retries`` corrective turns; read cost; :meth:`close`.
        """
        if spec.workdir is None:
            raise ValueError("spec.workdir must be set by the runner")
        version = await asyncio.to_thread(self.check_cli)
        spec.workdir.mkdir(parents=True, exist_ok=True)
        self._mailbox.open()
        try:
            return await asyncio.to_thread(self._run_sync, spec, sink, version)
        finally:
            self._mailbox.close()
            await self.close()

    async def inject(self, message: str) -> None:
        """Queue ``message`` as the next user turn of the running session.

        The running turn yields once its own prompt is journaled; the session is
        then resumed and the message typed at a clean prompt. Ignored (with a
        warning) when no run is in progress.
        """
        if not message.strip() or not self._mailbox.try_put(message):
            logger.warning("claude_cli: inject ignored, no run in progress")

    async def close(self) -> None:
        """Exit the REPL and kill its process tree. Idempotent."""
        session, self._session = self._session, None
        if session is not None:
            await asyncio.to_thread(session.close)

    def check_cli(self) -> str:
        """The installed CLI version; ``RuntimeError`` if missing or older than the pin."""
        path = shutil.which(self.cli.cli_path)
        if path is None:
            raise RuntimeError(f"the claude CLI ({self.cli.cli_path!r}) is not on PATH")
        try:
            out = subprocess.run(
                [path, "--version"], capture_output=True, text=True, timeout=30, check=True
            ).stdout
            installed = _parse_version(out)
        except (OSError, subprocess.SubprocessError, ValueError) as err:
            raise RuntimeError(f"could not read the claude CLI version: {err}") from err
        if installed < _parse_version(self.cli.cli_version):
            raise RuntimeError(
                f"claude CLI {'.'.join(map(str, installed))} is older than the "
                f"required {self.cli.cli_version}; upgrade it"
            )
        return ".".join(map(str, installed))

    # ---- the run loop (worker thread) ----

    def _run_sync(self, spec: AgentSpec, sink: EventSink, version: str) -> AgentResult:
        """The whole run, blocking; see :meth:`run`."""
        assert spec.workdir is not None
        workdir = spec.workdir.resolve()
        started = time.monotonic()
        model = spec.model or self.cli.model
        usage = TranscriptUsage()
        exit_cost: list[CostReport] = []
        lock = threading.Lock()

        def emit(kind: str, data: dict[str, Any]) -> None:
            with lock:
                try:
                    sink.emit(AgentEvent(kind, spec.name, data))  # type: ignore[arg-type]
                except Exception:
                    logger.exception("claude_cli: event sink raised; event dropped")

        def on_record(record: dict[str, Any]) -> None:
            usage.add(record)
            if (state := cost_from_state(record)) is not None:
                exit_cost.append(state)
            for event in translate_record(record, spec.name):
                emit(event.kind, event.data)

        env = build_agent_env(
            {
                **spec.env,
                **({"CLAUDE_CONFIG_DIR": str(self.cli.config_dir)} if self.cli.config_dir else {}),
            }
        )
        env.update({"TERM": "xterm-256color", "NO_COLOR": ""})
        env.pop("CLAUDE_CODE_EFFORT_LEVEL", None)
        session = ReplSession(
            argv_for=lambda sid, resume: build_argv(spec, self.cli, session_id=sid, resume=resume),
            cli_path=self.cli.cli_path,
            cwd=workdir,
            env=env,
            config_dir=resolve_config_dir(self.cli.config_dir),
            configured_dir=self.cli.config_dir,
            permission_mode=self.cli.permission_mode,
            stall_s=float(self.cli.stall_timeout_s),
            turn_cap_s=float(self.cli.turn_timeout_s),
            on_record=on_record,
            break_when=self._mailbox.pending,
            deadline=started + spec.timeout_s if spec.timeout_s else None,
        )
        self._session = session
        emit("agent_start", {"backend": self.name, "model": model, "cli_version": version})

        output_file = f"./{STRUCT_OUT_FILENAME}"
        prompts = list(spec.prompts)
        if spec.output_schema is not None:
            (workdir / STRUCT_OUT_FILENAME).unlink(missing_ok=True)
            if prompts:
                prompts[-1] += struct_out_instruction(spec.output_schema, output_file)

        driver = _TurnDriver(session, spec, emit, self._mailbox)
        final_text, error, structured = "", None, None
        try:
            session.start(resume=False)
            for prompt in prompts:
                final_text = driver.send(prompt) or final_text
            for attempt in range(1, spec.output_retries + 2):
                structured, fix = review_output(
                    workdir,
                    spec.output_schema,
                    spec.expected_files,
                    attempt=attempt,
                    output_file=output_file,
                )
                if fix is None:
                    break
                if attempt > spec.output_retries:
                    error = f"output still invalid after {spec.output_retries} corrective turns: {fix}"
                    break
                emit("status", {"message": f"output check failed; corrective turn {attempt}"})
                final_text = driver.send(fix) or final_text
        except (TimeoutError, RunDeadlineError, _AgentFailedError) as err:
            error = str(err)
        # The exact totals come from the ``cost-state`` record the CLI journals
        # as it quits; the ``/cost`` dialog is the fallback for a CLI that
        # cannot quit cleanly.
        dialog = parse_cost_output(session.capture_cost())
        session.close()
        session.read_remaining()
        self._session = None
        cost = exit_cost[-1] if exit_cost else dialog if dialog.read else None
        usd = cost.usd if cost is not None else 0.0
        tokens = (
            (cost.input_tokens, cost.output_tokens) if cost else (usage.input_tokens, usage.output_tokens)
        )

        duration = time.monotonic() - started
        if error:
            emit("error", {"message": error})
        emit(
            "cost",
            {"usd": usd, "input_tokens": tokens[0], "output_tokens": tokens[1]},
        )
        emit(
            "agent_end",
            {"failed": error is not None, "duration_s": duration, "session_id": session.session_id},
        )
        return AgentResult(
            agent=spec.name,
            final_text=final_text,
            structured_output=structured if error is None else None,
            failed=error is not None,
            error=error,
            session_id=session.session_id,
            cost_usd=usd,
            duration_s=duration,
            files=written_files(workdir),
        )


class _AgentFailedError(Exception):
    """The agent cannot go on (stall restarts or API retries used up)."""


class _TurnDriver:
    """Sends one prompt with every recovery the run allows."""

    def __init__(
        self,
        session: ReplSession,
        spec: AgentSpec,
        emit: Any,
        mailbox: InjectMailbox,
    ) -> None:
        self._session = session
        self._spec = spec
        self._emit = emit
        self._mailbox = mailbox
        self._restarts = 0
        self._history: list[str] = []

    def send(self, prompt: str) -> str:
        """Run ``prompt`` (and any message injected meanwhile) to the end of its turn.

        Returns the last non-empty assistant text. A stall restarts the CLI
        (``--resume`` when the transcript exists) up to ``spec.retries`` times;
        a retryable API error gets a continue nudge up to
        :data:`MAX_API_RETRIES` times in a row.
        """
        self._history.append(prompt)
        pending: deque[str] = deque([prompt])
        final_text = ""
        api_retries = 0
        while pending:
            text = pending.popleft()
            try:
                result = self._session.turn(text, system_prompt=self._spec.system_prompt)
            except TimeoutError as err:
                pending.appendleft(self._recover(text, err))
                continue
            final_text = result.final_text or final_text
            if result.interrupted:
                self._emit("status", {"message": "new message received; resuming the session"})
                self._session.kill()
                self._session.start(resume=True)
                pending.extendleft(reversed(self._mailbox.drain()))
                continue
            if result.api_error_status is not None:
                api_retries += 1
                self._api_retry(result, api_retries)
                pending.appendleft(API_ERROR_NUDGE)
                continue
            api_retries = 0
            if not pending:
                pending.extend(self._mailbox.drain())
        return final_text

    def _recover(self, prompt: str, err: TimeoutError) -> str:
        """Restart after a stall; the prompt to send next."""
        if self._restarts >= self._spec.retries:
            raise _AgentFailedError(f"{err} (no restarts left)") from err
        self._restarts += 1
        delivered = self._session.last_delivered
        self._session.kill()
        resumable = self._session.has_transcript()
        self._emit(
            "status",
            {
                "message": f"{err}; restart {self._restarts}/{self._spec.retries} "
                f"({'resumed' if resumable else 'fresh session'})"
            },
        )
        self._session.start(resume=resumable)
        if resumable and delivered:
            return STALL_NUDGE
        if not resumable:
            # A fresh session holds none of the earlier turns: send them all again.
            return "\n\n".join(self._history)
        return prompt

    def _api_retry(self, result: TurnResult, attempt: int) -> None:
        """Wait before retrying an API error, or fail when it is not retryable."""
        status = result.api_error_status
        message = f"API error {status}: {result.api_error_message[:300]}"
        if status not in RETRYABLE_API_STATUSES or attempt > MAX_API_RETRIES:
            raise _AgentFailedError(message)
        wait_s = API_RETRY_BACKOFF_S[min(attempt, len(API_RETRY_BACKOFF_S)) - 1]
        self._emit("status", {"message": f"{message}; retry {attempt} in {wait_s:.0f}s"})
        time.sleep(wait_s)


def build_argv(spec: AgentSpec, cli: ClaudeCliConfig, *, session_id: str, resume: bool) -> list[str]:
    """The ``claude`` command line for ``spec``.

    Flags as in AI Inventor's ``repl_driver._build_argv``: ``--session-id`` or
    ``--resume``, ``--model``, ``--effort``, ``--permission-mode``,
    ``--dangerously-skip-permissions``, ``--setting-sources``, ``--settings``
    (JSON), ``--allowed-tools``, ``--disallowed-tools``, ``--mcp-config``.
    The system prompt is not a flag: it is typed with the first prompt, so a
    resumed session keeps it without sending it twice.
    """
    argv = ["--resume", session_id] if resume else ["--session-id", session_id]
    # At flag precedence, so no settings file can turn these off: hop to a
    # sibling model when a message is flagged instead of stalling the turn,
    # and accept the Bypass Permissions warning without its dialog.
    settings: dict[str, Any] = {
        "switchModelsOnFlag": True,
        "skipDangerousModePermissionPrompt": True,
        "hooks": {},
    }
    argv += [
        "--model",
        spec.model or cli.model,
        "--permission-mode",
        cli.permission_mode,
    ]
    if cli.skip_permissions:
        argv.append("--dangerously-skip-permissions")
    argv += ["--settings", json.dumps(settings)]
    argv += ["--setting-sources", ",".join(cli.setting_sources)]
    argv += ["--effort", spec.effort or cli.effort]
    if spec.allowed_tools is not None:
        argv += ["--allowed-tools", ",".join(spec.allowed_tools)]
    if spec.disallowed_tools is not None:
        argv += ["--disallowed-tools", ",".join(spec.disallowed_tools)]
    if spec.mcp_servers:
        servers = spec.mcp_servers.get("mcpServers", spec.mcp_servers)
        argv += ["--mcp-config", json.dumps({"mcpServers": servers})]
    return argv


def _tool_output(content: Any) -> str:
    """A tool result's content as text (string, or the text of its blocks)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
            elif isinstance(block, dict):
                parts.append(f"[{block.get('type', 'block')}]")
        return "\n".join(parts)
    return "" if content is None else json.dumps(content, default=str)


def translate_record(record: dict[str, object], agent: str) -> list[AgentEvent]:
    """Events for one transcript JSONL record (zero or more).

    Assistant blocks become ``text``, ``thinking`` and ``tool_call``; tool
    results become ``tool_result``; a compaction becomes a ``status``. Records
    from a delegated agent carry ``"subagent": <agentId>`` in their data. The
    prompts this backend typed, API-error records (handled by the run loop)
    and bookkeeping records yield nothing.
    """
    kind = record.get("type")
    message = record.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    extra = {"subagent": record["agentId"]} if record.get("isSidechain") and record.get("agentId") else {}
    events: list[AgentEvent] = []

    def add(event_kind: str, data: dict[str, Any]) -> None:
        events.append(AgentEvent(event_kind, agent, {**data, **extra}))  # type: ignore[arg-type]

    if kind == "assistant" and isinstance(content, list) and not record.get("isApiErrorMessage"):
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if btype == "text" and block.get("text"):
                add("text", {"text": block["text"]})
            elif btype == "thinking" and block.get("thinking"):
                add("thinking", {"text": block["thinking"]})
            elif btype == "tool_use":
                add(
                    "tool_call",
                    {
                        "tool": block.get("name", ""),
                        "input": block.get("input", {}),
                        "call_id": block.get("id", ""),
                    },
                )
    elif kind == "user" and isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                add(
                    "tool_result",
                    {
                        "call_id": block.get("tool_use_id", ""),
                        "output": _tool_output(block.get("content")),
                        "is_error": bool(block.get("is_error")),
                    },
                )
    elif kind == "system" and record.get("subtype") == "compact_boundary":
        add("status", {"message": "context compacted"})
    return events


__all__ = ["ClaudeCliBackend", "build_argv", "transcript_path", "translate_record"]
