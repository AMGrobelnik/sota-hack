"""``on_demand`` mode: one RunPod worker pod per agent.

STUB: port from AI Inventor ``aii_runpod/runpod_backend.py::RunPodEnv``,
``pod_infra/worker_pod.py::WorkerPod.run_agent_job``,
``pod_infra/pod_launcher.py::PodLauncher.launch`` (re-scan stock, walk the
chain), ``pod_infra/pod_liveness.py`` and ``_worker_pod/_leak.py``, with the
server-routed ``RunPodClient`` replaced by :class:`RunPodAPI` and the DB
ledgers replaced by ``RunRecord.compute`` in ``run.json``.
"""

from __future__ import annotations

from typing import ClassVar

from loguru import logger

from chipmonk_backend.agents.types import AgentResult, AgentSpec
from chipmonk_backend.compute.base import Runner
from chipmonk_backend.compute.runpod.api import PodInfo, PodSpec, RunPodAPI, RunPodError
from chipmonk_backend.config import BackendConfig, ComputeTier, RunMode
from chipmonk_backend.runs import RunDir


class RunPodRunner(Runner):
    """Rents a worker pod, ships the spec, streams events back, terminates the pod."""

    mode: ClassVar[RunMode] = "on_demand"

    def __init__(self, config: BackendConfig, *, api: RunPodAPI | None = None) -> None:
        super().__init__(config)
        self.api = api or RunPodAPI()
        self._live_pods: dict[str, PodInfo] = {}

    async def run(self, spec: AgentSpec, run: RunDir, *, tier: ComputeTier | None = None) -> AgentResult:
        """One agent on one pod.

        1. ``chain = modes.chain_for_tier(runpod.tier_chains[tier], tier)``;
           drop machines above ``runpod.max_usd_per_hr``.
        2. :meth:`pod_spec` for the first in-stock machine; when
           ``runpod.dry_run`` is true, write ``api.build_create_request(...)``
           to ``run.path / "pod_request.json"`` and return a failed result
           saying so, without creating anything.
        3. ``api.create_pod``; record pod id, machine and $/hr in
           ``RunRecord.compute``; wait for :class:`WorkerClient.wait_healthy`.
        4. ``submit`` the spec, copy every ``events()`` item into
           ``run.event_sink()``, then fetch ``result()``.
        5. Terminate the pod in ``finally``; a failed terminate is logged and
           left for :func:`~chipmonk_backend.compute.runpod.reaper.reap_orphans`.
        """
        raise NotImplementedError("RunPodRunner.run: port RunPodEnv + WorkerPod")

    def pod_spec(self, *, run_id: str, agent: str, attempt: int, machine: str, token: str) -> PodSpec:
        """The create request for one worker: image, machine, ports, disk, the
        worker token in env, TTL ``runpod.pod_timeout_s``; no secret but the token."""
        raise NotImplementedError("RunPodRunner.pod_spec")

    async def close(self) -> None:
        """Terminate every pod this runner still holds, then close the API client.

        A pod that will not terminate is logged and kept in ``_live_pods`` for
        the next call or the reaper; ``close`` itself never raises for it.
        """
        for pod_id in list(self._live_pods):
            try:
                await self.api.terminate_pod(pod_id)
            except RunPodError as exc:
                logger.error("terminate of pod {} failed, left for the reaper: {}", pod_id, exc)
            else:
                del self._live_pods[pod_id]
        await self.api.aclose()


__all__ = ["RunPodRunner"]
