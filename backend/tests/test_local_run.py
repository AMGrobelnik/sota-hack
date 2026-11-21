"""The real local path end to end with the stub backend: config -> runner -> run folder."""

from __future__ import annotations

import json

import pytest

from chipmonk_backend.agents.env import build_agent_env
from chipmonk_backend.agents.types import AgentSpec
from chipmonk_backend.compute.modes import chain_for_tier
from chipmonk_backend.config import BackendConfig
from chipmonk_backend.orchestrate import run_agent


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


async def test_backend_setup_error_is_recorded_as_failed(config: BackendConfig) -> None:
    cli = config.agents.claude_cli.model_copy(update={"cli_path": "/nonexistent/claude"})
    agents = config.agents.model_copy(update={"claude_cli": cli})
    spec = AgentSpec(name="a1", prompts=["hi"], backend="claude_cli")
    with pytest.raises(RuntimeError, match="not on PATH"):
        await run_agent(spec, config.model_copy(update={"agents": agents}), run_mode="local", run_id="r1")
    record = json.loads((config.runs_dir / "r1" / "run.json").read_text())
    assert record["status"] == "failed"


def test_agent_env_scrubs_keys() -> None:
    base = {"PATH": "/bin", "ANTHROPIC_API_KEY": "x", "RUNPOD_API_KEY": "y", "SECRET_THING": "z"}
    env = build_agent_env({"RUNPOD_API_KEY": "y"}, base=base)
    assert env["PATH"] == "/bin"
    assert not {"ANTHROPIC_API_KEY", "RUNPOD_API_KEY", "SECRET_THING"} & env.keys()


def test_gpu_tier_never_falls_back_to_cpu() -> None:
    chain = ["cpu3g-2-8", "NVIDIA RTX A4000"]
    assert chain_for_tier(chain, "gpu_basic") == ["NVIDIA RTX A4000"]
    assert chain_for_tier(["NVIDIA L4", "cpu3g-2-8"], "cpu_basic") == ["cpu3g-2-8", "NVIDIA L4"]
