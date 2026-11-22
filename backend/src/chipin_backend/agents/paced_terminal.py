"""The ``openrouter`` agent's terminal: the SDK's subprocess terminal, fed in small pieces.

The OpenHands subprocess terminal writes a whole command into its PTY with one
``write``. A tty keeps only about 1 KiB of unread input (macOS: ``TTYHOG``
1024 bytes) and drops the rest, so a single-line command longer than that
loses its tail, closing quote and Enter included: bash waits for the rest of
the line, the tool times out, and the agent is stuck. A ``./subagent start``
with a long brief is exactly such a line (run 20261122-121312-1337eb stalled
seven minutes on one). The SDK paces only commands of more than 20 lines.

:class:`PacedSubprocessTerminal` writes every input in pieces well under that
limit, waiting for the PTY between them, so a command of any length arrives
whole. Requires the ``openhands`` extra; import this module only where the
SDK is installed.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Mapping, Sequence
from typing import Any

from openhands.sdk.tool import register_tool
from openhands.tools.terminal.definition import TerminalTool
from openhands.tools.terminal.env import normalize_terminal_env
from openhands.tools.terminal.impl import TerminalExecutor
from openhands.tools.terminal.terminal.subprocess_terminal import SubprocessTerminal
from openhands.tools.terminal.terminal.terminal_session import TerminalSession
from openhands.tools.terminal.terminal.tmux_pane_pool import DEFAULT_MAX_PANES

#: The registry name the backend asks for; the model still sees the tool as ``terminal``.
PACED_TERMINAL = "chipin_paced_terminal"
#: Bytes per PTY write: a quarter of the smallest tty input queue we run on.
CHUNK_BYTES = 256


class PacedSubprocessTerminal(SubprocessTerminal):
    """A :class:`SubprocessTerminal` whose PTY writes never exceed :data:`CHUNK_BYTES`."""

    def _write_pty(self, data: bytes) -> None:
        for start in range(0, len(data), CHUNK_BYTES):
            if start:
                # Let the shell read the last piece before the next lands.
                self._wait_for_pty_writable(self._SELECT_WRITE_TIMEOUT)
                time.sleep(self._LINE_PACING_DELAY)
            super()._write_pty(data[start : start + CHUNK_BYTES])


class PacedTerminalExecutor(TerminalExecutor):
    """The SDK's ``TerminalExecutor`` on one :class:`PacedSubprocessTerminal` session.

    ``TerminalExecutor.__init__`` builds its session through a factory with no
    way to pass a terminal class, so this sets the same fields itself (for the
    pinned ``openhands-tools`` 1.49.2) and starts the paced session instead.
    """

    def __init__(
        self,
        working_dir: str,
        *,
        env: Mapping[str, str] | None = None,
        full_output_save_dir: str | None = None,
    ) -> None:
        self.shell_path = None
        self._working_dir = working_dir
        self._username = None
        self._no_change_timeout_seconds = None
        self._terminal_type = "subprocess"
        self._env = normalize_terminal_env(env)
        self._max_panes = DEFAULT_MAX_PANES
        self.full_output_save_dir = full_output_save_dir
        self._pool = None
        self._sessions = {}
        self._sessions_lock = threading.Lock()
        self._pool_recovery_lock = threading.Lock()
        terminal = PacedSubprocessTerminal(working_dir, env=self._env)
        self._session = TerminalSession(terminal, None)
        self._session.initialize()


class PacedTerminalTool(TerminalTool):
    """Registry entry that builds a plain ``terminal`` tool on a :class:`PacedTerminalExecutor`."""

    @classmethod
    def create(  # type: ignore[override]
        cls, conv_state: Any, *, env: Mapping[str, str] | None = None, **_: Any
    ) -> Sequence[TerminalTool]:
        executor = PacedTerminalExecutor(
            conv_state.workspace.working_dir,
            env=env,
            full_output_save_dir=conv_state.env_observation_persistence_dir,
        )
        # ``TerminalTool.create``, not ``cls.create``: the tool keeps the name ``terminal``.
        return TerminalTool.create(conv_state, executor=executor)


register_tool(PACED_TERMINAL, PacedTerminalTool)

__all__ = ["CHUNK_BYTES", "PACED_TERMINAL", "PacedSubprocessTerminal", "PacedTerminalExecutor"]
