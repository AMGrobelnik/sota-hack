"""Settings of the local API server, read from ``api.yaml`` next to this module."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from chipmonk_backend.config import Effort

API_CONFIG_PATH = Path(__file__).with_name("api.yaml")

Preset = Literal["lite", "pro", "max", "ultra"]


class ApiConfig(BaseModel):
    """Server knobs; the contract itself (routes, headers, origins) is code."""

    model_config = ConfigDict(extra="forbid")

    port: int = 8797
    keepalive_s: float = 15.0
    progress_poll_s: float = 0.5
    run_timeout_s: int = 14400
    stub_step_s: float = 0.4
    presets: dict[Preset, Effort] = Field(
        default_factory=lambda: {"lite": "low", "pro": "high", "max": "xhigh", "ultra": "max"}
    )


def load_api_config(path: Path = API_CONFIG_PATH) -> ApiConfig:
    """Load and validate ``api.yaml``; ``ValueError`` on invalid YAML."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path} must hold a mapping at the top level")
    return ApiConfig.model_validate(data)


__all__ = ["API_CONFIG_PATH", "ApiConfig", "Preset", "load_api_config"]
