"""One ``claude`` REPL session under a PTY: spawn, type a turn, tail the transcript.

Synchronous on purpose: ``pexpect`` is blocking, so the backend runs this in a worker thread.

A turn is typed as one bracketed paste and ends at the transcript's
``system/turn_duration`` record, or at an API-error record (the CLI writes no
``turn_duration`` after one). Every record goes to ``on_record`` as it arrives.
"""

from __future__ import annotations

import contextlib
import json
import os
import select
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn

import pexpect
import psutil
from loguru import logger

from chipin_backend.agents._claude.background import BackgroundWork
from chipin_backend.agents._claude.config_dir import TrustGrant, pretrust, project_slug, revoke_trust
from chipin_backend.agents._claude.delivery import (
    PromptNotDeliveredError,
    bracketed_paste,
    check_delivery,
    typeable,
)
from chipin_backend.agents._claude.screen import (
    DialogPilot,
    permission_mode_marker,
    resume_refused,
    submit_held,
    visible_text,
)
from chipin_backend.agents._claude.steer import TypedMessages

#: Longest wait for the TUI to settle after a spawn.
START_WINDOW_S = 30.0
#: Output must stand still this long before the TUI counts as settled.
SETTLE_S = 2.0
#: Window for the terminal to take a prompt and the transcript to journal it.
COLD_START_S = 120.0
#: Bound on one short write (a key, ``/cost``, ``/quit``).
SHORT_WRITE_S = 10.0
#: CPU seconds the process tree must burn in a silent window to count as busy.
BUSY_CPU_S = 0.5
#: Empties the input box wherever its cursor is: (Ctrl-A, Ctrl-K, Backspace) per line.
CLEAR_INPUT = "\x01\x0b\x7f" * 100 + "\x7f" * 200
#: Folder in the workdir for the driver's own files (the PTY log).
DRIVER_DIR = ".chipin"


class StartFailedError(TimeoutError):
    """The CLI never reached a state where a prompt could be typed.

    A ``TimeoutError``, so the backend's stall recovery restarts it.
    """


class RunDeadlineError(Exception):
    """The run's whole time budget is spent; never retried."""


@dataclass(frozen=True)
class TurnResult:
    """How one turn ended."""

    final_text: str
    api_error_status: int | None = None
    api_error_message: str = ""
    interrupted: bool = False  # cut short because a message waits (``break_when``)


def transcript_path(config_dir: Path, workdir: Path, session_id: str) -> Path:
    """Where the CLI writes the session transcript for ``workdir``."""
    return config_dir / "projects" / project_slug(workdir.resolve()) / f"{session_id}.jsonl"


def _turn_ending_api_error(records: list[dict[str, Any]]) -> tuple[int, str] | None:
    """``(status, banner)`` of the first main-session API-error record, if any.

    An error inside a delegated agent is that agent's to retry; it does not end
    the parent turn.
    """
    for rec in records:
        if rec.get("isSidechain") or rec.get("isApiErrorMessage") is not True:
            continue
        banner = ""
        for block in (rec.get("message") or {}).get("content") or []:
            if isinstance(block, dict) and block.get("type") == "text":
                banner = block.get("text", "") or ""
                break
        return int(rec.get("apiErrorStatus") or 0), banner
    return None


def _assistant_texts(records: list[dict[str, Any]]) -> list[str]:
    """The main session's assistant text blocks in ``records``."""
    texts = []
    for rec in records:
        if rec.get("type") != "assistant" or rec.get("isSidechain") or rec.get("isApiErrorMessage"):
            continue
        for block in (rec.get("message") or {}).get("content") or []:
            if isinstance(block, dict) and block.get("type") == "text" and block.get("text"):
                texts.append(block["text"])
    return texts


