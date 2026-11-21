"""Backend configuration: one YAML file, an optional local overlay, and ``.env``.

Load order (later wins):

1. ``backend/config/backend.yaml`` (committed, commented defaults), or the file
   named by ``$CHIPMONK_CONFIG`` or the ``path`` argument;
2. its sibling ``<stem>.local.yaml`` if present (gitignored: RunPod ids, image
   refs, anything per machine), deep-merged on top;
3. ``backend/.env`` is loaded into ``os.environ`` with ``override=False`` so the
   process environment wins. Keys are only ever read from the environment by
   NAME; no secret value belongs in any YAML file.

The value vocabularies (:data:`RunMode`, :data:`ComputeTier`, :data:`Effort`)
are declared here because the schema is where they are enforced; the
subpackages import them from this module, which imports none of them.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field

#: ``backend/`` (the project root holding pyproject.toml, config/ and .env).
BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = BACKEND_ROOT / "config" / "backend.yaml"
DEFAULT_ENV_PATH = BACKEND_ROOT / ".env"
CONFIG_ENV_VAR = "CHIPMONK_CONFIG"

#: Where an agent runs. ``local``: in this process on any host (tests, dev,
#: and the agent process inside a RunPod worker pod). ``flex``: on a Mac the
#: team owns, at no rental cost. ``on_demand``: one rented RunPod worker pod
#: per agent. Same vocabulary as AI Inventor's ``execute_env.run_mode``.
RunMode = Literal["local", "flex", "on_demand"]
#: Hardware ladder, cheapest first. A GPU tier never falls back to a CPU host.
ComputeTier = Literal["cpu_basic", "cpu_plus", "gpu_basic", "gpu_plus"]
Effort = Literal["low", "medium", "high", "xhigh", "max"]
PermissionMode = Literal["default", "acceptEdits", "plan", "bypassPermissions"]


class _Section(BaseModel):
    """Base for every config section: unknown keys are an error, not ignored."""

    model_config = ConfigDict(extra="forbid")


class LlmConfig(_Section):
    """Direct OpenRouter chat calls (no agent loop)."""

    base_url: str | None = None  # None = chipmonk_backend.llm.endpoints.BASE_URL
    timeout_s: float = 120.0
    max_attempts: int = 5  # 1 call + 4 retries on 429/5xx, honouring Retry-After
    default_model: str = "deepseek/deepseek-v4-flash-0731"
    #: Short names for OpenRouter model ids, e.g. ``cheap: openai/gpt-5-nano``.
    presets: dict[str, str] = Field(default_factory=dict)


class ClaudeCliConfig(_Section):
    """The ``claude_cli`` agent backend: the interactive ``claude`` CLI under a PTY."""

    cli_path: str = "claude"
    #: Minimum CLI release the PTY driver was written against; startup dialogs
    #: change between releases, so upgrade deliberately.
    cli_version: str = "2.1.322"
    model: str = "claude-opus-5-5"
    effort: Effort = "high"
    permission_mode: PermissionMode = "bypassPermissions"
    skip_permissions: bool = True  # --dangerously-skip-permissions
    #: Empty = no settings files loaded (no stray .mcp.json); ["project"] loads skills.
    setting_sources: list[Literal["user", "project", "local"]] = Field(default_factory=list)
    #: CLI login directory; None = $CLAUDE_CONFIG_DIR or the CLI default (~/.claude).
    config_dir: Path | None = None
    turn_timeout_s: int = 3600
    stall_timeout_s: int = 1800


class OpenRouterAgentConfig(_Section):
    """The ``openrouter`` agent backend (OpenHands Agent SDK over LiteLLM)."""

    model: str = "deepseek/deepseek-v4-flash-0731"
    effort: Effort = "high"
    fallback_model: str | None = "openai/gpt-5-nano"
    provider_order: list[str] = Field(default_factory=list)
    allow_fallbacks: bool = True


class AgentsConfig(_Section):
    """Agent backends; a spec's ``backend`` overrides ``default_backend``."""

    default_backend: Literal["claude_cli", "openrouter", "stub"] = "claude_cli"
    #: True = tell the agent it may call any OpenRouter model through
    #: ``python -m chipmonk_backend ask``; each call's cost lands in the run record.
    openrouter_tool: bool = False
    claude_cli: ClaudeCliConfig = Field(default_factory=ClaudeCliConfig)
    openrouter: OpenRouterAgentConfig = Field(default_factory=OpenRouterAgentConfig)


