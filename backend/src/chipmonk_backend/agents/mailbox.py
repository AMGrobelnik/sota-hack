"""Messages injected into a running agent, queued until its next turn boundary.

Adapted from AI Inventor: a thread-safe queue
whose ``close`` and ``try_put`` are mutually exclusive, so a message can never
slip in after the agent began tearing down (it would be silently lost).
"""

from __future__ import annotations

import threading
from collections import deque


class InjectMailbox:
    """Thread-safe FIFO of follow-up prompts for one agent run."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: deque[str] = deque()
        self._closed = True

    def open(self) -> None:
        """Accept messages (called when a run starts); drops any left from a prior run."""
        with self._lock:
            self._items.clear()
            self._closed = False

    def close(self) -> list[str]:
        """Stop accepting messages; returns the ones never delivered."""
        with self._lock:
            self._closed = True
            left = list(self._items)
            self._items.clear()
            return left

    def try_put(self, message: str) -> bool:
        """Queue ``message``; ``False`` when the mailbox is closed."""
        with self._lock:
            if self._closed:
                return False
            self._items.append(message)
            return True

    def pending(self) -> bool:
        """Whether a message is waiting."""
        with self._lock:
            return bool(self._items)

    def drain(self) -> list[str]:
        """Every waiting message, oldest first, removed from the queue."""
        with self._lock:
            items = list(self._items)
            self._items.clear()
            return items


__all__ = ["InjectMailbox"]
