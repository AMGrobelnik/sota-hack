"""Pick the runner for a run mode."""

from __future__ import annotations

from chipin_backend.compute.base import Runner
from chipin_backend.compute.flex import FlexRunner
from chipin_backend.compute.local import LocalRunner
from chipin_backend.config import BackendConfig, RunMode


def runner_for(config: BackendConfig, run_mode: RunMode | None = None) -> Runner:
    """A new runner for ``run_mode`` (default ``config.compute.run_mode``)."""
    mode = run_mode or config.compute.run_mode
    if mode == "local":
        return LocalRunner(config)
    if mode == "flex":
        return FlexRunner(config)
    if mode == "on_demand":
        from chipin_backend.compute.runpod.runner import RunPodRunner

        return RunPodRunner(config)
    raise ValueError(f"unknown run mode {mode!r}")


__all__ = ["runner_for"]