class RunPodConfig(_Section):
    """On Demand mode: one RunPod worker pod per agent."""

    #: True = build and log every create-pod request but never send it.
    dry_run: bool = True
    cloud_type: Literal["SECURE", "COMMUNITY"] = "SECURE"
    data_center_id: str = ""  # empty = any data center
    image: str = ""  # the team's worker image ref; set in backend.local.yaml
    network_volume_id: str = ""  # empty = no volume; never default a name
    pod_name_prefix: str = "chipmonk_worker_"
    pod_timeout_s: int = 7200  # hard TTL: the worker kills itself after this
    healthcheck_timeout_s: int = 600  # image pull plus boot can take minutes
    max_usd_per_hr: float = 1.0  # never rent a machine above this price
    disk_gb: int = 20
    ports: list[str] = Field(default_factory=lambda: ["22/tcp", "8080/http"])
    #: Machines to race per tier, in order: GPU type ids or CPU instance ids.
    tier_chains: dict[ComputeTier, list[str]] = Field(default_factory=dict)


class FlexConfig(_Section):
    """Flex mode: agents run on a Mac the team owns."""

    #: ``host``: directly on the Mac, as the logged-in user. AI Inventor's
    #: macOS-VM isolation (``vm``) is deferred.
    isolation: Literal["host"] = "host"
    require_macos: bool = True


class ComputeConfig(_Section):
    """Where agents run and on what hardware."""

    run_mode: RunMode = "local"
    tier: ComputeTier = "cpu_basic"
    max_concurrent_agents: int = 4
    runpod: RunPodConfig = Field(default_factory=RunPodConfig)
    flex: FlexConfig = Field(default_factory=FlexConfig)


class BackendConfig(_Section):
    """The whole backend configuration."""

    runs_dir: Path = Path("runs")  # relative paths resolve against BACKEND_ROOT
    log_dir: Path = Path("logs")
    log_level: str = "INFO"
    llm: LlmConfig = Field(default_factory=LlmConfig)
    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    compute: ComputeConfig = Field(default_factory=ComputeConfig)

    def resolved_runs_dir(self) -> Path:
        """``runs_dir`` as an absolute path."""
        return resolve_path(self.runs_dir)

    def resolved_log_dir(self) -> Path:
        """``log_dir`` as an absolute path."""
        return resolve_path(self.log_dir)


def resolve_path(path: Path) -> Path:
    """An absolute path; a relative one is taken relative to :data:`BACKEND_ROOT`."""
    expanded = path.expanduser()
    return expanded if expanded.is_absolute() else BACKEND_ROOT / expanded


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """``overlay`` merged into a copy of ``base``; nested dicts merge, anything else replaces."""
    merged = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid YAML in {path}: {exc}") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must hold a mapping at the top level")
    return data


def load_config(path: Path | None = None, *, env_file: Path | None = None) -> BackendConfig:
    """Load and validate the backend config (see the module docstring for the order).

    Raises ``FileNotFoundError`` when the chosen config file is missing,
    ``ValueError`` for invalid YAML and ``pydantic.ValidationError`` for an
    unknown key or a bad value.
    """
    load_dotenv(env_file or DEFAULT_ENV_PATH, override=False)
    chosen = path or Path(os.environ.get(CONFIG_ENV_VAR) or DEFAULT_CONFIG_PATH)
    data = _read_yaml(chosen)
    overlay = chosen.with_name(f"{chosen.stem}.local.yaml")
    if overlay.is_file():
        data = deep_merge(data, _read_yaml(overlay))
    return BackendConfig.model_validate(data)


__all__ = [
    "BACKEND_ROOT",
    "CONFIG_ENV_VAR",
    "DEFAULT_CONFIG_PATH",
    "AgentsConfig",
    "BackendConfig",
    "ClaudeCliConfig",
    "ComputeConfig",
    "ComputeTier",
    "Effort",
    "FlexConfig",
    "LlmConfig",
    "OpenRouterAgentConfig",
    "PermissionMode",
    "RunMode",
    "RunPodConfig",
    "deep_merge",
    "load_config",
    "resolve_path",
]
