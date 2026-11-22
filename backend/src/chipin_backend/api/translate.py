"""From the agent backends' own events (:class:`AgentEvent`) to contract events.

Agent text becomes ``message``, a tool call and its result become ``tool``
(``started`` then ``done`` or ``failed``) with a one-line human summary,
``cost`` and ``error`` map across, and backend status lines become
``status``. Calls of the run's ``./progress`` helper are not shown as tools:
the progress tailer turns what they write into ``stage``, ``metric`` and
``status`` events instead. ``run.finished`` is written by the run itself.
"""

from __future__ import annotations

import re
import threading
from pathlib import Path
from typing import Any

from loguru import logger

from chipin_backend.agents.types import AgentEvent
from chipin_backend.api.events import EventLog
from chipin_backend.runs import JsonlEventSink

AUTHOR = "ChipIn"
#: The status line when a run's agent starts.
READING_BRIEF = "ChipIn is reading your brief"
SUMMARY_MAX = 120
DETAIL_MAX = 300


#: Terminal escape sequences (colours, cursor moves, titles) and other control characters.
_TERMINAL_NOISE = re.compile(
    r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)?|\x1b.|[\x00-\x08\x0e-\x1f\x7f]"
)


def clip(text: str, limit: int) -> str:
    """``text`` on one line without terminal escapes, cut to ``limit`` characters with an ellipsis."""
    flat = " ".join(_TERMINAL_NOISE.sub("", str(text)).split())
    return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "…"


def _rel(path: Any, workdir: Path | None) -> str:
    """``path`` relative to ``workdir`` when it lies inside it."""
    text = str(path or "")
    if workdir is not None and text:
        try:
            return str(Path(text).resolve().relative_to(workdir.resolve()))
        except (ValueError, OSError):
            return text
    return text


def is_progress_call(tool: str, args: dict[str, Any]) -> bool:
    """Whether a tool call only ran the run's ``progress`` helper."""
    if tool not in {"Bash", "terminal", "execute_bash"}:
        return False
    command = str(args.get("command", "")).strip()
    return command.startswith(("./progress ", "progress ")) and "&&" not in command and ";" not in command


def tool_summary(tool: str, args: dict[str, Any], workdir: Path | None = None) -> str:
    """One human line for a tool call, e.g. ``Read brief.md``."""
    if tool == "Bash":
        command = (str(args.get("command", "")).strip().splitlines() or [""])[0]
        line = f"Ran {args.get('description') or command}"
    elif tool in {"Read", "Write", "Edit", "NotebookEdit"}:
        verb = {"Read": "Read", "Write": "Wrote", "Edit": "Edited", "NotebookEdit": "Edited"}[tool]
        line = f"{verb} {_rel(args.get('file_path') or args.get('notebook_path'), workdir)}"
    elif tool == "Glob":
        line = f"Listed files matching {args.get('pattern', '')}"
    elif tool == "Grep":
        line = f"Searched files for {args.get('pattern', '')}"
    elif tool == "WebFetch":
        line = f"Fetched {args.get('url', '')}"
    elif tool == "WebSearch":
        line = f"Searched the web for {args.get('query', '')}"
    elif tool == "TodoWrite":
        line = "Updated the plan"
    elif tool in {"Task", "Agent"}:
        line = f"Delegated: {args.get('description', '')}"
    else:
        first = next((v for v in args.values() if isinstance(v, str | int | float) and str(v)), "")
        line = f"{tool} {first}".strip()
    return clip(line, SUMMARY_MAX)


class Translator:
    """An :class:`EventSink`: stores the raw event, then writes contract events.

    Thread-safe; never raises into the agent (a failure is logged).
    """

    def __init__(
        self,
        log: EventLog,
        raw: JsonlEventSink,
        workdir: Path | None = None,
        *,
        start_status: str | None = READING_BRIEF,
        errors: bool = True,
    ) -> None:
        self.log = log
        self.raw = raw
        self.workdir = workdir
        #: The status line written when the agent starts (``None``: none).
        self.start_status = start_status
        #: False: the agent's errors are kept (``error_text``) but not written
        #: as ``error`` events; a subagent's failure is not the run's.
        self.errors = errors
        self.error_text: str | None = None
        self._lock = threading.Lock()
        self._calls: dict[str, tuple[str, str]] = {}  # call_id -> (tool name, summary)
        self._hidden: set[str] = set()
        self.error_emitted = False
        self.cost: dict[str, Any] | None = None
        #: The agent's latest message: the run's closing summary.
        self.last_text: str | None = None

    def emit(self, event: AgentEvent) -> None:
        """Record ``event`` and translate it; errors are logged, never raised."""
        self.raw.emit(event)
        try:
            with self._lock:
                self._translate(event)
        except Exception:
            logger.exception("run {}: could not translate a {} event", self.log.run_id, event.kind)

    def _translate(self, event: AgentEvent) -> None:
        data = event.data
        kind = event.kind
        if data.get("subagent") and kind == "text":
            return  # a delegated helper's chatter; its tool calls still show
        if kind == "text" and str(data.get("text", "")).strip():
            self.last_text = str(data["text"]).strip()
            self.log.append("message", role="agent", author=AUTHOR, text=data["text"])
        elif kind == "tool_call":
            self._tool_call(data)
        elif kind == "tool_result":
            self._tool_result(data)
        elif kind == "cost":
            self.cost = {
                "usd": data.get("usd"),
                "tokens_in": data.get("input_tokens"),
                "tokens_out": data.get("output_tokens"),
            }
            self.log.append("cost", **self.cost)
        elif kind == "status" and data.get("message"):
            self.log.append("status", text=clip(data["message"], 200))
        elif kind == "error":
            self.error_text = str(data.get("message", "the agent failed"))
            if self.errors:
                self.error_emitted = True
                self.log.append("error", message=self.error_text)
        elif kind == "agent_start" and self.start_status:
            self.log.append("status", text=self.start_status)

    def _tool_call(self, data: dict[str, Any]) -> None:
        tool = str(data.get("tool", ""))
        args = data.get("input") if isinstance(data.get("input"), dict) else {}
        call_id = str(data.get("call_id", ""))
        if is_progress_call(tool, args):
            self._hidden.add(call_id)
            return
        summary = tool_summary(tool, args, self.workdir)
        self._calls[call_id] = (tool, summary)
        self.log.append("tool", call_id=call_id, name=tool, summary=summary, state="started")

    def _tool_result(self, data: dict[str, Any]) -> None:
        call_id = str(data.get("call_id", ""))
        if call_id in self._hidden:
            self._hidden.discard(call_id)
            return
        tool, summary = self._calls.pop(call_id, ("tool", "Tool finished"))
        output = str(data.get("output", "")).strip()
        if self.workdir is not None:  # show workspace paths relative, as the summaries do
            for folder in {str(self.workdir.resolve()), str(self.workdir)}:
                output = output.replace(f"{folder}/", "").replace(folder, ".")
        self.log.append(
            "tool",
            call_id=call_id,
            name=tool,
            summary=summary,
            state="failed" if data.get("is_error") else "done",
            detail=clip(output, DETAIL_MAX) if output else None,
        )


__all__ = [
    "AUTHOR",
    "READING_BRIEF",
    "Translator",
    "clip",
    "is_progress_call",
    "tool_summary",
]
