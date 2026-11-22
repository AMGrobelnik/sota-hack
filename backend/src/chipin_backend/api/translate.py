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


#: Shell tools across the agent backends; their ``command`` is a shell line.
SHELL_TOOLS = frozenset({"Bash", "terminal", "execute_bash"})
#: The longest row line built from a command.
LINE_MAX = 90

_HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][\w]*)\1")
_ASSIGN = re.compile(r"[A-Za-z_]\w*=")
_REDIRECT_NOISE = re.compile(r"\s*\d?>&\d|\s*&?\d?>{1,2}\s*/dev/null")
#: A path of three or more parts, absolute, home-relative or relative.
_LONG_PATH = re.compile(r"(?<![\w:/.~-])(?:~|\.{1,2})?/?(?:[\w.*@+-]+/){2,}[\w.*@+-]*")
#: Words that open a shell line without being its point.
_LEAD_WORDS = re.compile(r"^(?:do|then|else|if|while|until|!|time|nohup|exec|command|\{|\()\s+")
_TIMEOUT_LEAD = re.compile(r"^g?timeout\s+(?:-\S+\s+)*\d+[smhd]?\s+")
#: Segments that only set things up: the line skips them when anything else is left.
_SETUP = re.compile(
    r"^(?:pushd|popd|export|set|source|\.|sleep|true|echo|printf|unset|wait)\b"
    r"|^\.?/?progress\b|^[A-Za-z_]\w*\s*\(\)\s*\{?$"
)
#: Setup that says least about what a call did.
_QUIET = re.compile(r"^(?:export|set|unset|source|\.)\b")
#: Segments that are only shell structure or a folder hop: never the line while anything else is left.
_CONTROL = re.compile(r"^(?:cd|for|select|case|do|then|else|done|fi|esac|break|continue)\b|^[{}()]")


def _drop_heredocs(command: str) -> str:
    """``command`` without heredoc bodies (``cat > f <<'EOF' ... EOF`` keeps ``cat > f``)."""
    out: list[str] = []
    end: str | None = None
    for raw in command.splitlines():
        if end is not None:
            if raw.strip() == end:
                end = None
            continue
        match = _HEREDOC.search(raw)
        if match:
            end = match.group(2)
            raw = (raw[: match.start()] + raw[match.end() :]).rstrip()
        out.append(raw)
    return "\n".join(out)


def _segments(command: str) -> list[str]:
    """Top-level commands of a shell line: split at newlines, ``;``, ``&&``, ``||`` and ``|``.

    Quote-aware (a ``;`` inside quotes stays); a pipeline keeps only its first command.
    """
    parts: list[str] = []
    buf: list[str] = []
    quote = ""
    piped = False  # after a top-level "|": the rest of the pipeline is dropped
    i = 0
    while i < len(command):
        ch = command[i]
        if quote:
            if ch == "\\" and quote == '"' and i + 1 < len(command):
                if not piped:
                    buf.append(command[i : i + 2])
                i += 2
                continue
            if ch == quote:
                quote = ""
            if not piped:
                buf.append(ch)
            i += 1
            continue
        if ch in "'\"":
            quote = ch
        elif ch == "\\" and i + 1 < len(command):
            if not piped:
                buf.append(command[i : i + 2])
            i += 2
            continue
        two = command[i : i + 2]
        if ch in "\n;" or two in ("&&", "||"):
            parts.append("".join(buf))
            buf, piped = [], False
            i += 2 if two in ("&&", "||") else 1
            continue
        if ch == "|":
            piped = True
        elif ch == "&" and two != "&>" and command[i - 1 : i] != ">":
            parts.append("".join(buf))  # a background "&" ends the command too
            buf, piped = [], False
            i += 1
            continue
        if not piped:
            buf.append(ch)
        i += 1
    parts.append("".join(buf))
    return [" ".join(p.split()) for p in parts if p.strip()]


def _strip_lead(segment: str) -> str:
    """``segment`` without control words, timeouts and ``VAR=value`` prefixes before its command."""
    prev = None
    while prev != segment:
        prev = segment
        segment = _LEAD_WORDS.sub("", segment)
        segment = _TIMEOUT_LEAD.sub("", segment)
        match = _ASSIGN.match(segment)
        if match:  # FOO=1 python x.py -> python x.py; a bare assignment stays whole
            rest = segment[match.end() :]
            value_end = _word_end(rest)
            if rest[value_end:].strip():
                segment = rest[value_end:].strip()
    return segment.strip()


def _word_end(text: str) -> int:
    """Where the first shell word of ``text`` ends (quotes kept together)."""
    quote = ""
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\\" and quote != "'":
            i += 2  # an escaped character never ends the word or its quote
            continue
        if quote:
            if ch == quote:
                quote = ""
        elif ch in "'\"":
            quote = ch
        elif ch.isspace():
            return i
        i += 1
    return len(text)


