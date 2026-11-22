"""Settings of the local API server, read from ``api.yaml`` next to this module."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from chipin_backend.api.helper import HelperConfig
from chipin_backend.api.questions import QuestionsConfig
from chipin_backend.api.transcribe import TranscribeConfig
from chipin_backend.config import Effort, deep_merge

API_CONFIG_PATH = Path(__file__).with_name("api.yaml")

Preset = Literal["lite", "pro", "max", "ultra"]
#: The dashboard's agent harness names (``claude`` is the ``claude_cli`` backend).
ApiAgent = Literal["claude", "stub", "openrouter"]


class SubagentConfig(BaseModel):
    """What each subagent runs on when the request does not say."""

    model_config = ConfigDict(extra="forbid")

    #: The harness; ``None`` = the orchestrator's.
    agent: ApiAgent | None = None
    #: The automatic model of a subagent on the ``claude`` harness (the
    #: orchestrator's automatic model is ``agents.claude_cli.model``).
    model: str | None = "claude-sonnet-5-5"
    #: The automatic model of a subagent on the ``openrouter`` harness;
    #: ``None`` = ``agents.openrouter.model``.
    openrouter_model: str | None = None
    provider: str | None = None  # openrouter harness only; None = openrouter
    effort: Effort | None = None  # None = the orchestrator's
    #: Hard wall clock per subagent: one value for every run, or ``None`` for the
    #: preset's entry in ``timeouts`` (``default_timeout_s`` without a preset).
    #: A subagent still running then is stopped with its process tree, and the
    #: orchestrator gets its partial result marked ``timed out``.
    timeout_s: int | None = Field(default=None, ge=1)
    timeouts: dict[Preset, int] = Field(
        default_factory=lambda: {"lite": 600, "pro": 600, "max": 600, "ultra": 600}
    )
    default_timeout_s: int = Field(default=600, ge=1)


class FanoutConfig(BaseModel):
    """Fan-out: an orchestrator agent runs one batch of parallel subagents per stage.

    The batch size (``width``) is the run-size control: how many subagents,
    each trying a different strategy, run at once in each of the stages in
    ``BATCH_STAGES``. ``None`` takes the preset's entry in ``widths``
    (``default_width`` without a preset). Every ``None`` limit below is
    derived from the batch size; see :func:`chipin_backend.api.fanout.plan_fanout`.
    """

    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    width: int | None = Field(default=None, ge=1)
    #: Subagents per stage batch: the preset's total spread over the five batch stages.
    widths: dict[Preset, int] = Field(default_factory=lambda: {"lite": 1, "pro": 3, "max": 10, "ultra": 20})
    default_width: int = Field(default=3, ge=1)
    #: Subagents a run of the preset may start in all, retries included (the run
    #: size: Lite 5, Pro 15, Max 50). A preset not listed gets five batches plus
    #: ``spare_starts``; so does a request that names its own ``width``.
    totals: dict[Preset, int] = Field(default_factory=lambda: {"lite": 5, "pro": 15, "max": 50})
    #: Subagents running at once; ``None`` = the batch size (a whole batch at once).
    max_parallel: int | None = Field(default=None, ge=1)
    #: Subagents per run for every run; ``None`` = the preset's ``totals`` entry,
    #: else five batches plus ``spare_starts``.
    max_total: int | None = Field(default=None, ge=1)
    #: Starts beyond the five batches, for retries; ``None`` = a fifth of the batch, at least 2.
    spare_starts: int | None = Field(default=None, ge=0)
    #: API-model budget per allowed start, for ``max_usd``.
    usd_per_subagent: float = Field(default=0.05, ge=0)
    #: API-model spend of a run's subagents; ``None`` = ``usd_per_subagent`` x ``max_total``.
    max_usd: float | None = Field(default=None, ge=0)
    wait_timeout_s: int = Field(default=100, ge=1)
    subagent: SubagentConfig = Field(default_factory=SubagentConfig)


class ApiConfig(BaseModel):
    """Server knobs; the contract itself (routes, headers, origins) is code."""

    model_config = ConfigDict(extra="forbid")

    port: int = 8797
    keepalive_s: float = 15.0
    progress_poll_s: float = 0.5
    run_timeout_s: int = 14400
    stub_step_s: float = 0.4
    max_files: int = 200
    file_max_bytes: int = 524288
    presets: dict[Preset, Effort] = Field(
        default_factory=lambda: {"lite": "low", "pro": "high", "max": "xhigh", "ultra": "max"}
    )
    #: The run size of a request that names none (the page shows ``pro`` as Large).
    default_preset: Preset | None = "pro"
    transcribe: TranscribeConfig = Field(default_factory=TranscribeConfig)
    fanout: FanoutConfig = Field(default_factory=FanoutConfig)
    #: Browser origins that may call the API; ``:*`` at the end allows any port.
    allowed_origins: list[str] = Field(
        default_factory=lambda: [
            "https://chipin.space",
            "http://127.0.0.1:*",
            "http://localhost:*",
            "http://[::1]:*",
        ]
    )
    #: Public dataset name (a spec's ``data.dataset``) -> a local folder holding it.
    datasets: dict[str, Path] = Field(default_factory=dict)
    helper: HelperConfig = Field(default_factory=HelperConfig)
    questions: QuestionsConfig = Field(default_factory=QuestionsConfig)


def load_api_config(path: Path = API_CONFIG_PATH, *, overlay: dict[str, Any] | None = None) -> ApiConfig:
    """Load and validate ``api.yaml`` with ``overlay`` (the backend config's ``api:``
    section) deep-merged on top; ``ValueError`` on invalid YAML."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path} must hold a mapping at the top level")
    return ApiConfig.model_validate(deep_merge(data, overlay or {}))


__all__ = [
    "API_CONFIG_PATH",
    "ApiAgent",
    "ApiConfig",
    "FanoutConfig",
    "Preset",
    "SubagentConfig",
    "load_api_config",
]
