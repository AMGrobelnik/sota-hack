"""Background work a session still has running, read from its transcript records.

Adapted from AI Inventor. Claude Code lets a
turn end while work it started still runs (a ``run_in_background`` Bash, a
Monitor, an async Agent) and starts the next turn ITSELF when that work
reports back through a ``<task-notification>`` user turn. A turn that ends
with such work open is the agent waiting, not the agent being done.

Only the main session's records count; a delegated agent's own background
work is reported inside its sidechain.
"""

from __future__ import annotations

import re
from typing import Any

_NOTIFICATION_RE = re.compile(r"<task-notification>(.*?)</task-notification>", re.DOTALL)
_TASK_ID_RE = re.compile(r"<task-id>\s*([A-Za-z0-9_-]+)\s*</task-id>")
_STATUS_RE = re.compile(r"<status>\s*([A-Za-z_-]+)\s*</status>")


def _text_of(content: Any) -> str:
    """The prose of a user record's content, a string or text blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
    return ""


class BackgroundWork:
    """What the main session has running that the CLI will report back on."""

    def __init__(self) -> None:
        self._open: dict[str, str] = {}  # task id -> tool name
        self._tool_names: dict[str, str] = {}  # tool_use id -> tool name

    def observe(self, record: dict[str, Any]) -> None:
        """Open or close whatever background work ``record`` starts or reports."""
        if record.get("isSidechain"):
            return
        kind = record.get("type")
        content = (record.get("message") or {}).get("content")
        if kind == "assistant" and isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("id"):
                    self._tool_names[block["id"]] = str(block.get("name") or "")
        elif kind == "user":
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        tool = self._tool_names.get(block.get("tool_use_id") or "", "")
                        self._note_result(tool, record.get("toolUseResult"))
            self._note_notifications(_text_of(content))
        elif kind == "attachment":
            attachment = record.get("attachment") or {}
            if attachment.get("type") == "queued_command":
                self._note_notifications(_text_of(attachment.get("prompt")))

    def _note_result(self, tool: str, result: Any) -> None:
        """Track the job a tool result opened, or the one it stopped."""
        if not isinstance(result, dict):
            return
        if result.get("status") == "async_launched":
            child = result.get("agentId") or result.get("taskId")
            if child:
                self._open[str(child)] = tool or "Agent"
        if result.get("backgroundTaskId"):
            self._open[str(result["backgroundTaskId"])] = tool or "Bash"
        if tool == "Monitor" and result.get("taskId"):
            self._open[str(result["taskId"])] = tool
        stopped = result.get("task_id") or result.get("shell_id")
        if tool in ("TaskStop", "KillShell") and stopped:
            self._open.pop(str(stopped), None)

    def _note_notifications(self, text: str) -> None:
        """Close each task a terminal notification (one with a ``<status>``) reports."""
        for block in _NOTIFICATION_RE.findall(text):
            task_id = _TASK_ID_RE.search(block)
            if task_id and _STATUS_RE.search(block):
                self._open.pop(task_id.group(1), None)

    def holds_turn_open(self) -> bool:
        """Whether a turn ending now is the agent waiting on its own work."""
        return bool(self._open)

    def describe(self) -> str:
        """The open work for a log line, e.g. ``Bash b3k1, Agent a9``."""
        return ", ".join(f"{tool} {tid}" for tid, tool in self._open.items()) or "nothing"

    def clear(self) -> None:
        """Forget everything open: the CLI that ran it was killed."""
        self._open.clear()


__all__ = ["BackgroundWork"]
