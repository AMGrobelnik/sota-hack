"""User messages typed into a running ``claude`` turn, and proof of when each reached the agent.

The interactive CLI takes input while it works: a message typed and
submitted mid-turn is queued, not an interrupt, and the CLI hands it to the
model as soon as the running tool calls finish, inside the same turn; one
still queued when the turn ends goes out by itself as the next turn, in the
order typed (Claude Code docs, "Interactive mode", "Queue messages while
Claude works"). Nothing is killed or restarted.

The transcript shows each step (observed on CLI 2.1.330):

* ``{"type": "queue-operation", "operation": "enqueue", "content": <text>}``
  when the CLI queued it;
* mid-turn: ``queue-operation`` ``remove`` with ``"reason":
  "absorbed_mid_turn"`` and an ``attachment`` of type ``queued_command``
  whose ``prompt`` is the text: the model reads it with the next tool result;
* at the turn's end: ``queue-operation`` ``dequeue``, then an ordinary user
  record carrying the text, which opens a new turn.

A message counts as delivered at the first record that hands its text to the
model (the ``remove``/``queued_command`` pair or the user record).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from chipin_backend.agents._claude.delivery import (
    bracketed_paste,
    collapsed,
    expand_pasted_content,
    typeable,
    typed_text,
)

#: Characters of a message (collapsed) that identify it in the transcript.
KEY_CHARS = 80
#: Without an ``enqueue`` or a delivery this long after typing, Enter is pressed again;
#: after twice this, the message is typed once more.
ENQUEUE_WAIT_S = 10.0


@dataclass
class _Typed:
    text: str
    key: str
    typed_at: float = field(default_factory=time.monotonic)
    enqueued: bool = False
    nudges: int = 0


def _key(text: str) -> str:
    return collapsed(typeable(text))[:KEY_CHARS]


def _handed_over(record: dict[str, Any]) -> str | None:
    """The text a record hands to the model as a user message, if it does."""
    if record.get("isSidechain"):
        return None
    if record.get("type") == "queue-operation" and record.get("operation") == "remove":
        return str(record.get("content") or "") or None
    attachment = record.get("attachment")
    if record.get("type") == "attachment" and isinstance(attachment, dict):
        if attachment.get("type") == "queued_command":
            return str(attachment.get("prompt") or "") or None
        return None
    return typed_text(record)


class TypedMessages:
    """Types waiting messages into the CLI and reports each one's delivery, in order."""

    def __init__(self, inbox: Callable[[], list[str]], on_delivered: Callable[[str], None]) -> None:
        self._inbox = inbox
        self._on_delivered = on_delivered
        self.outstanding: list[_Typed] = []

    def __bool__(self) -> bool:
        return bool(self.outstanding)

    def type_waiting(self, write: Callable[[str], None]) -> None:
        """Type every message waiting in the inbox, each as one submitted paste."""
        for text in self._inbox():
            if not text.strip():
                continue
            self._type(text, write)
            self.outstanding.append(_Typed(text, _key(text)))

    @staticmethod
    def _type(text: str, write: Callable[[str], None]) -> None:
        write(bracketed_paste(typeable(text)))
        time.sleep(0.4)
        write("\r")

    def nudge(self, write: Callable[[str], None]) -> None:
        """Press Enter again, then type again, for a message the CLI never took."""
        now = time.monotonic()
        for item in self.outstanding:
            if item.enqueued or now - item.typed_at < ENQUEUE_WAIT_S * (item.nudges + 1):
                continue
            if item.nudges == 0:
                write("\r")
            elif item.nudges == 1:
                self._type(item.text, write)
            item.nudges += 1

    def observe(self, records: list[dict[str, Any]]) -> None:
        """Mark messages queued and delivered from new transcript records."""
        for record in records:
            if record.get("type") == "queue-operation" and record.get("operation") == "enqueue":
                content = collapsed(str(record.get("content") or ""))
                for item in self.outstanding:
                    if item.key in content:
                        item.enqueued = True
                continue
            text = _handed_over(record)
            if text is None or not self.outstanding:
                continue
            if self.outstanding[0].key in collapsed(expand_pasted_content(text)):
                self._on_delivered(self.outstanding.pop(0).text)

    def take(self) -> list[str]:
        """The messages typed but not delivered, oldest first; forgets them (the CLI was killed)."""
        left = [item.text for item in self.outstanding]
        self.outstanding.clear()
        return left


__all__ = ["ENQUEUE_WAIT_S", "TypedMessages"]
