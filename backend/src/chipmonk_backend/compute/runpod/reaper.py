"""Orphan sweep: find (and only with ``dry_run=False`` terminate) our leftover pods.

Ported from AI Inventor's ``.claude/skills/aii-runpod/scripts/
aii_runpod_reap_orphans.py``: dry run by default, prefix mandatory, one
failed terminate never stops the sweep. Never touches a pod whose name lacks
the prefix, and never touches volumes or templates.
"""

from __future__ import annotations

from loguru import logger

from chipmonk_backend.compute.runpod.api import PodInfo, RunPodAPI, RunPodError
from chipmonk_backend.compute.runpod.names import is_ours


async def reap_orphans(
    api: RunPodAPI,
    *,
    prefix: str,
    older_than_s: int = 0,
    dry_run: bool = True,
) -> list[PodInfo]:
    """Pods named ``prefix*`` (older than ``older_than_s``); terminated only when
    ``dry_run`` is false. ``ValueError`` for an empty prefix. Returns the matches.

    A pod with no creation time counts as old only when ``older_than_s`` is 0:
    an age that cannot be read never makes a pod eligible.
    """
    if not prefix:
        raise ValueError("a prefix is required; there is no sweep-everything")
    matches = []
    for pod in await api.list_pods():
        if not is_ours(pod.name, prefix) or pod.desired_status == "TERMINATED":
            continue
        age = pod.age_s()
        if older_than_s > 0 and (age is None or age < older_than_s):
            continue
        matches.append(pod)
    verb = "would terminate" if dry_run else "terminating"
    for pod in matches:
        logger.info("reaper: {} pod {} ({}, {})", verb, pod.id, pod.name, pod.desired_status)
        if dry_run:
            continue
        try:
            await api.terminate_pod(pod.id)
        except RunPodError as exc:
            logger.error("reaper: terminate of pod {} failed: {}", pod.id, exc)
    return matches


__all__ = ["reap_orphans"]
