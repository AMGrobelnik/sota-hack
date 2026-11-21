"""The worker protocol end to end on localhost: the real app and the real client."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from aiohttp.test_utils import TestServer

from chipmonk_backend.agents.types import AgentSpec
from chipmonk_backend.compute.runpod.worker import WorkerClient, WorkerUnreachableError, create_app
from chipmonk_backend.config import BackendConfig
from script_backend import use_script_backend

TOKEN = "per-pod-test-token"
LOGS_AND_WRITES = """
import pathlib
for i in range(3):
    print(f"epoch {i}")
pathlib.Path("models").mkdir()
pathlib.Path("models/best.txt").write_text("smallest chip")
"""


@pytest.fixture
async def server(config: BackendConfig, tmp_path: Path) -> AsyncIterator[TestServer]:
    pod_config = config.model_copy(update={"runs_dir": tmp_path / "pod_runs"})
    server = TestServer(create_app(pod_config, token=TOKEN))
    await server.start_server()
    yield server
    await server.close()


def _client(server: TestServer, token: str = TOKEN) -> WorkerClient:
    client = WorkerClient(str(server.make_url("")), token=token)
    client.retry_delay_s = client.reconnect_delay_s = 0.01
    client.max_retries = client.max_reconnects = 2
    return client


async def test_job_round_trip(server: TestServer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    use_script_backend(monkeypatch)
    client = _client(server)
    await client.wait_healthy(timeout_s=5, interval_s=0.05)
    await client.submit(AgentSpec(name="a", prompts=[LOGS_AND_WRITES], backend="script"), run_id="r1")  # type: ignore[arg-type]

    events = [event async for event in client.events()]
    result = await client.result()
    files = await client.download_outputs(tmp_path / "local")
    await client.aclose()

    assert [e.data["text"] for e in events if e.kind == "text"] == ["epoch 0", "epoch 1", "epoch 2"]
    assert events[0].kind == "agent_start" and events[-1].kind == "agent_end"
    assert not result.failed and result.files == ["models/best.txt"]
    assert files == ["models/best.txt"]
    assert (tmp_path / "local" / "models" / "best.txt").read_text() == "smallest chip"


async def test_events_resume_from_since(server: TestServer) -> None:
    client = _client(server)
    await client.submit(AgentSpec(name="a", prompts=["hi"], backend="stub"), run_id="r2")
    everything = [e async for e in client.events()]
    tail = [e async for e in client.events(since=2)]
    await client.aclose()
    assert tail == everything[2:]


async def test_every_route_needs_the_token(server: TestServer) -> None:
    async with httpx.AsyncClient(base_url=str(server.make_url(""))) as raw:
        for method, path in [("GET", "/health"), ("POST", "/job"), ("GET", "/events"), ("GET", "/result")]:
            assert (await raw.request(method, path)).status_code == 401
    wrong = _client(server, token="wrong")
    assert not await wrong.is_healthy()
    await wrong.aclose()


async def test_one_job_per_worker_and_bad_jobs_are_refused(server: TestServer) -> None:
    client = _client(server)
    with pytest.raises(RuntimeError, match="HTTP 400"):
        await client.submit(AgentSpec(name="a", prompts=["hi"], backend="stub"), run_id="")  # type: ignore[arg-type]
    await client.submit(AgentSpec(name="a", prompts=["hi"], backend="stub"), run_id="r3")
    with pytest.raises(RuntimeError, match="409"):
        await client.submit(AgentSpec(name="b", prompts=["hi"], backend="stub"), run_id="r4")
    await client.aclose()


async def test_a_worker_that_goes_away_mid_job_is_reported(config: BackendConfig, tmp_path: Path) -> None:
    pod_config = config.model_copy(update={"runs_dir": tmp_path / "pod_runs"})
    server = TestServer(create_app(pod_config, token=TOKEN))
    await server.start_server()
    client = _client(server)
    await client.submit(AgentSpec(name="a", prompts=["hi"], backend="stub"), run_id="r5")
    await server.close()
    with pytest.raises(WorkerUnreachableError):
        await client.result(poll_interval_s=0.01)
    await client.aclose()
