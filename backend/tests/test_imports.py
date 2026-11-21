"""Every module imports, without the optional OpenHands extra or any key."""

from __future__ import annotations

import importlib
import pkgutil

import pytest

import chipmonk_backend

MODULES = sorted(info.name for info in pkgutil.walk_packages(chipmonk_backend.__path__, "chipmonk_backend."))


def test_found_every_subpackage() -> None:
    for name in ("agents", "compute", "compute.runpod", "llm"):
        assert f"chipmonk_backend.{name}" in MODULES


@pytest.mark.parametrize("module", MODULES)
def test_module_imports(module: str) -> None:
    importlib.import_module(module)


@pytest.mark.parametrize("name", ["claude_cli", "openrouter", "stub"])
def test_every_registered_backend_resolves(name: str) -> None:
    from chipmonk_backend.agents.base import AgentBackend, backend_class

    assert issubclass(backend_class(name), AgentBackend)
