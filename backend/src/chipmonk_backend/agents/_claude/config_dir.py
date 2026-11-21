"""Where the ``claude`` CLI keeps its login, its per-folder state and its transcripts.

Adapted from AI Inventor's ``claude_oauth/config_dir.py`` and
``_repl_driver/_pretrust.py``.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from loguru import logger

_SLUG_SANITIZE_RE = re.compile(r"[^a-zA-Z0-9]")
#: Past this length the CLI truncates the folder name and appends a hash.
_SLUG_MAX_LEN = 200
_BASE36_DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz"

#: One-time screens the CLI would otherwise render on a fresh config dir.
#: Seeded only into a dedicated agent config dir, never a person's own login.
_ONBOARDING_FLAGS = (
    "hasCompletedOnboarding",
    "hasSeenAutoDefaultNudge",
    "hasSeenAutoDefaultNotice",
    "hasSeenAutoModeEntryWarning",
    "hasSeenAutoModeOutsideReadPrompt",
    "hasResetAutoModeOptInForDefaultOffer",
)


def resolve_config_dir(configured: Path | None) -> Path:
    """The CLI's config dir: ``configured``, else ``$CLAUDE_CONFIG_DIR``, else ``~/.claude``."""
    if configured is not None:
        return configured.expanduser()
    override = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(override) if override else Path.home() / ".claude"


def claude_json_path(configured: Path | None) -> Path:
    """The CLI's ``.claude.json``: inside an explicit config dir, else ``~/.claude.json``.

    With no override the CLI keeps this file beside ``~/.claude``, not in it.
    """
    if configured is not None:
        return configured.expanduser() / ".claude.json"
    override = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(override) / ".claude.json" if override else Path.home() / ".claude.json"


def _js_string_hash_base36(text: str) -> str:
    """The CLI's ``Math.abs(hash(s)).toString(36)`` (32-bit ``h * 31 + c``)."""
    h = 0
    for ch in text:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    if h >= 0x80000000:
        h -= 0x100000000
    n = abs(h)
    digits = ""
    while True:
        n, r = divmod(n, 36)
        digits = _BASE36_DIGITS[r] + digits
        if n == 0:
            return digits


def project_slug(cwd: str | Path) -> str:
    """The transcript folder name the CLI uses for ``cwd`` (every non-alphanumeric is ``-``)."""
    name = str(cwd)
    sanitized = _SLUG_SANITIZE_RE.sub("-", name)
    if len(sanitized) <= _SLUG_MAX_LEN:
        return sanitized
    return f"{sanitized[:_SLUG_MAX_LEN]}-{_js_string_hash_base36(name)}"


def _locked_json_merge(path: Path, mutate: Callable[[dict[str, Any]], bool]) -> None:
    """Edit a JSON object file in place under an exclusive ``flock``.

    ``mutate`` edits the parsed object and returns whether it changed; the
    file is rewritten only then. Best-effort: an unreadable or malformed file
    is logged and left alone, and the dialog pilot is the fallback.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    except OSError as err:
        logger.warning("claude_cli: cannot open {} to pre-trust: {}", path, err)
        return
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        with os.fdopen(fd, "r+", closefd=False) as f:
            raw = f.read()
            try:
                data = json.loads(raw) if raw.strip() else {}
            except json.JSONDecodeError as err:
                logger.warning("claude_cli: malformed {}, not pre-trusting: {}", path, err)
                return
            if not isinstance(data, dict) or not mutate(data):
                return
            f.seek(0)
            f.truncate()
            f.write(json.dumps(data, indent=2))
    except OSError as err:
        logger.warning("claude_cli: cannot write {} to pre-trust: {}", path, err)
    finally:
        os.close(fd)


def pretrust(cwd: Path, configured: Path | None) -> None:
    """Mark ``cwd`` trusted in the CLI's ``.claude.json`` so no trust dialog eats the prompt.

    Trust is per exact path. For a dedicated config dir (``configured`` set)
    the one-time onboarding and auto-mode screens are marked seen as well; a
    person's own login is left otherwise untouched, and the dialog pilot
    answers anything it still shows.
    """
    cwd_str = str(cwd.resolve())

    def seed(data: dict[str, Any]) -> bool:
        changed = False
        if configured is not None:
            for flag in _ONBOARDING_FLAGS:
                if data.get(flag) is not True:
                    data[flag] = True
                    changed = True
        projects = data.setdefault("projects", {})
        if not isinstance(projects, dict):
            return changed
        entry = projects.setdefault(cwd_str, {})
        if isinstance(entry, dict) and entry.get("hasTrustDialogAccepted") is not True:
            entry["hasTrustDialogAccepted"] = True
            changed = True
        return changed

    _locked_json_merge(claude_json_path(configured), seed)


__all__ = ["claude_json_path", "pretrust", "project_slug", "resolve_config_dir"]
