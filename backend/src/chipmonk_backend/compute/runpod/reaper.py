"""Orphan sweep: find (and only with ``dry_run=False`` terminate) our leftover pods.

STUB: port from AI Inventor's
``.claude/skills/aii-runpod/scripts/aii_runpod_reap_orphans.py`` (dry run by
default, prefix mandatory) and ``aii_runpod/pod_infra/utils.py::
cleanup_stale_workers``. Never touch a pod whose name lacks the prefix, and
never touch volumes.
"""

from __future__ import annotations

from chipmonk_backend.compute.runpod.api import PodInfo, RunPodAPI


async def reap_orphans(
    api: RunPodAPI,
    *,
    prefix: str,
    older_than_s: int = 0,
    dry_run: bool = True,
) -> list[PodInfo]:
    """Pods named ``prefix*`` (older than ``older_than_s``); terminated only when
    ``dry_run`` is false. ``ValueError`` for an empty prefix. Returns the matches."""
    raise NotImplementedError("reap_orphans: port aii_runpod_reap_orphans.py")


__all__ = ["reap_orphans"]
