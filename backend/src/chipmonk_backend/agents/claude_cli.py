"""``claude_cli`` backend: drives the interactive ``claude`` CLI under a PTY.

This is NOT the Claude Agent SDK. As in AI Inventor's ``terminal_claude_agent``,
the backend spawns ``claude`` with ``pexpect``, types the prompts into its REPL,
and reads the CLI's own session transcript
(``$CLAUDE_CONFIG_DIR/projects/<cwd-slug>/<session-id>.jsonl``) to turn each
record into :class:`~chipmonk_backend.agents.types.AgentEvent`. A turn ends at
the transcript's ``turn_duration`` record. It authenticates with the CLI's own
subscription login (``claude`` logged in on the machine); ``ANTHROPIC_API_KEY``
is scrubbed from the agent env (:mod:`chipmonk_backend.agents.env`).

STUB: the signatures below are the contract; the bodies are to be ported from
AI Inventor's ``aii_lib/src/aii_lib/agent_backend/``:

* ``terminal_claude_agent/agent.py`` (Agent.run / inject / close),
* ``terminal_claude_agent/repl_driver.py`` (``_build_argv``, ``start``),
* ``terminal_claude_agent/_repl_driver/{_records,_dialogs,_pretrust,_watchdog,
  _background,_cli_version,_cost_dialog,_pty_write,_session}.py``,
* ``terminal_claude_agent/jsonl_to_emit.py`` (transcript record -> event),
* ``_shared/core/struct_out.py`` and ``expected_files.py`` (output checks).

Replace every ``aii_lib.run.emit`` call with ``sink.emit(AgentEvent(...))``;
drop DBOS, memory_pool, claude_oauth, OTel and the metering proxy.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from chipmonk_backend.agents.base import AgentBackend
from chipmonk_backend.agents.types import AgentEvent, AgentResult, AgentSpec, EventSink
from chipmonk_backend.config import ClaudeCliConfig


class ClaudeCliBackend(AgentBackend):
    """One ``claude`` REPL session per :meth:`run`; prompts are sent in order."""

    name: ClassVar[str] = "claude_cli"

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
        raise NotImplementedError("claude_cli backend: port from terminal_claude_agent")

    async def inject(self, message: str) -> None:
        """Queue ``message`` as the next user turn of the running session."""
        raise NotImplementedError("claude_cli backend: port inject_mailbox")

    async def close(self) -> None:
        """Exit the REPL and kill its process tree. Idempotent."""
        return None

    def check_cli(self) -> str:
        """The installed CLI version; ``RuntimeError`` if missing or older than the pin."""
        raise NotImplementedError("claude_cli backend: port _repl_driver/_cli_version.py")


def build_argv(spec: AgentSpec, cli: ClaudeCliConfig, *, session_id: str, resume: bool) -> list[str]:
    """The ``claude`` command line for ``spec``.

    Flags as in AI Inventor's ``repl_driver._build_argv``: ``--session-id`` or
    ``--resume``, ``--model``, ``--effort``, ``--permission-mode``,
    ``--dangerously-skip-permissions``, ``--setting-sources``, ``--settings``
    (JSON), ``--allowed-tools``, ``--disallowed-tools``, ``--mcp-config``,
    ``--append-system-prompt``.
    """
    raise NotImplementedError("claude_cli backend: port repl_driver._build_argv")


def transcript_path(config_dir: Path, workdir: Path, session_id: str) -> Path:
    """Where the CLI writes the session transcript for ``workdir``."""
    raise NotImplementedError("claude_cli backend: port _repl_driver/_records.project_dir_for_cwd")


def translate_record(record: dict[str, object], agent: str) -> list[AgentEvent]:
    """Events for one transcript JSONL record (zero or more)."""
    raise NotImplementedError("claude_cli backend: port jsonl_to_emit.JsonlEmitTranslator")


__all__ = ["ClaudeCliBackend", "build_argv", "transcript_path", "translate_record"]
