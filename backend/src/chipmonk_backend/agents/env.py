"""The environment an agent process gets: an allowlist, default deny.

Agents run with permissions bypassed, so whatever is in their environment is
theirs. Only the names below pass through; everything else (RUNPOD_API_KEY
above all) stays in the launcher. ``ANTHROPIC_API_KEY`` is scrubbed on purpose:
the ``claude`` CLI would silently switch from the subscription login to paid
API billing. Adapted from AI Inventor.
"""

from __future__ import annotations

import os
from collections.abc import Mapping

#: Names copied from the launcher's environment when present.
AGENT_ENV_ALLOWED_NAMES: frozenset[str] = frozenset(
    {
        # process basics
        "HOME",
        "PATH",
        "PWD",
        "SHELL",
        "TERM",
        "TMPDIR",
        "TZ",
        "USER",
        "LOGNAME",
        "LANG",
        "LANGUAGE",
        "COLUMNS",
        "LINES",
        "NO_COLOR",
        "FORCE_COLOR",
        # toolchains
        "VIRTUAL_ENV",
        "PYTHONPATH",
        "PYTHONUNBUFFERED",
        "PYTHONIOENCODING",
        "NODE_PATH",
        "CUDA_VISIBLE_DEVICES",
        "HF_HOME",
        # claude CLI
        "CLAUDE_CONFIG_DIR",
        "CLAUDE_CODE_ENABLE_TELEMETRY",
        "DISABLE_AUTOUPDATER",
        "IS_SANDBOX",
        # keys an agent's own tools may use
        "OPENROUTER_API_KEY",
        "HF_TOKEN",
    }
)

#: Name prefixes copied as a family (locale settings).
AGENT_ENV_ALLOWED_PREFIXES: tuple[str, ...] = ("LC_",)

#: Never passed, even when a caller's ``extra`` names them.
AGENT_ENV_SCRUBBED_NAMES: frozenset[str] = frozenset(
    {"ANTHROPIC_API_KEY", "RUNPOD_API_KEY", "CLAUDECODE", "CLAUDE_CODE_EFFORT_LEVEL"}
)

#: Always set for an agent: no cross-run memory, no CLI self-update mid-run.
AGENT_ENV_FORCED: Mapping[str, str] = {
    "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
    "DISABLE_AUTOUPDATER": "1",
}


def build_agent_env(
    extra: Mapping[str, str] | None = None,
    *,
    base: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """The environment for one agent process.

    ``base`` (default ``os.environ``) is filtered through the allowlist, then
    ``extra`` (the spec's non-secret values) and :data:`AGENT_ENV_FORCED` are
    laid on top; scrubbed names are removed last, whatever their source.
    """
    source = os.environ if base is None else base
    env = {
        name: value
        for name, value in source.items()
        if name in AGENT_ENV_ALLOWED_NAMES or name.startswith(AGENT_ENV_ALLOWED_PREFIXES)
    }
    env.update(extra or {})
    env.update(AGENT_ENV_FORCED)
    for name in AGENT_ENV_SCRUBBED_NAMES:
        env.pop(name, None)
    return env


__all__ = [
    "AGENT_ENV_ALLOWED_NAMES",
    "AGENT_ENV_ALLOWED_PREFIXES",
    "AGENT_ENV_FORCED",
    "AGENT_ENV_SCRUBBED_NAMES",
    "build_agent_env",
]
