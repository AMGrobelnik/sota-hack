"""The contract's event log for one run: ``events.jsonl``, numbered from 1.

Every event is appended to the file as it happens and kept in memory, so a
stream can replay from any ``seq`` and a reconnect, or a server restart,
loses nothing. Appends may come from worker threads (the ``claude_cli``
backend emits from one); waiters on the event loop are woken thread-safely.

The file keeps the events as written. What the API serves comes from
:meth:`EventLog.public_since`: the same events through the shared scrubber
(``chipin_backend/scrub.py``: home paths, user and host names, e-mails and
key shapes replaced), each scrubbed once and kept. Every ``cost`` event
carries ``run_total_usd`` and ``agent_usd`` (``api/costs.py``), added as it
is written, and to the events of an older run as they are read back.
"""

from __future__ import annotations

import asyncio
import json
import re
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from loguru import logger

from chipin_backend.agents.types import utc_now
from chipin_backend.api.costs import CostLedger
from chipin_backend.scrub import scrub_value

API_EVENTS_FILE = "events.jsonl"
#: Per event type, the text fields that may carry an error's wording (see :func:`public_text`).
_ERROR_TEXT_FIELDS = {"error": ("message",), "run.finished": ("summary",), "status": ("text",)}
#: An absolute local path of two or more parts, not part of a URL or a relative path.
_ABSOLUTE_PATH = re.compile(r"(?<![\w.:/~-])/(?:[\w.@+-]+/)+[\w.@+-]*")
#: The stages of a ChipIn run, in order (contract version 1).
STAGES = ("spec", "reference", "propose", "finetune", "compile", "verify", "report")
FINISHED = "run.finished"


def public_text(text: str, root: Path | None = None) -> str:
    """``text`` with no local absolute path: one inside ``root`` relative to it, any
    other cut to its last part. Error text reaches the stream and the API."""
    out = str(text)
    if root is not None:
        for folder in sorted({str(root.resolve()), str(root)}, key=len, reverse=True):
            out = out.replace(f"{folder}/", "").replace(folder, ".")
    return _ABSOLUTE_PATH.sub(lambda m: m.group().rstrip("/").rsplit("/", 1)[-1] or ".", out)


class EventLog:
    """Append-only, replayable list of contract events for one run.

    Error wording (``error`` messages, ``run.finished`` summaries, status
    lines) is written with paths relative to the run folder (:func:`public_text`).
    """

    def __init__(self, path: Path, run_id: str, loop: asyncio.AbstractEventLoop) -> None:
        self.path = path
        self.run_id = run_id
        self._loop = loop
        self._lock = threading.Lock()
        self._events: list[dict[str, Any]] = []
        self._changed = asyncio.Event()
        self._reopened = False
        #: Called with each new event, under the lock and in seq order; a listener only schedules work.
        self.listeners: list[Callable[[dict[str, Any]], None]] = []
        self._ledger = CostLedger()
        self._public: dict[int, dict[str, Any]] = {}
        if path.is_file():
            for event in _read_jsonl(path):
                extra = self._ledger.fields(event)
                self._events.append({**event, **extra} if extra else event)

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
        """Write one event; ``None`` (dropped) once the run has finished, unless reopened."""
        with self._lock:
            if self._events and self._events[-1]["type"] == FINISHED and not self._reopened:
                logger.debug("run {}: {} after run.finished dropped", self.run_id, type_)
                return None
            for key in _ERROR_TEXT_FIELDS.get(type_, ()):
                if isinstance(fields.get(key), str):
                    fields[key] = public_text(fields[key], self.path.parent)
            fields.update(self._ledger.fields({"type": type_, **fields}))
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
            if type_ == FINISHED:
                self._reopened = False
            for listener in self.listeners:
                try:
                    listener(event)
                except Exception:
                    logger.exception("run {}: an event listener failed", self.run_id)
        self._wake()
        return event

    def reopen(self) -> None:
        """Take events again after ``run.finished`` (a follow-up), until the next ``run.finished``."""
        with self._lock:
            self._reopened = True

    def since(self, seq: int) -> list[dict[str, Any]]:
        """Every event with ``seq >= seq``, oldest first."""
        with self._lock:
            return [event for event in self._events if event["seq"] >= seq]

    def public_since(self, seq: int) -> list[dict[str, Any]]:
        """:meth:`since`, every event scrubbed for display (each one scrubbed once, then kept)."""
        out: list[dict[str, Any]] = []
        for event in self.since(seq):
            key = int(event["seq"])
            public = self._public.get(key)
            if public is None:
                public = self._public[key] = scrub_value(event)
            out.append(public)
        return out

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


__all__ = ["API_EVENTS_FILE", "FINISHED", "STAGES", "EventLog", "public_text"]
