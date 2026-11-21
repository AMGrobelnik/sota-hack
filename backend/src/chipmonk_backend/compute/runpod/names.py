"""Pod names. Every pod this backend creates starts with the configured prefix,
and every sweep matches that prefix only: a pod with any other name belongs to
someone else and is never terminated."""

from __future__ import annotations

import re

DEFAULT_WORKER_PREFIX = "chipmonk_worker_"
_UNSAFE = re.compile(r"[^A-Za-z0-9_-]+")


def worker_pod_name(prefix: str, run_id: str, agent: str, attempt: int) -> str:
    """``<prefix><run_id>_<agent>_a<attempt>``, with unsafe characters replaced."""
    return f"{prefix}{_UNSAFE.sub('-', run_id)}_{_UNSAFE.sub('-', agent)}_a{attempt}"


def is_ours(pod_name: str, prefix: str) -> bool:
    """Whether a pod name carries our (non-empty) prefix."""
    return bool(prefix) and pod_name.startswith(prefix)


__all__ = ["DEFAULT_WORKER_PREFIX", "is_ours", "worker_pod_name"]
