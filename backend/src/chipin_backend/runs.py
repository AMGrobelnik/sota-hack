"""Runs are folders on disk; no database.

Layout of one run::

    <runs_dir>/<run_id>/
        run.json       # RunRecord: status, mode, spec, config, result, timings, cost
        events.jsonl   # one AgentEvent per line, appended as they happen
        llm_calls.jsonl  # OpenRouter calls the agent made via ``ask`` (if enabled)
        workspace/     # the agent's working folder (default AgentSpec.workdir)

:class:`JsonlEventSink` is the event journal: an append-only file, no
database.
"""

from __future__ import annotations

import json
import re
import secrets
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from loguru import logger

from chipin_backend.agents.types import AgentEvent, utc_now

#: ``stopped``: interrupted (Ctrl-C, task cancelled) before it finished.
RunStatus = Literal["created", "running", "succeeded", "failed", "stopped"]
RECORD_FILE = "run.json"
EVENTS_FILE = "events.jsonl"
WORKSPACE_DIR = "workspace"
LLM_CALLS_FILE = "llm_calls.jsonl"
#: A run id is one plain path segment: no separators, no ``..``, bounded length.
_SAFE_RUN_ID = re.compile(r"[A-Za-z0-9._-]{1,128}")


def new_run_id() -> str:
    """A sortable, unique id: ``YYYYmmdd-HHMMSS-<6 hex>`` (UTC)."""
    return f"{datetime.now(UTC):%Y%m%d-%H%M%S}-{secrets.token_hex(3)}"


def is_safe_run_id(run_id: str) -> bool:
    """Whether ``run_id`` is a single safe folder name (letters, digits, ``._-``; not ``.``/``..``)."""
    return bool(_SAFE_RUN_ID.fullmatch(run_id)) and run_id not in (".", "..")


@dataclass
class RunRecord:
    """The JSON record of one run (``run.json``)."""

    run_id: str
    run_mode: str
    agent: dict[str, Any]  # AgentSpec.to_dict()
    tier: str | None = None
    status: RunStatus = "created"
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    result: dict[str, Any] | None = None  # AgentResult.to_dict()
    error: str | None = None
    #: Free-form facts a runner records, e.g. pod id, machine, $/hr.
    compute: dict[str, Any] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)  # resolved BackendConfig, no secrets
    finished_at: str | None = None
    duration_s: float | None = None  # wall clock of the whole run
    agent_cost_usd: float | None = None  # as the agent backend reported it
    #: OpenRouter spend: the agent's ``ask`` calls, the end-of-run summary and the level summaries.
    llm_cost_usd: float | None = None
    llm_calls: int = 0
    #: Fan-out runs only (left out of the file otherwise): one entry per
    #: subagent, and what they cost together.
    subagents: list[dict[str, Any]] | None = None
    subagent_cost_usd: float | None = None
    #: The level summaries' share of ``llm_cost_usd`` (live API runs; left out otherwise).
    summaries_usd: float | None = None
    #: The intake's follow-up questions call's share of ``llm_cost_usd`` (live API runs; left out otherwise).
    questions_usd: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Plain JSON-ready dict; the fan-out fields only when set."""
        data = asdict(self)
        for name in ("subagents", "subagent_cost_usd", "summaries_usd", "questions_usd"):
            if data[name] is None:
                del data[name]
        return data


def event_summary(event: AgentEvent, *, width: int = 160) -> str:
    """One short line describing ``event``, for the console and the log file."""
    data = event.data
    if event.kind in ("text", "thinking"):
        detail = data.get("text", "")
    elif event.kind == "tool_call":
        detail = f"{data.get('tool')} {json.dumps(data.get('input'), ensure_ascii=False)}"
    elif event.kind == "tool_result":
        detail = f"{'error ' if data.get('is_error') else ''}{data.get('output', '')}"
    elif event.kind in ("status", "error"):
        detail = data.get("message", "")
    else:
        detail = json.dumps(data, ensure_ascii=False)
    flat = " ".join(str(detail).split())
    return flat if len(flat) <= width else flat[: width - 3] + "..."


class JsonlEventSink:
    """Appends each event as one JSON line and logs a one-line summary of it.

    Thread-safe; never raises on write errors.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()

    def emit(self, event: AgentEvent) -> None:
        """Append ``event``; an OSError is logged, not raised, so the agent keeps going."""
        logger.info("[{}] {}: {}", event.agent, event.kind, event_summary(event))
        line = json.dumps(event.to_dict(), ensure_ascii=False)
        with self._lock:
            try:
                with self.path.open("a", encoding="utf-8") as handle:
                    handle.write(line + "\n")
            except OSError as exc:
                logger.error("event write to {} failed: {}", self.path, exc)


