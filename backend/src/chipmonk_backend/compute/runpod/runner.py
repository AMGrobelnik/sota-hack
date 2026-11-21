"""``on_demand`` mode: one RunPod worker pod per agent.

A tier maps to a chain of machine types under the owner's $/hr ceiling. The
launcher walks the chain (in-stock first; a stock reading orders the chain
but never vetoes a type), creates the pod, waits for its health check,
submits the job, streams the events, fetches the result and terminates the
pod in ``finally``. A pod that RunPod reports gone ends the wait, and a
failed terminate is kept for a retry. RunPod is reached through
:class:`RunPodAPI`; the pod's facts go into ``RunRecord.compute`` in
``run.json``; the name prefix is what
:func:`~chipmonk_backend.compute.runpod.reaper.reap_orphans` sweeps.
"""

from __future__ import annotations

import asyncio
import json
import secrets
import time
from dataclasses import replace
from typing import Any, ClassVar

from loguru import logger

from chipmonk_backend.agents.types import AgentEvent, AgentResult, AgentSpec, EventSink
from chipmonk_backend.compute.base import Runner
from chipmonk_backend.compute.modes import chain_for_tier
from chipmonk_backend.compute.runpod.api import (
    Offer,
    PodInfo,
    PodNotFoundError,
    PodSpec,
    RunPodAPI,
    RunPodError,
    offer_for,
)
from chipmonk_backend.compute.runpod.names import worker_pod_name
from chipmonk_backend.compute.runpod.worker import (
    RUNPOD_PROXY_URL,
    TTL_GRACE_S,
    WORKER_PORT,
    WORKER_TOKEN_ENV,
    WorkerClient,
    WorkerUnreachableError,
)
from chipmonk_backend.config import BackendConfig, ComputeTier, RunMode, RunPodConfig
from chipmonk_backend.runs import RunDir

POD_REQUEST_FILE = "pod_request.json"
#: Where a network volume is mounted on a worker (RunPod has no default).
WORKER_VOLUME_PATH = "/workspace"
#: Extra wall clock past the agent's own timeout for transfer and teardown.
RESULT_GRACE_S = 120
REDACTED = "<redacted>"


def max_pod_lifetime_s(rp: RunPodConfig) -> int:
    """The longest a healthy worker pod of this config can legitimately live:
    boot and health check, the job, its result grace, and the worker's TTL grace.
    A pod of ours older than this is an orphan, never a live run."""
    return rp.healthcheck_timeout_s + rp.pod_timeout_s + RESULT_GRACE_S + TTL_GRACE_S


class _MachineUnavailableError(RuntimeError):
    """This machine could not be had (create refused, never healthy, pod gone)."""