class ReplSession:
    """The ``claude`` CLI for one agent: one session id, respawned with ``--resume`` on a stall."""

    def __init__(
        self,
        *,
        argv_for: Callable[[str, bool], list[str]],
        cli_path: str,
        cwd: Path,
        env: dict[str, str],
        config_dir: Path,
        configured_dir: Path | None,
        permission_mode: str,
        stall_s: float,
        turn_cap_s: float,
        on_record: Callable[[dict[str, Any]], None],
        break_when: Callable[[], bool] = lambda: False,
        deadline: float | None = None,
        inbox: Callable[[], list[str]] = list,
        on_message_delivered: Callable[[str], None] = lambda _text: None,
    ) -> None:
        self._argv_for = argv_for
        self._cli_path = cli_path
        self.cwd = cwd
        self._env = env
        self._config_dir = config_dir
        self._configured_dir = configured_dir
        self._permission_mode = permission_mode
        self._stall_s = stall_s
        self._turn_cap_s = turn_cap_s
        self._on_record = on_record
        self._break_when = break_when
        self._deadline = deadline
        self.session_id = str(uuid.uuid4())
        self._child: pexpect.spawn | None = None
        self._log_path = cwd / DRIVER_DIR / "claude-pty.log"
        self._read_pos: dict[Path, int] = {}
        self._background = BackgroundWork()
        self._first_turn = True
        self.last_delivered = False
        self._trust: TrustGrant | None = None
        #: Messages typed into the running turn (see ``_claude/steer.py``).
        self.typed = TypedMessages(inbox, on_message_delivered)

    # ---- transcript ----

    @property
    def transcript(self) -> Path:
        """This session's transcript file."""
        return transcript_path(self._config_dir, self.cwd, self.session_id)

    def has_transcript(self) -> bool:
        """Whether the transcript exists, so ``--resume`` can reload it."""
        return self.transcript.exists()

    def _session_files(self) -> list[Path]:
        """The main transcript, then every delegated agent's, in name order."""
        subagents = self.transcript.parent / self.session_id / "subagents"
        return [self.transcript, *sorted(subagents.glob("agent-*.jsonl"))]

    def _read_new_records(self) -> list[dict[str, Any]]:
        """Every complete record appended to the session's files since the last read.

        A delegated agent's records live in their own file and are marked
        ``isSidechain`` with its ``agentId``.
        """
        records: list[dict[str, Any]] = []
        for path in self._session_files():
            if not path.exists():
                continue
            pos = self._read_pos.get(path, 0)
            with path.open("rb") as f:
                f.seek(pos)
                data = f.read()
            cut = data.rfind(b"\n") + 1
            if cut == 0:
                continue
            self._read_pos[path] = pos + cut
            marks = (
                {}
                if path == self.transcript
                else {"isSidechain": True, "agentId": path.stem.removeprefix("agent-")}
            )
            for line in data[:cut].splitlines():
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    logger.warning("claude_cli: unparseable transcript line skipped: {!r}", line[:200])
                    continue
                records.append({**marks, **rec})
        return records

    def _fast_forward(self) -> None:
        """Skip everything already on disk (a resumed session's earlier turns)."""
        for path in self._session_files():
            if path.exists():
                self._read_pos[path] = path.stat().st_size

    def read_remaining(self) -> None:
        """Pass on whatever the transcript gained since the last read (e.g. after quitting)."""
        self._deliver(self._read_new_records())

    def _deliver(self, records: list[dict[str, Any]]) -> None:
        for rec in records:
            self._background.observe(rec)
            self._on_record(rec)

    # ---- process ----

    def _check_deadline(self) -> None:
        if self._deadline is not None and time.monotonic() >= self._deadline:
            raise RunDeadlineError("the agent's time budget is spent")

    def continue_session(self, session_id: str) -> None:
        """Take over an earlier session (a follow-up): the next ``start(resume=True)`` reloads it,
        and its standing instructions are not typed again."""
        self.session_id = session_id
        self._first_turn = False

    def start(self, *, resume: bool) -> None:
        """Spawn the CLI and wait until it can take a prompt.

        ``resume`` reloads this session's transcript (``--resume``); a fresh
        start uses a new session id. Raises :class:`StartFailedError` when the
        CLI exits, refuses the resume or shows a dialog the pilot cannot answer.
        """
        if resume and not self.has_transcript():
            resume = False
        if not resume:
            self.session_id = str(uuid.uuid4())
            self._read_pos.clear()
            self._first_turn = True
        else:
            self._fast_forward()
        # Granted again at every spawn: another CLI on the same login may have
        # rewritten the config since. The first grant is the one withdrawn at close.
        grant = pretrust(self.cwd, self._configured_dir)
        if self._trust is None:
            self._trust = grant
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        argv = self._argv_for(self.session_id, resume)
        self._child = pexpect.spawn(
            self._cli_path,
            args=argv,
            cwd=str(self.cwd),
            env=self._env,
            encoding="utf-8",
            codec_errors="replace",
            dimensions=(50, 200),
        )
        self._child.logfile_read = self._log_path.open("a", encoding="utf-8")
        self._settle(resume=resume)

    def _settle(self, *, resume: bool) -> None:
        """Answer startup dialogs and wait for stable output with the mode marker shown."""
        assert self._child is not None
        marker = permission_mode_marker(self._permission_mode)
        pilot = DialogPilot()
        raw = ""
        quiet_for = 0.0
        deadline = time.monotonic() + START_WINDOW_S
        while time.monotonic() < deadline:
            try:
                raw += self._child.read_nonblocking(size=4096, timeout=0.5)
                quiet_for = 0.0
            except pexpect.TIMEOUT:
                quiet_for += 0.5
            except pexpect.EOF:
                pass
            if resume and resume_refused(raw):
                self._fail_start(f"the CLI refused --resume {self.session_id}")
            if not self._child.isalive():
                self._fail_start(f"the CLI exited before it could take a prompt [{pilot.report()}]")
            key = pilot.reply(raw, now=time.monotonic())
            if key is not None:
                self._write(key, deadline=time.monotonic() + SHORT_WRITE_S)
                quiet_for = 0.0
                continue
            if quiet_for >= SETTLE_S and raw:
                if blocker := pilot.blocker(raw):
                    self._fail_start(blocker)
                if marker is None or marker in visible_text(raw[-4096:]):
                    logger.info("claude_cli: CLI ready [{}]", pilot.report())
                    return
        if blocker := pilot.blocker(raw):
            self._fail_start(blocker)
        logger.warning("claude_cli: the TUI did not settle in {:.0f}s; typing anyway", START_WINDOW_S)

    def _fail_start(self, reason: str) -> NoReturn:
        self.kill()
        log = self._log_path.relative_to(self.cwd)
        raise StartFailedError(f"claude CLI start failed: {reason} (PTY log: {log} in the agent's folder)")

    def _write(self, data: str, *, deadline: float) -> None:
        """Write to the PTY without ever blocking past ``deadline``.

        A child that stopped draining its terminal would park a blocking write
        forever, so the master is non-blocking and each chunk waits on
        ``select``; a terminal that takes nothing by the deadline is killed and
        reported as a stall.
        """
        assert self._child is not None
        fd = self._child.child_fd
        payload = data.encode("utf-8")
        os.set_blocking(fd, False)
        while payload:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                self.kill()
                raise TimeoutError("REPL turn stalled (the terminal took no input)")
            if not select.select([], [fd], [], min(remaining, 0.5))[1]:
                continue
            try:
                payload = payload[os.write(fd, payload) :]
            except BlockingIOError:
                continue
            except OSError as err:
                self.kill()
                raise TimeoutError(f"REPL turn stalled (terminal not writable: {err})") from err

    def _drain_screen(self, screen: str) -> str:
        """Read what the CLI drew (so it never blocks on its own output); the last 4 KB."""
        assert self._child is not None
        with contextlib.suppress(pexpect.TIMEOUT, pexpect.EOF):
            screen += self._child.read_nonblocking(size=4096, timeout=0.2)
        return screen[-4096:]

    def _tree_cpu_s(self) -> float:
        """CPU seconds used so far by the CLI and every process under it."""
        if self._child is None:
            return 0.0
        try:
            root = psutil.Process(self._child.pid)
            procs = [root, *root.children(recursive=True)]
        except psutil.Error:
            return 0.0
        total = 0.0
        for proc in procs:
            try:
                times = proc.cpu_times()
                total += times.user + times.system
            except psutil.Error:
                continue
        return total

    # ---- turns ----

    def format_prompt(self, prompt: str, system_prompt: str | None) -> str:
        """The exact text typed for ``prompt``: tagged, and safe to bracket-paste."""
        body = f"<prompt>\n{prompt.strip()}\n</prompt>"
        if self._first_turn and system_prompt:
            body = f"<system-prompt>\n{system_prompt.strip()}\n</system-prompt>\n\n{body}"
        return typeable(body)

    def turn(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        on_journaled: Callable[[], None] | None = None,
    ) -> TurnResult:
        """Type ``prompt`` and block until the turn ends.

        ``on_journaled`` is called once, when the transcript shows the prompt.
        Messages from the inbox are typed while the turn runs; the turn ends
        only once every one of them reached the model and its turn ended.

        Raises ``TimeoutError`` (a stall: nothing journaled, or no progress and
        an idle process tree for a whole window) or :class:`RunDeadlineError`.
        """
        self._check_deadline()
        if self._child is None:
            self.start(resume=True)
        if pending := self._read_new_records():
            self._deliver(pending)
        outgoing = self.format_prompt(prompt, system_prompt)
        started = time.monotonic()
        hard_stop = started + self._turn_cap_s
        deadline = started + min(COLD_START_S, self._stall_s)
        self.last_delivered = False
        self._write(CLEAR_INPUT, deadline=deadline)
        time.sleep(0.3)
        self._write(bracketed_paste(outgoing), deadline=deadline)
        time.sleep(0.4)
        self._write("\r", deadline=deadline)
        self._first_turn = False

        texts: list[str] = []
        screen = ""
        waiting_on_background = False
        cpu_mark = self._tree_cpu_s()
        while True:
            self._check_deadline()
            now = time.monotonic()
            if now >= hard_stop:
                if waiting_on_background:
                    logger.warning(
                        "claude_cli: gave up waiting on background work ({})",
                        self._background.describe(),
                    )
                    break
                raise TimeoutError(f"REPL turn stalled (turn ran past its {self._turn_cap_s:.0f}s cap)")
            if now >= deadline:
                if not self.last_delivered:
                    raise TimeoutError("REPL turn stalled (the prompt never journaled)")
                cpu_now = self._tree_cpu_s()
                alive = self._child is not None and self._child.isalive()
                if alive and (waiting_on_background or cpu_now - cpu_mark >= BUSY_CPU_S):
                    cpu_mark = cpu_now
                    deadline = now + self._stall_s
                    continue
                raise TimeoutError(f"REPL turn stalled (no progress for {self._stall_s:.0f}s)")
            if self.last_delivered and self._break_when():
                return TurnResult(final_text="\n".join(texts), interrupted=True)
            if self.last_delivered:  # the CLI queues what is typed now; see _claude/steer.py
                self.typed.type_waiting(self._short_write)
                self.typed.nudge(self._short_write)
            screen = self._drain_screen(screen)
            held = None if self.last_delivered else submit_held(screen)
            if held and held not in visible_text(outgoing):
                self.kill()
                raise PromptNotDeliveredError(f"REPL turn stalled (prompt held: {held})")
            new = self._read_new_records()
            if not new:
                time.sleep(0.2)
                continue
            if not self.last_delivered:
                self.last_delivered = check_delivery(new, outgoing)
            if self.last_delivered:
                deadline = time.monotonic() + self._stall_s
                if on_journaled is not None:
                    on_journaled, journaled = None, on_journaled
                    journaled()
            texts += _assistant_texts(new)
            for i, rec in enumerate(new):
                # Record by record, so a delivery is reported before the answer to it.
                self.typed.observe([rec])
                self._deliver([rec])
                if rec.get("isSidechain"):
                    continue
                if rec.get("type") in ("user", "assistant"):
                    waiting_on_background = False
                if rec.get("type") == "system" and rec.get("subtype") == "turn_duration":
                    if self.typed:
                        continue  # a typed message still queued goes out as the next turn
                    if not self._background.holds_turn_open():
                        self.typed.observe(new[i + 1 :])
                        self._deliver(new[i + 1 :])
                        return TurnResult(final_text="\n".join(texts))
                    waiting_on_background = True
                    logger.info(
                        "claude_cli: turn ended with background work open ({}); waiting",
                        self._background.describe(),
                    )
            if (api_error := _turn_ending_api_error(new)) is not None:
                status, banner = api_error
                return TurnResult(
                    final_text="\n".join(texts), api_error_status=status, api_error_message=banner
                )
        return TurnResult(final_text="\n".join(texts))

    def _short_write(self, data: str) -> None:
        self._write(data, deadline=time.monotonic() + SHORT_WRITE_S)

    def capture_cost(self, *, idle_s: float = 2.5, max_wait_s: float = 8.0) -> str:
        """Send ``/cost``, return what the dialog drew, and dismiss it; ``""`` with no CLI.

        The dialog keeps animating, so the capture usually ends at ``max_wait_s``.
        """
        if self._child is None or not self._child.isalive():
            return ""
        try:
            return self._capture_cost(idle_s=idle_s, max_wait_s=max_wait_s)
        except TimeoutError:
            return ""  # the terminal took no input and was killed

    def _capture_cost(self, *, idle_s: float, max_wait_s: float) -> str:
        self._write(CLEAR_INPUT, deadline=time.monotonic() + SHORT_WRITE_S)
        time.sleep(0.3)
        self._write("/cost", deadline=time.monotonic() + SHORT_WRITE_S)
        time.sleep(0.3)
        self._write("\r", deadline=time.monotonic() + SHORT_WRITE_S)
        chunks: list[str] = []
        quiet_for = 0.0
        deadline = time.monotonic() + max_wait_s
        while time.monotonic() < deadline and quiet_for < idle_s:
            try:
                chunks.append(self._child.read_nonblocking(size=4096, timeout=0.5))
                quiet_for = 0.0
            except (pexpect.TIMEOUT, pexpect.EOF):
                quiet_for += 0.5
        self._write("\x1b", deadline=time.monotonic() + SHORT_WRITE_S)
        time.sleep(0.2)
        return "".join(chunks)

    def _descendants(self) -> list[psutil.Process]:
        """Every process under the CLI (its shells, background jobs, subagents)."""
        if self._child is None:
            return []
        try:
            return psutil.Process(self._child.pid).children(recursive=True)
        except psutil.Error:
            return []

    def kill(self, extra: list[psutil.Process] | None = None) -> None:
        """Hard-kill the CLI, every process under it and ``extra``. Idempotent."""
        procs = [*self._descendants(), *(extra or [])]
        child, self._child = self._child, None
        self._background.clear()
        if child is not None:
            child.close(force=True)
            if child.logfile_read is not None:
                child.logfile_read.close()
        for proc in procs:
            try:
                proc.kill()
            except psutil.Error:
                continue

    def close(self) -> None:
        """Quit the CLI politely (``/quit``), make sure the whole tree is gone, then
        withdraw the folder trust :meth:`start` granted. Idempotent."""
        try:
            if self._child is not None:
                descendants = self._descendants()
                try:
                    self._write(CLEAR_INPUT, deadline=time.monotonic() + SHORT_WRITE_S)
                    self._write("/quit", deadline=time.monotonic() + SHORT_WRITE_S)
                    time.sleep(0.3)
                    self._write("\r", deadline=time.monotonic() + SHORT_WRITE_S)
                    self._child.expect(pexpect.EOF, timeout=5)
                except (TimeoutError, pexpect.TIMEOUT, pexpect.EOF):
                    pass  # a CLI that will not quit is killed below
                self.kill(descendants)
        finally:
            trust, self._trust = self._trust, None
            if trust is not None:
                revoke_trust(trust)


__all__ = [
    "PromptNotDeliveredError",
    "ReplSession",
    "RunDeadlineError",
    "StartFailedError",
    "TurnResult",
    "transcript_path",
]
