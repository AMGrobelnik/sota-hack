"""The contract's event log for one run: ``events.jsonl``, numbered from 1.

Every event is appended to the file as it happens and kept in memory, so a
stream can replay from any ``seq`` and a reconnect, or a server restart,
loses nothing. Appends may come from worker threads (the ``claude_cli``
backend emits from one); waiters on the event loop are woken thread-safely.
"""

from __future__ import annotations

import asyncio
import json
import threading
from pathlib import Path
from typing import Any

from loguru import logger

from chipmonk_backend.agents.types import utc_now

API_EVENTS_FILE = "events.jsonl"
#: The stages of a ChipIn run, in order (contract version 1).
STAGES = ("spec", "reference", "propose", "finetune", "compile", "verify", "report")
FINISHED = "run.finished"


class EventLog:
    """Append-only, replayable list of contract events for one run."""

    def __init__(self, path: Path, run_id: str, loop: asyncio.AbstractEventLoop) -> None:
        self.path = path
        self.run_id = run_id
        self._loop = loop
        self._lock = threading.Lock()
        self._events: list[dict[str, Any]] = []
        self._changed = asyncio.Event()
        if path.is_file():
            self._events = _read_jsonl(path)

    @property
    def changed(self) -> asyncio.Event:
        """Set at the next append; take it BEFORE reading :meth:`since` to miss nothing."""
        return self._changed

    @property
    def finished(self) -> bool:
        """Whether ``run.finished`` has been written."""
        with self._lock:
            return bool(self._events) and self._events[-1]["type"] == FINISHED

    @property
    def last_seq(self) -> int:
        """The seq of the newest event, 0 when there is none."""
        with self._lock:
            return self._events[-1]["seq"] if self._events else 0

    def append(self, type_: str, **fields: Any) -> dict[str, Any] | None:
        """Write one event; ``None`` (dropped) once the run has finished."""
        with self._lock:
            if self._events and self._events[-1]["type"] == FINISHED:
                logger.debug("run {}: {} after run.finished dropped", self.run_id, type_)
                return None
            event = {
                "seq": (self._events[-1]["seq"] + 1) if self._events else 1,
                "ts": utc_now(),
                "run_id": self.run_id,
                "type": type_,
                **{k: v for k, v in fields.items() if v is not None},
            }
            try:
                with self.path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(event, ensure_ascii=False) + "\n")
            except OSError as exc:
                logger.error("run {}: event write to {} failed: {}", self.run_id, self.path, exc)
            self._events.append(event)
        self._wake()
        return event

    def since(self, seq: int) -> list[dict[str, Any]]:
        """Every event with ``seq >= seq``, oldest first."""
        with self._lock:
            return [event for event in self._events if event["seq"] >= seq]

    def wake(self) -> None:
        """Wake every waiter without an event (server shutdown)."""
        self._wake()

    def _wake(self) -> None:
        try:
            self._loop.call_soon_threadsafe(self._bump)
        except RuntimeError:
            logger.debug("run {}: event loop closed; no waiter to wake", self.run_id)

    def _bump(self) -> None:
        changed, self._changed = self._changed, asyncio.Event()
        changed.set()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    """The events in ``path``; a torn last line (crash mid-write) is skipped."""
    events: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                logger.warning("{}: skipping an unreadable event line", path)
    return events


__all__ = ["API_EVENTS_FILE", "FINISHED", "STAGES", "EventLog"]