@dataclass(frozen=True)
class RunDir:
    """Handle on one run folder."""

    path: Path

    @classmethod
    def create(cls, runs_dir: Path, run_id: str | None = None) -> RunDir:
        """Make ``runs_dir/<run_id>/workspace``; ``FileExistsError`` if the run exists,
        ``ValueError`` for a run id that is not one safe folder name."""
        chosen = new_run_id() if run_id is None else run_id
        if not is_safe_run_id(chosen):
            raise ValueError(f"bad run_id {chosen!r}: use letters, digits, '.', '_' or '-' (max 128)")
        run = cls(runs_dir / chosen)
        run.path.mkdir(parents=True, exist_ok=False)
        run.workspace.mkdir()
        return run

    @property
    def run_id(self) -> str:
        """The folder name."""
        return self.path.name

    @property
    def record_path(self) -> Path:
        """``run.json``."""
        return self.path / RECORD_FILE

    @property
    def events_path(self) -> Path:
        """``events.jsonl``."""
        return self.path / EVENTS_FILE

    @property
    def workspace(self) -> Path:
        """The agent's default working folder."""
        return self.path / WORKSPACE_DIR

    @property
    def owned_path(self) -> Path:
        """The folder this run owns: the runner prepares a working folder (the chip-lab skill)
        only inside it."""
        return self.path

    @property
    def llm_calls_path(self) -> Path:
        """``llm_calls.jsonl``: one line per OpenRouter call the agent made via ``ask``."""
        return self.path / LLM_CALLS_FILE

    def read_llm_calls(self) -> list[dict[str, Any]]:
        """Every ``ask`` call recorded so far (unreadable lines are skipped)."""
        if not self.llm_calls_path.is_file():
            return []
        calls = []
        for line in self.llm_calls_path.read_text(encoding="utf-8").splitlines():
            try:
                calls.append(json.loads(line))
            except json.JSONDecodeError:
                logger.warning("skipping a malformed line in {}", self.llm_calls_path)
        return calls

    def event_sink(self) -> JsonlEventSink:
        """A sink appending to this run's ``events.jsonl``."""
        return JsonlEventSink(self.events_path)

    def write_record(self, record: RunRecord) -> None:
        """Write ``run.json`` atomically, stamping ``updated_at``."""
        record.updated_at = utc_now()
        tmp = self.record_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(record.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.record_path)

    def read_record(self) -> RunRecord:
        """Load ``run.json``."""
        return RunRecord(**json.loads(self.record_path.read_text(encoding="utf-8")))

    def update_record(self, **fields: Any) -> RunRecord:
        """Set ``fields`` on the record in ``run.json`` and write it back.

        The file is the one record of a run: the orchestrator and the runner
        both change it through here, so neither overwrites the other's facts.
        """
        record = self.read_record()
        for name, value in fields.items():
            if not hasattr(record, name):
                raise TypeError(f"RunRecord has no field {name!r}")
            setattr(record, name, value)
        self.write_record(record)
        return record

    def add_compute(self, **facts: Any) -> RunRecord:
        """Merge ``facts`` into the record's ``compute`` block (pod id, machine, $/hr)."""
        record = self.read_record()
        record.compute.update(facts)
        self.write_record(record)
        return record

    def read_events(self) -> list[AgentEvent]:
        """Every event so far, in order."""
        if not self.events_path.is_file():
            return []
        with self.events_path.open(encoding="utf-8") as handle:
            return [AgentEvent.from_dict(json.loads(line)) for line in handle if line.strip()]


__all__ = [
    "EVENTS_FILE",
    "LLM_CALLS_FILE",
    "RECORD_FILE",
    "WORKSPACE_DIR",
    "JsonlEventSink",
    "RunDir",
    "RunRecord",
    "RunStatus",
    "event_summary",
    "is_safe_run_id",
    "new_run_id",
]
