"""The real local path end to end with the stub backend: config -> runner -> run folder."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
import yaml

from chipmonk_backend.agents.env import build_agent_env
from chipmonk_backend.agents.stub import StubBackend
from chipmonk_backend.agents.types import AgentResult, AgentSpec, EventSink
from chipmonk_backend.compute.local import LocalRunner
from chipmonk_backend.compute.modes import chain_for_tier
from chipmonk_backend.config import BackendConfig, load_config
from chipmonk_backend.orchestrate import run_agent
from chipmonk_backend.runs import RunDir


async def test_stub_run_writes_record_events_and_files(config: BackendConfig) -> None:
    spec = AgentSpec(name="a1", prompts=["hello"], backend="stub", expected_files=["out/x.txt"])
    run, result = await run_agent(spec, config, run_mode="local")

    assert not result.failed
    record = json.loads(run.record_path.read_text())
    assert record["status"] == "succeeded"
    assert record["agent"]["prompts"] == ["hello"]
    kinds = [event.kind for event in run.read_events()]
    assert kinds[0] == "agent_start" and kinds[-1] == "agent_end"
    assert (run.workspace / "out" / "x.txt").is_file()


async def test_backend_setup_error_is_recorded_as_failed(
    config: BackendConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def setup_fails(self: StubBackend, spec: AgentSpec, sink: EventSink) -> AgentResult:
        raise RuntimeError("backend could not start")

    monkeypatch.setattr(StubBackend, "run", setup_fails)
    spec = AgentSpec(name="a1", prompts=["hi"], backend="stub")
    with pytest.raises(RuntimeError, match="could not start"):
        await run_agent(spec, config, run_mode="local", run_id="r1")
    record = json.loads((config.runs_dir / "r1" / "run.json").read_text())
    assert record["status"] == "failed" and "could not start" in record["error"]
    assert record["finished_at"]


async def test_cancelled_run_is_recorded_as_stopped(
    config: BackendConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    started = asyncio.Event()

    async def hangs(self: StubBackend, spec: AgentSpec, sink: EventSink) -> AgentResult:
        started.set()
        await asyncio.sleep(60)
        raise AssertionError("not cancelled")

    closed: list[str] = []

    async def close(self: LocalRunner) -> None:
        closed.append("closed")

    monkeypatch.setattr(StubBackend, "run", hangs)
    monkeypatch.setattr(LocalRunner, "close", close)
    task = asyncio.create_task(
        run_agent(AgentSpec(name="a1", prompts=["hi"], backend="stub"), config, run_mode="local", run_id="r2")
    )
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    record = json.loads((config.runs_dir / "r2" / "run.json").read_text())
    assert record["status"] == "stopped" and record["finished_at"]
    assert closed == ["closed"]  # the runner released its machines (pods) on the way out


async def test_max_concurrent_agents_is_enforced(
    config: BackendConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    running, peak = 0, 0

    async def tracked(self: StubBackend, spec: AgentSpec, sink: EventSink) -> AgentResult:
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(0.05)
        running -= 1
        return AgentResult(agent=spec.name)

    monkeypatch.setattr(StubBackend, "run", tracked)
    compute = config.compute.model_copy(update={"max_concurrent_agents": 2})
    cfg = config.model_copy(update={"compute": compute})
    specs = [AgentSpec(name=f"a{i}", prompts=["hi"], backend="stub") for i in range(5)]
    results = await asyncio.gather(*(run_agent(spec, cfg, run_mode="local") for spec in specs))
    assert peak == 2 and all(not result.failed for _run, result in results)


@pytest.mark.parametrize("run_id", ["../escape", "a/b", "..", ".", "", "x" * 129, "has space"])
def test_unsafe_run_id_is_refused(tmp_path: Path, run_id: str) -> None:
    with pytest.raises(ValueError, match="bad run_id"):
        RunDir.create(tmp_path / "runs", run_id)
    assert not (tmp_path / "escape").exists()


def test_config_file_overlays_the_defaults(tmp_path: Path) -> None:
    path = tmp_path / "mine.yaml"
    path.write_text(yaml.safe_dump({"compute": {"runpod": {"max_usd_per_hr": 0.5}}}), encoding="utf-8")
    loaded = load_config(path, env_file=tmp_path / "absent.env")
    defaults = load_config(env_file=tmp_path / "absent.env")
    assert loaded.compute.runpod.max_usd_per_hr == 0.5
    assert loaded.compute.runpod.tier_chains == defaults.compute.runpod.tier_chains
    assert loaded.compute.runpod.tier_chains["gpu_basic"]
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "missing.yaml", env_file=tmp_path / "absent.env")


def test_agent_env_scrubs_keys() -> None:
    base = {"PATH": "/bin", "ANTHROPIC_API_KEY": "x", "RUNPOD_API_KEY": "y", "SECRET_THING": "z"}
    env = build_agent_env({"RUNPOD_API_KEY": "y"}, base=base)
    assert env["PATH"] == "/bin"
    assert not {"ANTHROPIC_API_KEY", "RUNPOD_API_KEY", "SECRET_THING"} & env.keys()


def test_gpu_tier_never_falls_back_to_cpu() -> None:
    chain = ["cpu3g-2-8", "NVIDIA RTX A4000"]
    assert chain_for_tier(chain, "gpu_basic") == ["NVIDIA RTX A4000"]
    assert chain_for_tier(["NVIDIA L4", "cpu3g-2-8"], "cpu_basic") == ["cpu3g-2-8", "NVIDIA L4"]