def _short_paths(text: str) -> str:
    """Every path of three or more parts cut to its last two (``a/b/c/d.py`` -> ``c/d.py``)."""

    def last_two(match: re.Match[str]) -> str:
        path = match.group(0)
        trail = "/" if path.endswith("/") else ""
        parts = [p for p in path.split("/") if p]
        return "/".join(parts[-2:]) + trail if len(parts) > 2 else path

    return _LONG_PATH.sub(last_two, text)


def cap_words(text: str, limit: int) -> str:
    """``text`` cut to ``limit`` characters at a word boundary, with an ellipsis when cut."""
    if len(text) <= limit:
        return text
    head = text[: limit - 1]
    space = head.rfind(" ")
    if space >= limit // 3:
        head = head[:space]
    return head.rstrip(" ;,|&") + "…"


def command_line(command: str, workdir: Path | None = None, limit: int = LINE_MAX) -> str:
    """A readable one-line gist of a shell command, built before anything is cut.

    Drops heredoc bodies, leading ``cd <path> &&`` hops, setup steps and ``VAR=value``
    prefixes, keeps the first meaningful command with its arguments, cuts long paths
    to their last two parts, and notes how many more commands follow. ``""`` for an
    empty command.
    """
    text = _TERMINAL_NOISE.sub("", str(command or ""))
    if workdir is not None:
        for folder in {str(workdir.resolve()), str(workdir)}:
            text = text.replace(f"{folder}/", "").replace(folder, ".")
    segments = [_strip_lead(s) for s in _segments(_drop_heredocs(text))]
    segments = [s for s in segments if s]
    if not segments:
        return ""
    meaningful = [
        s for s in segments if not _CONTROL.match(s) and not _SETUP.match(s) and not _is_assignment(s)
    ]
    # Only setup left: a progress call or a pause tells more than setting a variable.
    steps = [s for s in segments if not _CONTROL.match(s)]
    pick = (
        meaningful or [s for s in steps if not _QUIET.match(s) and not _is_assignment(s)] or steps or segments
    )
    first = _short_paths(_REDIRECT_NOISE.sub("", pick[0])).strip() or pick[0]
    more = len(meaningful) - 1 if meaningful else 0
    suffix = f" (+{more} more)" if more > 0 else ""
    return cap_words(first, max(limit - len(suffix), 20)) + suffix


def _is_assignment(segment: str) -> bool:
    match = _ASSIGN.match(segment)
    return bool(match) and not segment[match.end() + _word_end(segment[match.end() :]) :].strip()


def tool_line(
    tool: str, args: dict[str, Any], workdir: Path | None = None, description: str | None = None
) -> str:
    """The collapsed row's line for a tool call.

    The agent's own short description when it gave one (Claude Code's Bash
    ``description``; another backend's action summary as ``description``),
    else for a shell call a gist of the command (:func:`command_line`), else
    :func:`tool_summary`.
    """
    given = description or args.get("description")
    if tool in SHELL_TOOLS and isinstance(given, str) and given.strip():
        return clip(given, SUMMARY_MAX)
    if tool in SHELL_TOOLS:
        gist = command_line(str(args.get("command", "")), workdir)
        if gist:
            return f"Ran {gist}"
    return tool_summary(tool, args, workdir)


def line_from_summary(summary: str) -> str:
    """A row line for a tool event recorded before lines existed: its ``Ran <command>`` summary reshaped."""
    text = str(summary or "").strip()
    if not text.startswith("Ran "):
        return text
    command = text[4:]
    if command.endswith("…"):  # cut mid-word when recorded: the partial last word goes
        command = command[:-1].rsplit(None, 1)[0] if " " in command else command[:-1]
    gist = command_line(command)
    return f"Ran {gist}" if gist else text


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
                # a follow-up's total keeps its parts: own turn, subagents, summaries, questions
                **{
                    k: data[k]
                    for k in ("turn_usd", "subagents_usd", "summaries_usd", "questions_usd")
                    if data.get(k) is not None
                },
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
        description = data.get("description") if isinstance(data.get("description"), str) else None
        line = tool_line(tool, args, self.workdir, description)
        self._calls[call_id] = (tool, summary, line)
        self.log.append("tool", call_id=call_id, name=tool, summary=summary, line=line, state="started")

    def _tool_result(self, data: dict[str, Any]) -> None:
        call_id = str(data.get("call_id", ""))
        if call_id in self._hidden:
            self._hidden.discard(call_id)
            return
        tool, summary, line = self._calls.pop(call_id, ("tool", "Tool finished", "Tool finished"))
        output = str(data.get("output", "")).strip()
        if self.workdir is not None:  # show workspace paths relative, as the summaries do
            for folder in {str(self.workdir.resolve()), str(self.workdir)}:
                output = output.replace(f"{folder}/", "").replace(folder, ".")
        self.log.append(
            "tool",
            call_id=call_id,
            name=tool,
            summary=summary,
            line=line,
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
