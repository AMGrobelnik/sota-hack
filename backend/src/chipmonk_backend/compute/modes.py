"""Run-mode and compute-tier vocabulary, asked one named question at a time.

``local``: in this process (tests, dev, and the agent inside a worker pod).
``flex``: on a Mac the team owns, nothing rented. ``on_demand``: a rented
RunPod worker pod per agent. Tiers are the hardware ladder ``cpu_basic <
cpu_plus < gpu_basic < gpu_plus``. Adapted from AI Inventor's
``aii_lib/execute_env/modes.py`` and ``aii_lib/compute_tiers.py``: compare a
mode through these predicates, not with string literals elsewhere.
"""

from __future__ import annotations

from typing import Final, get_args

from chipmonk_backend.config import ComputeTier, RunMode

RUN_MODES: Final[tuple[RunMode, ...]] = get_args(RunMode)
TIERS: Final[tuple[ComputeTier, ...]] = get_args(ComputeTier)
CPU_TIERS: Final[tuple[ComputeTier, ...]] = ("cpu_basic", "cpu_plus")
GPU_TIERS: Final[tuple[ComputeTier, ...]] = ("gpu_basic", "gpu_plus")


def rents_pods(mode: RunMode) -> bool:
    """Whether the mode rents RunPod machines (and so costs money per hour)."""
    return mode == "on_demand"


def runs_in_process(mode: RunMode) -> bool:
    """Whether the agent runs in the launcher's own process."""
    return mode in ("local", "flex")


def needs_gpu(tier: ComputeTier) -> bool:
    """Whether the tier promises a GPU. A GPU tier never falls back to CPU."""
    return tier in GPU_TIERS


def is_cpu_machine(machine_id: str) -> bool:
    """RunPod CPU instance ids start with ``cpu`` (``cpu3g-2-8``); GPU ids name the card."""
    return machine_id.lower().startswith("cpu")


def chain_for_tier(machine_ids: list[str], tier: ComputeTier) -> list[str]:
    """The machines to race for ``tier``, in order.

    A CPU tier keeps every CPU host ahead of any GPU host (a GPU host is a
    stock-out last resort, still bounded by ``max_usd_per_hr``). A GPU tier
    drops CPU hosts entirely: GPU work on a CPU box silently produces wrong
    results.
    """
    named = [m for m in machine_ids if m]
    cpus = [m for m in named if is_cpu_machine(m)]
    gpus = [m for m in named if not is_cpu_machine(m)]
    return gpus if needs_gpu(tier) else cpus + gpus


__all__ = [
    "CPU_TIERS",
    "GPU_TIERS",
    "RUN_MODES",
    "TIERS",
    "ComputeTier",
    "RunMode",
    "chain_for_tier",
    "is_cpu_machine",
    "needs_gpu",
    "rents_pods",
    "runs_in_process",
]
