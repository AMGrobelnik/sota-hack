"""Shared fixtures. Default tests never reach a paid service: the keys are
removed from the environment, and live tests carry the ``live`` marker."""

from __future__ import annotations

from pathlib import Path

import pytest

from chipin_backend.config import BackendConfig, load_config

PAID_KEYS = (
    "OPENROUTER_API_KEY",
    "RUNPOD_API_KEY",
    "ANTHROPIC_API_KEY",
    "TINKER_API_KEY",
    "CALLOSUM_API_KEY",
)


@pytest.fixture(autouse=True)
def _no_paid_keys(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip paid-service keys from every non-live test."""
    if request.node.get_closest_marker("live") is None:
        for name in PAID_KEYS:
            monkeypatch.delenv(name, raising=False)


@pytest.fixture
def config(tmp_path: Path) -> BackendConfig:
    """The committed default config with runs and logs under ``tmp_path``."""
    loaded = load_config(env_file=tmp_path / "absent.env")
    return loaded.model_copy(update={"runs_dir": tmp_path / "runs", "log_dir": tmp_path / "logs"})
