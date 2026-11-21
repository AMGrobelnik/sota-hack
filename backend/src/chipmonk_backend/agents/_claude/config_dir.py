"""Where the ``claude`` CLI keeps its login, its per-folder state and its transcripts,
and the folder trust a run grants itself for its own lifetime. Adapted from AI Inventor.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loguru import logger

#: ``TrustGrant.previous_flag`` when :func:`pretrust` did not touch the flag.
_UNSET: Any = object()
#: ``TrustGrant.previous_flag`` when the entry had no trust flag at all.
_ABSENT: Any = object()

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


def _atomic_write(path: Path, text: str) -> None:
    """Replace ``path`` with ``text`` atomically: a temporary file in the same
    folder, flushed to disk, then renamed over it. The file's mode is kept
    (``0o600`` for a new file), so a crash never leaves it empty or half written."""
    try:
        mode = path.stat().st_mode & 0o777
    except FileNotFoundError:
        mode = 0o600
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        tmp.chmod(mode)
        tmp.replace(path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def _locked_json_merge(path: Path, mutate: Callable[[dict[str, Any]], bool]) -> None:
    """Edit a JSON object file under an exclusive ``flock``, replacing it atomically.

    ``mutate`` edits the parsed object and returns whether it changed; the
    file is rewritten only then, through :func:`_atomic_write` (never truncated
    in place). The lock is held on a sibling ``.lock`` file, because the rename
    swaps the JSON file's inode. Best-effort: an unreadable or malformed file
    is logged and left alone, and the dialog pilot is the fallback.
    """
    path = path.resolve()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        lock_fd = os.open(path.with_name(f"{path.name}.chipmonk.lock"), os.O_RDWR | os.O_CREAT, 0o600)
    except OSError as err:
        logger.warning("claude_cli: cannot lock {} to edit trust: {}", path, err)
        return
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        try:
            raw = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            raw = ""
        try:
            data = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError as err:
            logger.warning("claude_cli: malformed {}, trust left unchanged: {}", path, err)
            return
        if not isinstance(data, dict) or not mutate(data):
            return
        _atomic_write(path, json.dumps(data, indent=2))
    except OSError as err:
        logger.warning("claude_cli: cannot write {} to edit trust: {}", path, err)
    finally:
        os.close(lock_fd)


@dataclass
class TrustGrant:
    """What :func:`pretrust` changed for one folder, so :func:`revoke_trust` can undo it."""

    cwd: str
    path: Path
    created_entry: bool = False  # the folder had no ``projects`` entry before
    previous_flag: Any = _UNSET  # the entry's ``hasTrustDialogAccepted`` before


def pretrust(cwd: Path, configured: Path | None) -> TrustGrant:
    """Mark ``cwd`` trusted in the CLI's ``.claude.json`` so no trust dialog eats the prompt.

    Trust is per exact path. For a dedicated config dir (``configured`` set)
    the one-time onboarding and auto-mode screens are marked seen as well; a
    person's own login is left otherwise untouched, and the dialog pilot
    answers anything it still shows. Returns the grant to pass to
    :func:`revoke_trust` when the run ends.
    """
    grant = TrustGrant(cwd=str(cwd.resolve()), path=claude_json_path(configured))

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
        if grant.cwd not in projects:
            grant.created_entry = True
        entry = projects.setdefault(grant.cwd, {})
        if isinstance(entry, dict) and entry.get("hasTrustDialogAccepted") is not True:
            if not grant.created_entry:
                grant.previous_flag = entry.get("hasTrustDialogAccepted", _ABSENT)
            entry["hasTrustDialogAccepted"] = True
            changed = True
        return changed

    _locked_json_merge(grant.path, seed)
    return grant


def revoke_trust(grant: TrustGrant) -> None:
    """Undo :func:`pretrust`: drop the folder's entry if the grant created it, else
    put its trust flag back as it was. Leaves every other entry alone."""

    def undo(data: dict[str, Any]) -> bool:
        projects = data.get("projects")
        if not isinstance(projects, dict) or grant.cwd not in projects:
            return False
        if grant.created_entry:
            del projects[grant.cwd]
            return True
        entry = projects[grant.cwd]
        if grant.previous_flag is _UNSET or not isinstance(entry, dict):
            return False
        if grant.previous_flag is _ABSENT:
            entry.pop("hasTrustDialogAccepted", None)
        else:
            entry["hasTrustDialogAccepted"] = grant.previous_flag
        return True

    _locked_json_merge(grant.path, undo)


__all__ = [
    "TrustGrant",
    "claude_json_path",
    "pretrust",
    "project_slug",
    "resolve_config_dir",
    "revoke_trust",
]
