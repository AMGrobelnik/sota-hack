"""One scrubber for everything that leaves the backend: the API, the export and model requests.

Home folder paths become ``~`` (URL-encoded ones such as ``%2FUsers%2F...``
too), anything that looks like a key or token and every e-mail address
becomes ``[removed]``, and this machine's host and user names (read at run
time, matched in any case and next to an underscore or digit, never inside a
longer word) become ``[host]`` and ``[user]``. The export (``export.py``), every API
route that serves text for display, and every request to an outside model
(the summary model and Chippy's model) pass through the same rules, so what
the page shows and what a model reads never holds a private detail. Files on
disk (``events.jsonl`` and the rest) stay as they were written.
"""

from __future__ import annotations

import getpass
import re
import socket
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REMOVED = "[removed]"

#: Key and token shapes of the services a run can touch, and generic ``name=value`` secrets.
KEY_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p)
    for p in (
        r"sk-(?:or-v1-|ant-|proj-)?[A-Za-z0-9_\-]{16,}",
        r"\bgh[pousr]_[A-Za-z0-9]{20,}",
        r"\bgithub_pat_[A-Za-z0-9_]{20,}",
        r"\bAKIA[0-9A-Z]{16}\b",
        r"\bhf_[A-Za-z0-9]{20,}",
        r"\bxox[abprs]-[A-Za-z0-9-]{10,}",
        r"\brpa_[A-Za-z0-9]{20,}",
        r"\bAIza[0-9A-Za-z_\-]{30,}",
        r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}",
        r"(?i)\bbearer\s+[A-Za-z0-9._\-]{16,}",
    )
)
SECRET_ASSIGN = re.compile(
    r"(?i)\b((?:[a-z0-9]+_)*(?:token|api_?key|apikey|secret|password|passwd))(\"?'?\s*[:=]\s*[\"']?)([A-Za-z0-9._\-/+]{8,})"
)
EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}")
HOME_GENERIC = re.compile(r"(?:/Users|/home)/[^/\s\"'`:;,)]+", re.IGNORECASE)
#: A home path inside a URL or a query string: ``%2FUsers%2Fname`` (hex digits in any case).
HOME_ENCODED = re.compile(
    r"%2F(?:Users|home)%2F(?:(?!%2F)[^/\s\"'`:;,)&?#%]|%(?!2F)[0-9A-F]{2})+", re.IGNORECASE
)


def _name_pattern(name: str) -> re.Pattern[str]:
    """``name`` in any case, where it is not part of a longer word or number.

    An underscore, a digit next to a letter or any punctuation ends the name
    (``name_tools``, ``name2``, ``Name.local``); a letter next to a letter, or a
    digit next to a digit, makes a longer word (``names``, ``rename``) that is left.
    """

    def guard(char: str) -> str:
        if char.isalpha():
            return "A-Za-z"
        return "0-9" if char.isdigit() else ""

    before, after = guard(name[0]), guard(name[-1])
    head = f"(?<![{before}])" if before else ""
    tail = f"(?![{after}])" if after else ""
    return re.compile(f"{head}{re.escape(name)}{tail}", re.IGNORECASE)


def _host_names() -> tuple[str, ...]:
    try:
        full = socket.gethostname()
    except OSError:
        return ()
    names = {full, full.split(".")[0]}
    return tuple(sorted((n for n in names if len(n) >= 4), key=len, reverse=True))


def _user_name() -> str:
    try:
        name = getpass.getuser()
    except (OSError, KeyError):
        return ""
    return name if len(name) >= 4 else ""


@dataclass
class Scrubber:
    """Replaces home paths, keys, e-mail addresses, host and user names in strings; counts each."""

    home: str = field(default_factory=lambda: str(Path.home()))
    host_names: tuple[str, ...] = field(default_factory=_host_names)
    user: str = field(default_factory=_user_name)
    counts: dict[str, int] = field(
        default_factory=lambda: {"home_paths": 0, "keys": 0, "emails": 0, "host": 0, "user": 0}
    )

    def __post_init__(self) -> None:
        self._hosts = [_name_pattern(h) for h in self.host_names if h]
        self._user = _name_pattern(self.user) if self.user else None

    def _sub(
        self, pattern: re.Pattern[str], repl: str | Callable[[re.Match[str]], str], text: str, key: str
    ) -> str:
        out, n = pattern.subn(repl, text)
        self.counts[key] += n
        return out

    def text(self, value: str) -> str:
        """``value`` with every private detail replaced."""
        out = value
        if self.home and self.home != "/":
            n = out.count(self.home)
            if n:
                out = out.replace(self.home, "~")
                self.counts["home_paths"] += n
        out = self._sub(HOME_GENERIC, "~", out, "home_paths")
        out = self._sub(HOME_ENCODED, "~", out, "home_paths")
        for pattern in KEY_PATTERNS:
            out = self._sub(pattern, REMOVED, out, "keys")
        out = self._sub(SECRET_ASSIGN, lambda m: f"{m.group(1)}{m.group(2)}{REMOVED}", out, "keys")
        out = self._sub(EMAIL, REMOVED, out, "emails")
        for host in self._hosts:
            out = self._sub(host, "[host]", out, "host")
        if self._user is not None:
            out = self._sub(self._user, "[user]", out, "user")
        return out

    def value(self, data: Any) -> Any:
        """``data`` (any JSON value) with every string scrubbed, keys of objects included."""
        if isinstance(data, str):
            return self.text(data)
        if isinstance(data, list | tuple):
            return [self.value(v) for v in data]
        if isinstance(data, dict):
            return {self.text(str(k)): self.value(v) for k, v in data.items()}
        return data


_default: Scrubber | None = None


def default_scrubber() -> Scrubber:
    """The process's scrubber (this machine's home, host and user names), made once."""
    global _default
    if _default is None:
        _default = Scrubber()
    return _default


def scrub_text(text: str) -> str:
    """``text`` with every private detail replaced (see :class:`Scrubber`)."""
    return default_scrubber().text(text)


def scrub_value(data: Any) -> Any:
    """``data`` (any JSON value) with every string scrubbed."""
    return default_scrubber().value(data)


__all__ = [
    "EMAIL",
    "HOME_ENCODED",
    "HOME_GENERIC",
    "KEY_PATTERNS",
    "REMOVED",
    "SECRET_ASSIGN",
    "Scrubber",
    "default_scrubber",
    "scrub_text",
    "scrub_value",
]
