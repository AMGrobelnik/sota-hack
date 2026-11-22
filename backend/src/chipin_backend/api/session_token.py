"""The session token that ``chipin-backend serve`` keeps across restarts.

A dashboard page holds the token from the link the CLI prints; if every
restart issued a new one, an open page would get 401 and could not resume the
run it was showing. So the token lives in ``TOKEN_FILE`` inside the server's
runs folder (which is never committed), readable by the owner only, and the
next start reuses it. ``serve --new-token`` rotates it.

``CHIPIN_SESSION_TOKEN`` in the environment fixes the token instead (a public
demo page ships it): the saved file is then neither read nor written.
"""

from __future__ import annotations

import os
import re
import secrets
import stat
from pathlib import Path

from loguru import logger

TOKEN_FILE = ".session-token"
OWNER_ONLY = 0o600
_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{24,128}$")
TOKEN_ENV = "CHIPIN_SESSION_TOKEN"
_FIXED_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{16,128}$")


def fixed_token() -> str | None:
    """The token set in ``TOKEN_ENV``, or None when unset; ValueError when malformed."""
    value = os.environ.get(TOKEN_ENV, "").strip()
    if not value:
        return None
    if not _FIXED_TOKEN_RE.fullmatch(value):
        raise ValueError(f"{TOKEN_ENV} must be 16 to 128 characters of A-Z, a-z, 0-9, _ or -")
    return value


def new_token() -> str:
    """A fresh session token."""
    return secrets.token_urlsafe(24)


def token_path(runs_dir: Path) -> Path:
    """Where the token for the server whose runs live in ``runs_dir`` is kept."""
    return runs_dir / TOKEN_FILE


def _read(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError) as exc:
        logger.warning("cannot read the saved session token ({}); issuing a new one", type(exc).__name__)
        return None
    if not _TOKEN_RE.fullmatch(text):
        logger.warning("the saved session token is malformed; issuing a new one")
        return None
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode != OWNER_ONLY:
        path.chmod(OWNER_ONLY)
        logger.info("tightened the session token file to owner-only (was {:o})", mode)
    return text


def _write(path: Path, token: str) -> None:
    """Write ``token`` to ``path`` atomically, the file owner-only from its creation."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, OWNER_ONLY)
    try:
        os.fchmod(fd, OWNER_ONLY)
        os.write(fd, f"{token}\n".encode())
    finally:
        os.close(fd)
    os.replace(tmp, path)


def load_or_create_token(runs_dir: Path, *, rotate: bool = False) -> str:
    """The fixed token, else the saved one for ``runs_dir``, else a new one saved there.

    ``rotate`` always issues a new saved token, unless a fixed token is set.
    """
    fixed = fixed_token()
    if fixed is not None:
        logger.info("using the fixed session token from {}", TOKEN_ENV)
        return fixed
    path = token_path(runs_dir)
    if not rotate:
        saved = _read(path)
        if saved is not None:
            logger.info("reusing the saved session token")
            return saved
    token = new_token()
    _write(path, token)
    logger.info("issued a new session token ({})", "rotated" if rotate else "none saved")
    return token


__all__ = [
    "OWNER_ONLY",
    "TOKEN_ENV",
    "TOKEN_FILE",
    "fixed_token",
    "load_or_create_token",
    "new_token",
    "token_path",
]
