"""The serve token survives a restart: saved owner-only in the runs folder, rotated on request."""

from __future__ import annotations

import stat
from pathlib import Path

from chipin_backend.api.session_token import OWNER_ONLY, TOKEN_FILE, load_or_create_token, token_path
from chipin_backend.cli import _parser


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_first_start_saves_an_owner_only_token(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    token = load_or_create_token(runs)
    path = runs / TOKEN_FILE
    assert path == token_path(runs)
    assert path.read_text(encoding="utf-8").strip() == token
    assert _mode(path) == OWNER_ONLY
    assert not list(runs.glob("*.tmp"))


def test_a_restart_reuses_the_saved_token(tmp_path: Path) -> None:
    first = load_or_create_token(tmp_path)
    assert load_or_create_token(tmp_path) == first


def test_new_token_rotates_and_saves(tmp_path: Path) -> None:
    first = load_or_create_token(tmp_path)
    rotated = load_or_create_token(tmp_path, rotate=True)
    assert rotated != first
    assert load_or_create_token(tmp_path) == rotated
    assert _mode(token_path(tmp_path)) == OWNER_ONLY


def test_a_malformed_file_is_replaced(tmp_path: Path) -> None:
    path = token_path(tmp_path)
    path.write_text("not a token!\n", encoding="utf-8")
    token = load_or_create_token(tmp_path)
    assert token != "not a token!"
    assert path.read_text(encoding="utf-8").strip() == token


def test_loose_permissions_are_tightened(tmp_path: Path) -> None:
    first = load_or_create_token(tmp_path)
    path = token_path(tmp_path)
    path.chmod(0o644)
    assert load_or_create_token(tmp_path) == first
    assert _mode(path) == OWNER_ONLY


def test_the_token_is_never_logged(tmp_path: Path, capfd) -> None:  # type: ignore[no-untyped-def]
    from loguru import logger

    lines: list[str] = []
    sink = logger.add(lines.append, level="DEBUG")
    try:
        first = load_or_create_token(tmp_path)
        load_or_create_token(tmp_path)
        rotated = load_or_create_token(tmp_path, rotate=True)
    finally:
        logger.remove(sink)
    text = "".join(lines) + "".join(capfd.readouterr())
    assert lines and first not in text and rotated not in text


def test_serve_has_new_token_flag() -> None:
    assert _parser().parse_args(["serve"]).new_token is False
    assert _parser().parse_args(["serve", "--new-token"]).new_token is True