class RunPodRunner(Runner):
    """Rents a worker pod, ships the spec, streams events back, terminates the pod.

    Paid pods are refused unless ``compute.runpod.allow_paid_pods`` is true and
    the agent backend is in :attr:`POD_READY_BACKENDS`: a pod receives only its
    worker token, so a backend that needs a login or an API key (``claude_cli``,
    ``openrouter``) cannot authenticate there as built.
    """

    mode: ClassVar[RunMode] = "on_demand"
    #: Backends that can run on a pod with no credential but the worker token.
    POD_READY_BACKENDS: ClassVar[frozenset[str]] = frozenset({"stub"})

    def __init__(self, config: BackendConfig, *, api: RunPodAPI | None = None) -> None:
        super().__init__(config)
        self.api = api or RunPodAPI()
        self._live_pods: dict[str, PodInfo] = {}
        #: Names whose create failed ambiguously (timeout, 5xx, dropped answer):
        #: the pod may exist. :meth:`close` looks them up once more.
        self._doubtful: dict[str, RunDir] = {}
        #: Seconds between readiness probes; tests shrink it.
        self.poll_interval_s = 10.0

    async def run(self, spec: AgentSpec, run: RunDir, *, tier: ComputeTier | None = None) -> AgentResult:
        """One agent on one pod.

        1. The tier's chain (GPU tiers drop CPU hosts), without machines whose
           list price is above ``runpod.max_usd_per_hr``, in-stock first.
        2. With ``runpod.dry_run`` true, write the create request (token
           redacted) to ``run.path / "pod_request.json"`` and return a failed
           result saying so; nothing is created.
        3. Create a pod on the first machine that can be had, record it in
           ``RunRecord.compute``, wait for the worker's ``/health``.
        4. Submit the spec, copy every event into ``run.event_sink()``, fetch
           the result and the workspace.
        5. Terminate the pod in ``finally``; a failed terminate is logged,
           kept for :meth:`close`, and left for the reaper.

        Raises :class:`RunPodError` when no machine could be had, and before
        any create when paid pods are not enabled (see :meth:`check_paid_run`).
        """
        rp = self.config.compute.runpod
        chosen = tier or self.config.compute.tier
        token = secrets.token_urlsafe(32)
        if not rp.dry_run:
            self.check_paid_run(spec)
        machines = await self.candidates(chosen)
        if rp.dry_run:
            return self._dry_run(spec, run, chosen, machines, token)
        sink = run.event_sink()
        errors: list[str] = []
        for attempt, machine in enumerate(machines, start=1):
            pod_spec = self.pod_spec(
                run_id=run.run_id, agent=spec.name, attempt=attempt, machine=machine, token=token
            )
            try:
                pod = await self._create(pod_spec, run)
            except (RunPodError, _MachineUnavailableError) as exc:
                errors.append(f"{machine}: {exc}")
                logger.warning("pod on {} not created: {}", machine, exc)
                continue
            self._record(
                run, pod=pod.id, pod_name=pod.name, machine=machine, usd_per_hr=pod.usd_per_hr, tier=chosen
            )
            sink.emit(AgentEvent("status", spec.name, {"message": f"pod {pod.id} created on {machine}"}))
            try:
                return await self._run_on_pod(pod, spec, run, token)
            except _MachineUnavailableError as exc:
                errors.append(f"{machine}: {exc}")
                logger.warning("pod {} on {} unusable: {}", pod.id, machine, exc)
            finally:
                await self._terminate(pod.id, run)
        raise RunPodError(f"no {chosen} machine could be had: " + "; ".join(errors or ["empty chain"]))

    def check_paid_run(self, spec: AgentSpec) -> None:
        """:class:`RunPodError` unless a real (paid) pod may be created for ``spec``.

        Three conditions: ``compute.runpod.allow_paid_pods`` is true, the
        worker image is set, and the agent backend can authenticate on a pod
        that holds nothing but its worker token (:attr:`POD_READY_BACKENDS`).
        """
        rp = self.config.compute.runpod
        backend = spec.backend or self.config.agents.default_backend
        if not rp.allow_paid_pods:
            raise RunPodError(
                "paid pods are off: set compute.runpod.allow_paid_pods: true to create real pods "
                "(compute.runpod.dry_run: true writes the request without creating one)"
            )
        if backend not in self.POD_READY_BACKENDS:
            raise RunPodError(
                f"agent backend {backend!r} cannot authenticate on a pod: a pod gets only its worker "
                f"token, no Claude login and no API key. Backends that can run there: "
                f"{sorted(self.POD_READY_BACKENDS)}"
            )
        if not rp.image:
            raise RunPodError("compute.runpod.image is not set (the team's worker image ref)")

    async def candidates(self, tier: ComputeTier) -> list[str]:
        """Machines to try for ``tier``: in stock, then unknown, then out of stock; capped by price.

        The catalog read fails open (no key, API down): the chain is then
        tried in its configured order, and the price is checked on the pod.
        """
        rp = self.config.compute.runpod
        chain = chain_for_tier(rp.tier_chains.get(tier, []), tier)
        try:
            offers = await self.api.offers(cloud=rp.cloud_type)
        except RunPodError as exc:
            logger.warning("RunPod catalog unavailable ({}); trying the chain in order", exc)
            offers = {}
        ranked: list[tuple[int, str]] = []
        for machine in chain:
            offer = offer_for(machine, offers)
            if offer is not None and offer.usd_per_hr is not None and offer.usd_per_hr > rp.max_usd_per_hr:
                logger.info(
                    "skipping {}: ${:.2f}/hr is above the ${:.2f}/hr cap",
                    machine,
                    offer.usd_per_hr,
                    rp.max_usd_per_hr,
                )
                continue
            ranked.append((_stock_rank(offer), machine))
        if not ranked:
            raise RunPodError(f"tier {tier} has no machine at or under ${rp.max_usd_per_hr:.2f}/hr")
        return [machine for _rank, machine in sorted(ranked, key=lambda item: item[0])]

    def pod_spec(self, *, run_id: str, agent: str, attempt: int, machine: str, token: str) -> PodSpec:
        """The create request for one worker: image, machine, ports, disk, the
        worker token in env, and the worker's TTL; no secret but the token.

        The TTL ends the worker PROCESS only, not the pod (see
        :func:`~chipmonk_backend.compute.runpod.worker.start_ttl_watchdog`):
        this runner's ``finally`` and :meth:`close` terminate the pod, and the
        prefix reaper is the safety net when this process dies first."""
        rp = self.config.compute.runpod
        ports = list(rp.ports)
        if f"{WORKER_PORT}/http" not in ports:
            ports.append(f"{WORKER_PORT}/http")  # the launcher reaches the worker through it
        command = (
            "python",
            "-m",
            "chipmonk_backend.compute.runpod.worker",
            "--port",
            str(WORKER_PORT),
            "--ttl-s",
            str(rp.pod_timeout_s + TTL_GRACE_S),
        )
        return PodSpec(
            name=worker_pod_name(rp.pod_name_prefix, run_id, agent, attempt),
            image=rp.image,
            machine=machine,
            cloud_type=rp.cloud_type,
            data_center_id=rp.data_center_id,
            disk_gb=rp.disk_gb,
            ports=tuple(ports),
            env={WORKER_TOKEN_ENV: token},
            command=command,
            network_volume_id=rp.network_volume_id,
            volume_mount_path=WORKER_VOLUME_PATH if rp.network_volume_id else "",
        )

    def dry_run_request(self, *, run_id: str, agent: str, machine: str) -> dict[str, Any]:
        """The exact create body for ``machine``, with the worker token redacted."""
        spec = self.pod_spec(run_id=run_id, agent=agent, attempt=1, machine=machine, token=REDACTED)
        return self.api.build_create_request(spec)

    def worker_url(self, pod: PodInfo) -> str:
        """Where the launcher reaches the pod's worker (RunPod's HTTP proxy)."""
        return RUNPOD_PROXY_URL.format(pod_id=pod.id, port=WORKER_PORT)

    async def close(self) -> None:
        """Terminate every pod this runner still holds, then close the API client.

        First the names of failed creates are looked up once more (a pod can
        show up in the listing late) and any pod found is terminated. A pod
        that will not terminate, or a name that cannot be checked, is logged,
        recorded in ``run.json`` as a possible leak and kept for the next call
        or the reaper; ``close`` itself never raises for it.
        """
        for name, run in list(self._doubtful.items()):
            if await self._settle_failed_create(name, run):
                del self._doubtful[name]
        for pod_id in list(self._live_pods):
            try:
                await self.api.terminate_pod(pod_id)
            except RunPodError as exc:
                logger.error("terminate of pod {} failed, left for the reaper: {}", pod_id, exc)
            else:
                del self._live_pods[pod_id]
        await self.api.aclose()

    # ------------------------------------------------------------------

    def _dry_run(
        self, spec: AgentSpec, run: RunDir, tier: ComputeTier, machines: list[str], token: str
    ) -> AgentResult:
        """Write what would be sent, create nothing, return a failed result."""
        del token  # never written: the saved request carries a placeholder
        request = self.dry_run_request(run_id=run.run_id, agent=spec.name, machine=machines[0])
        plan = {"mode": self.mode, "tier": tier, "dry_run": True, "machines": machines, "request": request}
        path = run.path / POD_REQUEST_FILE
        path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
        self._record(run, dry_run=True, tier=tier, machine=machines[0], pod_request=str(path))
        message = f"dry run: no pod created; the create request for {machines[0]} is in {path}"
        run.event_sink().emit(AgentEvent("status", spec.name, {"message": message}))
        logger.info(message)
        return AgentResult(agent=spec.name, failed=True, error=message)

    async def _create(self, pod_spec: PodSpec, run: RunDir) -> PodInfo:
        """Create one pod and hold it; a pod billing above the cap is terminated at once.

        Any failed create may still have made a pod (the request timed out,
        the connection dropped, RunPod answered 5xx after acting, or the
        answer lacked an id), so the pod is looked up by its unique name and
        terminated. The name stays doubtful, because a pod can reach the
        listing late, and :meth:`close` looks once more.
        """
        try:
            pod = await self.api.create_pod(pod_spec)
        except RunPodError:
            self._doubtful[pod_spec.name] = run
            await self._settle_failed_create(pod_spec.name, run)
            raise
        self._live_pods[pod.id] = pod
        cap = self.config.compute.runpod.max_usd_per_hr
        if pod.usd_per_hr is not None and pod.usd_per_hr > cap:
            await self._terminate(pod.id, None)
            raise _MachineUnavailableError(f"pod bills ${pod.usd_per_hr:.2f}/hr, above the ${cap:.2f}/hr cap")
        return pod

    async def _run_on_pod(self, pod: PodInfo, spec: AgentSpec, run: RunDir, token: str) -> AgentResult:
        """Health, submit, stream, result, outputs. Machine trouble before submit raises."""
        rp = self.config.compute.runpod
        sink = run.event_sink()
        workdir = spec.workdir or run.workspace
        limit = min(spec.timeout_s or rp.pod_timeout_s, rp.pod_timeout_s)
        remote = replace(
            spec, workdir=None, timeout_s=limit, backend=spec.backend or self.config.agents.default_backend
        )
        client = WorkerClient(self.worker_url(pod), token=token)
        started = time.monotonic()
        try:
            await self._wait_ready(pod, client)
            sink.emit(AgentEvent("status", spec.name, {"message": f"worker on pod {pod.id} is up"}))
            try:
                await client.submit(remote, run_id=run.run_id)
            except (WorkerUnreachableError, RuntimeError) as exc:
                raise _MachineUnavailableError(f"job not accepted: {exc}") from exc
            try:
                async with asyncio.timeout(limit + RESULT_GRACE_S):
                    async for event in client.events():
                        sink.emit(event)
                    result = await client.result()
                    files = await client.download_outputs(workdir)
            except TimeoutError:
                return self._failed(
                    spec, sink, f"no result from pod {pod.id} within {limit + RESULT_GRACE_S}s", started
                )
            except WorkerUnreachableError as exc:
                return self._failed(spec, sink, f"worker pod {pod.id} lost: {exc}", started)
            logger.info(
                "pod {}: agent {} done (failed={}), {} output files",
                pod.id,
                spec.name,
                result.failed,
                len(files),
            )
            return result
        finally:
            await client.aclose()

    async def _wait_ready(self, pod: PodInfo, client: WorkerClient) -> None:
        """Until ``/health`` answers; RunPod reporting the pod gone or dead ends it early."""
        deadline = time.monotonic() + self.config.compute.runpod.healthcheck_timeout_s
        while not await client.is_healthy():
            try:
                state = await self.api.get_pod(pod.id)
            except PodNotFoundError as exc:
                raise _MachineUnavailableError("pod vanished while starting") from exc
            except RunPodError as exc:
                logger.debug("pod {} status read failed while starting: {}", pod.id, exc)
            else:
                if state.is_terminal:
                    raise _MachineUnavailableError(f"pod went {state.desired_status} while starting")
            if time.monotonic() >= deadline:
                raise _MachineUnavailableError(
                    f"worker not healthy after {self.config.compute.runpod.healthcheck_timeout_s}s"
                )
            await asyncio.sleep(self.poll_interval_s)

    async def _settle_failed_create(self, name: str, run: RunDir) -> bool:
        """Terminate any live pod named ``name``; ``True`` when the listing could be read.

        An unreadable listing records ``name`` under ``possible_leaks`` in
        ``run.json`` (the reaper finds it by prefix) and returns ``False``.
        """
        try:
            pods = await self.api.list_pods()
        except RunPodError as exc:
            logger.error("could not check for a pod named {} after a failed create: {}", name, exc)
            self._record_leak(run, name)
            return False
        for pod in pods:
            if pod.name == name and pod.desired_status != "TERMINATED":
                logger.warning("create of {} failed, yet pod {} exists: terminating it", name, pod.id)
                self._live_pods[pod.id] = pod
                self._record(run, pod=pod.id, pod_name=name, machine=pod.machine, created_despite_error=True)
                await self._terminate(pod.id, run)
        return True

    def _record_leak(self, run: RunDir, name: str) -> None:
        """Add ``name`` to ``RunRecord.compute["possible_leaks"]``."""
        if not run.record_path.is_file():
            return
        try:
            leaks = list(run.read_record().compute.get("possible_leaks") or [])
        except (OSError, ValueError, TypeError) as exc:
            logger.error("could not read {} to record leak {}: {}", run.record_path, name, exc)
            return
        if name not in leaks:
            self._record(run, possible_leaks=[*leaks, name])

    async def _terminate(self, pod_id: str, run: RunDir | None) -> None:
        """Terminate and forget a pod; on failure keep it for :meth:`close` and the reaper."""
        try:
            await self.api.terminate_pod(pod_id)
        except RunPodError as exc:
            logger.error("terminate of pod {} failed, left for close() and the reaper: {}", pod_id, exc)
            if run is not None:
                self._record(run, terminated=False, terminate_error=str(exc))
            return
        self._live_pods.pop(pod_id, None)
        logger.info("pod {} terminated", pod_id)
        if run is not None:
            self._record(run, terminated=True)

    @staticmethod
    def _failed(spec: AgentSpec, sink: EventSink, error: str, started: float) -> AgentResult:
        """A failed result, with the error also put in the event stream."""
        logger.warning("agent {}: {}", spec.name, error)
        sink.emit(AgentEvent("error", spec.name, {"message": error}))
        return AgentResult(agent=spec.name, failed=True, error=error, duration_s=time.monotonic() - started)

    @staticmethod
    def _record(run: RunDir, **facts: Any) -> None:
        """Merge ``facts`` into ``RunRecord.compute`` in ``run.json`` when the record exists."""
        if not run.record_path.is_file():
            return
        try:
            run.add_compute(**facts)
        except (OSError, ValueError, TypeError) as exc:
            logger.error("could not record compute facts in {}: {}", run.record_path, exc)


def _stock_rank(offer: Offer | None) -> int:
    """0 in stock, 1 unknown (fail open: still tried), 2 out of stock (tried last)."""
    if offer is None:
        return 1
    return 0 if offer.stock else 2


__all__ = ["POD_REQUEST_FILE", "WORKER_VOLUME_PATH", "RunPodRunner", "max_pod_lifetime_s"]
