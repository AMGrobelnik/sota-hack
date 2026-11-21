"""RunPodRunner's lifecycle against a fake control plane and real local workers.

The fake RunPodAPI "creates" a pod by starting the real worker app on
localhost with the token from the create request, so create, wait for ready,
submit, stream, fetch the result and outputs, and terminate all run for real;
only RunPod itself is faked. Nothing here reaches the network.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from aiohttp.test_utils import TestServer
from script_backend import use_script_backend

from chipmonk_backend.agents.types import AgentSpec
from chipmonk_backend.compute.factory import runner_for
from chipmonk_backend.compute.runpod.api import (
    Offer,
    PodInfo,
    PodNotFoundError,
    PodSpec,
    RunPodAPI,
    RunPodError,
    RunPodTransientError,
)
from chipmonk_backend.compute.runpod.reaper import reap_orphans
from chipmonk_backend.compute.runpod.runner import RunPodRunner
from chipmonk_backend.compute.runpod.worker import WORKER_TOKEN_ENV, create_app
from chipmonk_backend.config import BackendConfig
from chipmonk_backend.orchestrate import run_agent
from chipmonk_backend.runs import RunDir

TRAINS = """
import pathlib
print("fine-tuning 1000 candidates")
pathlib.Path("best").mkdir()
pathlib.Path("best/netlist.v").write_text("module chip; endmodule")
print("best: 12 gates")
"""


class FakeRunPod(RunPodAPI):
    """Records every call; a created pod is a real worker app on localhost."""

    def __init__(self, pod_config: BackendConfig, **behaviour: Any) -> None:
        super().__init__("fake-key")
        self.pod_config = pod_config
        self.offers_by_machine: dict[str, Offer] | None = behaviour.get("offers")
        self.refuse: set[str] = set(behaviour.get("refuse", ()))  # create fails (stock-out)
        self.never_healthy: set[str] = set(behaviour.get("never_healthy", ()))
        self.price: dict[str, float] = behaviour.get("price", {})
        self.terminate_failures: int = behaviour.get("terminate_failures", 0)
        self.created: list[PodSpec] = []
        self.terminated: list[str] = []
        self.pods: dict[str, PodInfo] = {}
        self.urls: dict[str, str] = {}
        self._servers: list[TestServer] = []

    async def offers(self, *, cloud: str = "SECURE") -> dict[str, Offer]:
        if self.offers_by_machine is None:
            raise RunPodError("catalog down")
        return self.offers_by_machine

    async def create_pod(self, spec: PodSpec) -> PodInfo:
        self.build_create_request(spec)  # the real body builder must accept it
        self.created.append(spec)
        if spec.machine in self.refuse:
            raise RunPodError("HTTP 400: There are no longer any instances available")
        pod = PodInfo(
            id=f"pod{len(self.created)}",
            name=spec.name,
            desired_status="RUNNING",
            machine=spec.machine,
            usd_per_hr=self.price.get(spec.machine, 0.2),
            created_at="2026-11-21T10:00:00Z",
        )
        self.pods[pod.id] = pod
        if spec.machine not in self.never_healthy:
            server = TestServer(create_app(self.pod_config, token=spec.env[WORKER_TOKEN_ENV]))
            await server.start_server()
            self._servers.append(server)
            self.urls[pod.id] = str(server.make_url(""))
        return pod

    async def get_pod(self, pod_id: str) -> PodInfo:
        if pod_id not in self.pods:
            raise PodNotFoundError(pod_id)
        return self.pods[pod_id]

    async def list_pods(self) -> list[PodInfo]:
        return list(self.pods.values())

    async def terminate_pod(self, pod_id: str) -> None:
        if self.terminate_failures > 0:
            self.terminate_failures -= 1
            raise RunPodTransientError("HTTP 503 on DELETE")
        self.terminated.append(pod_id)
        if pod_id in self.pods:
            self.pods[pod_id] = replace(self.pods[pod_id], desired_status="TERMINATED")

    async def stop_servers(self) -> None:
        for server in self._servers:
            await server.close()


class LocalPodRunner(RunPodRunner):
    """Reaches a pod's worker on localhost instead of RunPod's proxy."""

    def worker_url(self, pod: PodInfo) -> str:
        assert isinstance(self.api, FakeRunPod)
        return self.api.urls.get(pod.id, "http://127.0.0.1:9")  # nothing listens: never healthy


def _with_runpod(config: BackendConfig, **runpod: Any) -> BackendConfig:
    settings = {
        "dry_run": False,
        "image": "registry.example/chipmonk-worker:test",
        "healthcheck_timeout_s": 1,
        "tier_chains": {
            "cpu_basic": ["cpu3g-2-8", "cpu5g-2-8"],
            "gpu_basic": ["cpu3g-2-8", "NVIDIA RTX A4000"],
        },
        **runpod,
    }
    compute = config.compute.model_copy(update={"runpod": config.compute.runpod.model_copy(update=settings)})
    return config.model_copy(update={"compute": compute})


@pytest.fixture
async def fake(config: BackendConfig, tmp_path: Path) -> AsyncIterator[FakeRunPod]:
    api = FakeRunPod(config.model_copy(update={"runs_dir": tmp_path / "pod_runs"}))
    yield api
    await api.stop_servers()


def _runner(config: BackendConfig, api: FakeRunPod) -> LocalPodRunner:
    runner = LocalPodRunner(config, api=api)
    runner.poll_interval_s = 0.05
    return runner


async def test_pod_lifecycle_streams_fetches_outputs_and_terminates(
    config: BackendConfig, fake: FakeRunPod, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_script_backend(monkeypatch)
    cfg = _with_runpod(config)
    run = RunDir.create(tmp_path / "runs", "r1")
    spec = AgentSpec(name="designer", prompts=[TRAINS], backend="script")  # type: ignore[arg-type]

    result = await _runner(cfg, fake).run(spec, run, tier="cpu_basic")

    assert not result.failed and result.files == ["best/netlist.v"]
    assert (run.workspace / "best" / "netlist.v").read_text() == "module chip; endmodule"
    texts = [e.data["text"] for e in run.read_events() if e.kind == "text"]
    assert texts == ["fine-tuning 1000 candidates", "best: 12 gates"]
    assert fake.terminated == ["pod1"]
    created = fake.created[0]
    assert created.machine == "cpu3g-2-8" and created.name == "chipmonk_worker_r1_designer_a1"
    assert set(created.env) == {WORKER_TOKEN_ENV}  # the only secret a pod gets
    assert "--ttl-s" in created.command and str(7200 + 300) in created.command


async def test_stock_out_and_unhealthy_pods_fall_through_the_chain(
    config: BackendConfig, fake: FakeRunPod, tmp_path: Path
) -> None:
    fake.refuse = {"cpu3g-2-8"}
    fake.never_healthy = {"cpu5g-2-8"}
    cfg = _with_runpod(config, tier_chains={"cpu_basic": ["cpu3g-2-8", "cpu5g-2-8", "cpu3c-2-4"]})
    run = RunDir.create(tmp_path / "runs", "r2")

    result = await _runner(cfg, fake).run(AgentSpec(name="a", prompts=["hi"], backend="stub"), run)

    assert not result.failed
    assert [s.machine for s in fake.created] == ["cpu3g-2-8", "cpu5g-2-8", "cpu3c-2-4"]
    assert fake.terminated == ["pod2", "pod3"]  # the unhealthy pod was terminated too


async def test_no_machine_at_all_raises_and_leaves_nothing_running(
    config: BackendConfig, fake: FakeRunPod, tmp_path: Path
) -> None:
    fake.never_healthy = {"cpu3g-2-8", "cpu5g-2-8"}
    cfg = _with_runpod(config)
    spec = AgentSpec(name="a", prompts=["hi"], backend="stub")
    runner = _runner(cfg, fake)
    with pytest.raises(RunPodError, match="no cpu_basic machine"):
        await runner.run(spec, RunDir.create(tmp_path / "runs", "r3"))
    assert sorted(fake.terminated) == ["pod1", "pod2"]
    assert not runner._live_pods


async def test_failed_terminate_is_kept_and_retried_by_close(
    config: BackendConfig, fake: FakeRunPod, tmp_path: Path
) -> None:
    fake.terminate_failures = 1
    runner = _runner(_with_runpod(config), fake)
    await runner.run(
        AgentSpec(name="a", prompts=["hi"], backend="stub"), RunDir.create(tmp_path / "runs", "r4")
    )
    assert list(runner._live_pods) == ["pod1"] and fake.terminated == []
    await runner.close()
    await runner.close()  # idempotent
    assert fake.terminated == ["pod1"] and not runner._live_pods


async def test_gpu_tier_never_rents_a_cpu_host_and_price_cap_holds(
    config: BackendConfig, fake: FakeRunPod, tmp_path: Path
) -> None:
    fake.offers_by_machine = {"NVIDIA RTX A4000": Offer("HIGH", 0.25), "NVIDIA L4": Offer("HIGH", 0.49)}
    cfg = _with_runpod(
        config, max_usd_per_hr=0.4, tier_chains={"gpu_basic": ["cpu3g-2-8", "NVIDIA L4", "NVIDIA RTX A4000"]}
    )
    runner = _runner(cfg, fake)
    assert await runner.candidates("gpu_basic") == ["NVIDIA RTX A4000"]

    fake.offers_by_machine = None  # catalog down: chain order, but the pod's own rate is checked
    fake.price = {"NVIDIA L4": 0.49}
    await runner.run(
        AgentSpec(name="a", prompts=["hi"], backend="stub"),
        RunDir.create(tmp_path / "runs", "r5"),
        tier="gpu_basic",
    )
    assert [s.machine for s in fake.created] == ["NVIDIA L4", "NVIDIA RTX A4000"]
    assert fake.terminated[0] == "pod1"  # over the cap: terminated at once


async def test_dry_run_writes_the_request_and_creates_nothing(config: BackendConfig, tmp_path: Path) -> None:
    cfg = _with_runpod(config, dry_run=True, image="")
    run, result = await run_agent(
        AgentSpec(name="a", prompts=["hi"], backend="stub"),
        cfg,
        run_mode="on_demand",
        tier="gpu_basic",
        run_id="dry",
    )
    assert isinstance(runner_for(cfg, "on_demand"), RunPodRunner)
    assert result.failed and "dry run" in (result.error or "")
    plan = json.loads((run.path / "pod_request.json").read_text())
    assert plan["machines"] == ["NVIDIA RTX A4000"]  # the CPU host is dropped for a GPU tier
    assert plan["request"]["gpu"] == {"id": "NVIDIA RTX A4000", "count": 1}
    assert plan["request"]["env"] == {WORKER_TOKEN_ENV: "<redacted>"}


async def test_reaper_matches_prefix_and_age_and_only_acts_when_asked(fake: FakeRunPod) -> None:
    fake.pods = {
        "a": PodInfo("a", "chipmonk_worker_r1_x_a1", "RUNNING", "cpu3g", created_at="2026-11-21T10:00:00Z"),
        "b": PodInfo("b", "someone_elses_pod", "RUNNING", "cpu3g", created_at="2026-11-21T10:00:00Z"),
        "c": PodInfo("c", "chipmonk_worker_r2_x_a1", "TERMINATED", "cpu3g"),
        "d": PodInfo("d", "chipmonk_worker_r3_x_a1", "RUNNING", "cpu3g"),  # age unknown
    }
    with pytest.raises(ValueError):
        await reap_orphans(fake, prefix="")
    found = await reap_orphans(fake, prefix="chipmonk_worker_")
    assert [p.id for p in found] == ["a", "d"] and fake.terminated == []
    old = await reap_orphans(fake, prefix="chipmonk_worker_", older_than_s=60, dry_run=False)
    assert [p.id for p in old] == ["a"] and fake.terminated == ["a"]
