"""The serve token survives a restart: saved owner-only in the runs folder, rotated on request."""

from __future__ import annotations

import stat
from pathlib import Path

import pytest

from chipin_backend.api.session_token import (
    OWNER_ONLY,
    TOKEN_ENV,
    TOKEN_FILE,
    load_or_create_token,
    token_path,
)
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


def test_a_fixed_token_wins_and_leaves_the_file_alone(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    saved = load_or_create_token(tmp_path)
    monkeypatch.setenv(TOKEN_ENV, "public-demo-token-1")
    assert load_or_create_token(tmp_path) == "public-demo-token-1"
    assert load_or_create_token(tmp_path, rotate=True) == "public-demo-token-1"
    assert token_path(tmp_path).read_text(encoding="utf-8").strip() == saved
    monkeypatch.delenv(TOKEN_ENV)
    assert load_or_create_token(tmp_path) == saved


def test_a_malformed_fixed_token_is_refused(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    for bad in ("short", "has spaces in the middle", "x" * 129):
        monkeypatch.setenv(TOKEN_ENV, bad)
        with pytest.raises(ValueError, match=TOKEN_ENV):
            load_or_create_token(tmp_path)
    assert not token_path(tmp_path).exists()


def test_serve_has_new_token_flag() -> None:
    assert _parser().parse_args(["serve"]).new_token is False
    assert _parser().parse_args(["serve", "--new-token"]).new_token is True
