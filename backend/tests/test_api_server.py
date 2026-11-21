"""The local API server: token and origin rules, run lifecycle, replay, progress, stop, messages."""

from __future__ import annotations

import asyncio
import functools
import json
import subprocess
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from aiohttp import ClientResponse
from aiohttp.test_utils import TestClient, TestServer

from chipin_backend.agents.types import AgentEvent
from chipin_backend.api.config import ApiConfig, load_api_config
from chipin_backend.api.events import STAGES, EventLog
from chipin_backend.api.manager import API_RECORD_FILE, RunManager
from chipin_backend.api.progress import ProgressTailer, write_helper
from chipin_backend.api.server import TOKEN_HEADER, create_app, serve
from chipin_backend.api.translate import Translator, tool_summary
from chipin_backend.cli import _parser
from chipin_backend.config import BackendConfig
from chipin_backend.llm import summarise as summarise_mod
from chipin_backend.runs import JsonlEventSink, RunDir, RunRecord

TOKEN = "test-session-token"
AUTH = {TOKEN_HEADER: TOKEN}


def _config(config: BackendConfig) -> BackendConfig:
    """Flex without the macOS check, so the suite runs on any host."""
    flex = config.compute.flex.model_copy(update={"require_macos": False})
    return config.model_copy(update={"compute": config.compute.model_copy(update={"flex": flex})})


def _api(step_s: float) -> ApiConfig:
    return ApiConfig(keepalive_s=0.2, progress_poll_s=0.02, stub_step_s=step_s, run_timeout_s=60)


async def _client(config: BackendConfig, step_s: float, agent: str = "stub") -> TestClient:
    app = create_app(_config(config), _api(step_s), token=TOKEN, agent=agent)  # type: ignore[arg-type]
    return TestClient(TestServer(app))


@pytest.fixture
async def client(config: BackendConfig) -> AsyncIterator[TestClient]:
    """A server with the scripted stub agent, fast steps."""
    async with await _client(config, 0.01) as c:
        yield c


@pytest.fixture
async def slow_client(config: BackendConfig) -> AsyncIterator[TestClient]:
    """A server whose stub agent pauses long enough to be stopped or messaged."""
    async with await _client(config, 3.0) as c:
        yield c


async def _start(client: TestClient, prompt: str = "A wristband that spots seizures") -> str:
    resp = await client.post("/api/runs", json={"prompt": prompt, "preset": "lite"}, headers=AUTH)
    assert resp.status == 201, await resp.text()
    body = await resp.json()
    assert body["status"] == "running"
    return str(body["id"])


async def _read_stream(resp: ClientResponse, *, until: str = "run.finished") -> list[dict[str, Any]]:
    """Events of an SSE response up to the first event of type ``until``."""
    events: list[dict[str, Any]] = []
    ids: list[int] = []
    async with asyncio.timeout(20):
        async for raw in resp.content:
            line = raw.decode().rstrip("\n")
            if line.startswith("id: "):
                ids.append(int(line[4:]))
            elif line.startswith("data: "):
                events.append(json.loads(line[6:]))
                if events[-1]["type"] == until:
                    break
    assert ids == [e["seq"] for e in events]
    return events


async def _events(client: TestClient, run_id: str, **params: str) -> list[dict[str, Any]]:
    resp = await client.get(f"/api/runs/{run_id}/events", params={"token": TOKEN, **params})
    assert resp.status == 200
    assert resp.headers["Content-Type"].startswith("text/event-stream")
    return await _read_stream(resp)


# ---- token and origin rules ----


async def test_health_needs_no_token(client: TestClient) -> None:
    resp = await client.get("/api/health")
    assert resp.status == 200
    assert await resp.json() == {"ok": True, "version": 1, "defaults": {"agent": "stub", "runner": "local"}}


async def test_default_agent_is_claude_on_this_mac(config: BackendConfig) -> None:
    app = create_app(_config(config), _api(0.01), token=TOKEN)
    async with TestClient(TestServer(app)) as c:
        body = await (await c.get("/api/health")).json()
    assert body["defaults"] == {"agent": "claude", "runner": "local"}


@pytest.mark.parametrize("headers", [{}, {TOKEN_HEADER: "wrong"}])
async def test_api_without_the_token_is_401(client: TestClient, headers: dict[str, str]) -> None:
    assert (await client.get("/api/runs", headers=headers)).status == 401
    assert (await client.post("/api/runs", json={"prompt": "x"}, headers=headers)).status == 401
    assert (await client.get("/api/runs/20260101-000000-abcdef/events", headers=headers)).status == 401
    assert (await client.get("/api/runs", headers=AUTH)).status == 200


async def test_token_in_query_only_for_the_event_stream(client: TestClient) -> None:
    assert (await client.get("/api/runs", params={"token": TOKEN})).status == 401


@pytest.mark.parametrize(
    "origin", ["https://chipin.space", "http://127.0.0.1:5500", "http://localhost:3000", "http://localhost"]
)
async def test_preflight_from_an_allowed_origin(client: TestClient, origin: str) -> None:
    resp = await client.options(
        "/api/runs",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": f"content-type,{TOKEN_HEADER.lower()}",
        },
    )
    assert resp.status == 204
    assert resp.headers["Access-Control-Allow-Origin"] == origin
    assert TOKEN_HEADER in resp.headers["Access-Control-Allow-Headers"]
    assert "Content-Type" in resp.headers["Access-Control-Allow-Headers"]
    assert "POST" in resp.headers["Access-Control-Allow-Methods"]
    get = await client.get("/api/runs", headers={"Origin": origin, **AUTH})
    assert get.headers["Access-Control-Allow-Origin"] == origin


@pytest.mark.parametrize(
    "origin", ["https://evil.example", "http://chipin.space", "https://chipin.space.evil.example", "null"]
)
async def test_a_disallowed_origin_gets_no_cors_grant(client: TestClient, origin: str) -> None:
    pre = await client.options(
        "/api/runs", headers={"Origin": origin, "Access-Control-Request-Method": "POST"}
    )
    assert "Access-Control-Allow-Origin" not in pre.headers
    assert pre.status == 403
    post = await client.post("/api/runs", json={"prompt": "x"}, headers={"Origin": origin, **AUTH})
    assert post.status == 403
    assert "Access-Control-Allow-Origin" not in post.headers


async def test_binds_to_loopback_only(config: BackendConfig) -> None:
    app = create_app(_config(config), _api(0.01), token=TOKEN)
    runner = await serve(app, 0)
    try:
        assert runner.addresses
        assert all(addr[0] == "127.0.0.1" for addr in runner.addresses)
    finally:
        await runner.cleanup()


async def test_serves_a_frontend_folder(config: BackendConfig, tmp_path: Path) -> None:
    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text("<h1>ChipIn</h1>")
    (site / "app.js").write_text("console.log(1)")
    app = create_app(_config(config), _api(0.01), token=TOKEN, frontend=site)
    async with TestClient(TestServer(app)) as c:
        assert "ChipIn" in await (await c.get("/")).text()
        assert "console" in await (await c.get("/app.js")).text()
        assert (await c.get("/api/health")).status == 200
        assert (await c.get("/api/runs")).status == 401


def test_serve_command_defaults() -> None:
    args = _parser().parse_args(["serve"])
    assert (args.command, args.agent, args.runner, args.port, args.frontend) == (
        "serve",
        "claude",
        "local",
        None,
        None,
    )
    assert load_api_config().port == 8797
    assert _parser().parse_args(["serve", "--config", "x.yaml"]).config == Path("x.yaml")


# ---- run lifecycle ----


async def test_run_lifecycle_with_the_stub(client: TestClient, config: BackendConfig) -> None:
    run_id = await _start(client)
    events = await _events(client, run_id)

    assert [e["seq"] for e in events] == list(range(1, len(events) + 1))
    assert all(e["run_id"] == run_id and e["ts"] for e in events)
    first, last = events[0], events[-1]
    assert first["type"] == "run.started"
    assert (first["agent"], first["runner"]) == ("stub", "local")
    assert first["prompt"] == "A wristband that spots seizures"
    assert last == {**last, "type": "run.finished", "status": "succeeded"}

    stages = [(e["name"], e["state"]) for e in events if e["type"] == "stage"]
    assert stages == [(s, state) for s in STAGES for state in ("started", "done")]
    metrics = {e["key"]: e["value"] for e in events if e["type"] == "metric"}
    assert metrics == {"candidates": 3, "round": 2, "gates": 2330, "patients_pass": 41, "patients_total": 48}
    assert any(e["type"] == "status" and e["text"].startswith("ChipIn is") for e in events)
    assert any(e["type"] == "message" and e["role"] == "agent" and e["author"] == "ChipIn" for e in events)
    tools = [e for e in events if e["type"] == "tool"]
    assert tools, "the stub's Read and Write calls show as tools"
    assert not any("./progress" in e["summary"] for e in tools), "progress calls are not tools"
    assert {"started", "done"} <= {e["state"] for e in tools}
    assert any(e["summary"] == "Read brief.md" for e in tools)
    artifacts = [e for e in events if e["type"] == "artifact"]
    assert artifacts == [
        {**artifacts[0], "name": "report.md", "kind": "report", "path": "workspace/report.md"}
    ]
    assert any(e["type"] == "cost" and e["usd"] == 0.0 for e in events)

    run_dir = config.resolved_runs_dir() / run_id
    assert (run_dir / artifacts[0]["path"]).is_file()
    on_disk = [json.loads(line) for line in (run_dir / "events.jsonl").read_text().splitlines()]
    assert on_disk == events
    run_record = json.loads((run_dir / "run.json").read_text())
    assert (run_record["run_mode"], run_record["status"]) == ("flex", "succeeded")
    assert run_record["config"] and run_record["duration_s"] is not None and run_record["result"]
    assert "seizures" in (run_dir / "workspace" / "brief.md").read_text()

    detail = await (await client.get(f"/api/runs/{run_id}", headers=AUTH)).json()
    assert detail["status"] == "succeeded"
    assert detail["finished_at"] and detail["started_at"]
    assert detail["cost"]["usd"] == 0.0
    assert "Stub run complete" in detail["summary"]
    assert "bullets" not in detail, "no OpenRouter key in the tests: no run summary"


async def test_run_summary_reaches_the_record_and_run_finished(
    client: TestClient, config: BackendConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every run through run_agent is summarised, the dashboard's runs too."""
    bullets = "- Task: a seizure wristband.\n- Stub stages all done.\n- Report written."
    reply = {
        "model": "openai/gpt-oss-120b",
        "provider": "X",
        "choices": [{"message": {"role": "assistant", "content": bullets}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "cost": 2e-5},
    }
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=reply))
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-key-for-api-summary-test")
    monkeypatch.setattr(
        summarise_mod.httpx, "AsyncClient", functools.partial(httpx.AsyncClient, transport=transport)
    )
    run_id = await _start(client)
    last = (await _events(client, run_id))[-1]
    assert (last["type"], last["bullets"]) == ("run.finished", bullets)
    assert "Stub run complete" in last["summary"], "the agent's last message stays the summary"
    record = json.loads((config.resolved_runs_dir() / run_id / "run.json").read_text())
    assert record["result"]["summary"]["run"]["text"] == bullets
    assert record["llm_cost_usd"] == pytest.approx(2e-5)


async def test_runs_listed_newest_first(client: TestClient) -> None:
    first = await _start(client, "first")
    await _events(client, first)
    second = await _start(client, "second")
    await _events(client, second)
    runs = (await (await client.get("/api/runs", headers=AUTH)).json())["runs"]
    assert [r["id"] for r in runs] == [second, first]
    assert set(runs[0]) == {"id", "prompt", "status", "started_at", "finished_at"}


async def test_replay_from_a_seq_and_after_last_event_id(client: TestClient) -> None:
    run_id = await _start(client)
    full = await _events(client, run_id)
    tail = await _events(client, run_id, **{"from": "5"})
    assert tail == full[4:]
    resp = await client.get(
        f"/api/runs/{run_id}/events", params={"token": TOKEN, "from": "1"}, headers={"Last-Event-ID": "9"}
    )
    assert (await _read_stream(resp)) == full[9:]


async def test_replay_survives_a_server_restart(config: BackendConfig) -> None:
    async with await _client(config, 0.01) as c1:
        run_id = await _start(c1)
        before = await _events(c1, run_id)
    async with await _client(config, 0.01) as c2:
        assert await _events(c2, run_id) == before
        assert (await (await c2.get(f"/api/runs/{run_id}", headers=AUTH)).json())["status"] == "succeeded"


async def test_bad_requests(client: TestClient) -> None:
    assert (await client.post("/api/runs", json={}, headers=AUTH)).status == 400
    assert (
        await client.post("/api/runs", json={"prompt": "x", "preset": "huge"}, headers=AUTH)
    ).status == 400
    on_demand = await client.post("/api/runs", json={"prompt": "x", "machine": "on_demand"}, headers=AUTH)
    assert on_demand.status == 400
    assert (await client.get("/api/runs/20260101-000000-abcdef", headers=AUTH)).status == 404
    assert (await client.get("/api/runs/..%2F..%2Fetc", headers=AUTH)).status == 404


async def test_files_and_answers_reach_the_brief(client: TestClient, config: BackendConfig) -> None:
    body = {
        "prompt": "ECG patch",
        "answers": {"wearer": "adults"},
        "files": [{"name": "ecg.csv", "size": 1024, "header": "t,lead_ii"}],
    }
    resp = await client.post("/api/runs", json=body, headers=AUTH)
    run_id = (await resp.json())["id"]
    await _events(client, run_id)
    brief = (config.resolved_runs_dir() / run_id / "workspace" / "brief.md").read_text()
    assert "wearer" in brief and "ecg.csv" in brief and "t,lead_ii" in brief and "NOT uploaded" in brief


# ---- stop and messages ----


async def test_stop_a_running_run(slow_client: TestClient, config: BackendConfig) -> None:
    run_id = await _start(slow_client)
    resp = await slow_client.get(f"/api/runs/{run_id}/events", params={"token": TOKEN})
    await _read_stream(resp, until="stage")
    stop = await slow_client.post(f"/api/runs/{run_id}/stop", headers=AUTH)
    assert stop.status == 202
    rest = await _read_stream(resp)
    assert rest[-1]["type"] == "run.finished" and rest[-1]["status"] == "stopped"
    detail = await (await slow_client.get(f"/api/runs/{run_id}", headers=AUTH)).json()
    assert detail["status"] == "stopped"
    assert json.loads((config.resolved_runs_dir() / run_id / "run.json").read_text())["status"] == "stopped"
    again = await slow_client.post(f"/api/runs/{run_id}/stop", headers=AUTH)
    assert again.status == 202


async def test_a_user_message_reaches_the_agent(slow_client: TestClient) -> None:
    run_id = await _start(slow_client)
    resp = await slow_client.get(f"/api/runs/{run_id}/events", params={"token": TOKEN})
    await _read_stream(resp, until="stage")
    sent = await slow_client.post(
        f"/api/runs/{run_id}/messages", json={"text": "use 8-bit weights"}, headers=AUTH
    )
    assert sent.status == 202
    seen: list[dict[str, Any]] = []
    async with asyncio.timeout(15):
        while not any(e["type"] == "message" and "Noted your message" in e.get("text", "") for e in seen):
            seen += await _read_stream(resp, until="message")
    user = [e for e in seen if e["type"] == "message" and e["role"] == "user"]
    assert user and user[0]["text"] == "use 8-bit weights"
    agent_reply = next(e for e in seen if "Noted your message" in e.get("text", ""))
    assert "use 8-bit weights" in agent_reply["text"]
    await slow_client.post(f"/api/runs/{run_id}/stop", headers=AUTH)
    await _read_stream(resp)
    late = await slow_client.post(f"/api/runs/{run_id}/messages", json={"text": "hi"}, headers=AUTH)
    assert late.status == 409


async def test_message_needs_text(slow_client: TestClient) -> None:
    run_id = await _start(slow_client)
    resp = await slow_client.post(f"/api/runs/{run_id}/messages", json={"text": " "}, headers=AUTH)
    assert resp.status == 400
    await slow_client.post(f"/api/runs/{run_id}/stop", headers=AUTH)


# ---- progress helper -> events ----


async def test_progress_helper_to_events(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    progress_file = tmp_path / "progress.jsonl"
    helper = write_helper(workspace, progress_file)
    calls = [
        (["stage", "propose", "started"], 0),
        (["stage", "finetune", "started", "2"], 0),
        (["metric", "gates", "2330"], 0),
        (["metric", "power", "1.5", "mW"], 0),
        (["status", "ChipIn is wiring the weights into gates"], 0),
        (["artifact", "chip.v", "chip"], 0),
        (["stage", "verify", "skipped", "no", "recordings", "attached"], 0),
        (["stage", "compile", "skipped"], 2),
        (["stage", "dance", "started"], 2),
        (["metric", "gates", "many"], 2),
        (["artifact", "x", "movie"], 2),
        ([], 2),
    ]
    for argv, code in calls:
        proc = subprocess.run([str(helper), *argv], cwd=workspace, capture_output=True, text=True, timeout=30)
        assert proc.returncode == code, (argv, proc.stderr)
    with progress_file.open("a") as handle:
        handle.write(
            '{"type": "stage", "name": "nope", "state": "started"}\n'
            '{"type": "stage", "name": "spec", "state": "skipped"}\n'
            'not json\n{"type": "status"'
        )
    log = EventLog(tmp_path / "events.jsonl", "r1", asyncio.get_running_loop())
    tailer = ProgressTailer(progress_file, log, tmp_path, workspace)
    tailer.drain()
    got = [{k: v for k, v in e.items() if k not in {"seq", "ts", "run_id"}} for e in log.since(1)]
    assert got == [
        {"type": "stage", "name": "propose", "stage": "propose", "state": "started"},
        {"type": "stage", "name": "finetune", "stage": "finetune", "state": "started", "round": 2},
        {"type": "metric", "key": "gates", "value": 2330},
        {"type": "metric", "key": "power", "value": 1.5, "unit": "mW"},
        {"type": "status", "text": "ChipIn is wiring the weights into gates"},
        {"type": "artifact", "name": "chip.v", "kind": "chip", "path": "workspace/chip.v"},
        {
            "type": "stage",
            "name": "verify",
            "stage": "verify",
            "state": "skipped",
            "reason": "no recordings attached",
        },
    ]
    # replay: a fresh log over the same file sees the skipped event unchanged
    replay = EventLog(tmp_path / "events.jsonl", "r1", asyncio.get_running_loop())
    assert replay.since(1)[-1]["state"] == "skipped"
    assert replay.since(1)[-1]["reason"] == "no recordings attached"
    with progress_file.open("a") as handle:
        handle.write(', "text": "late line"}\n')
    tailer.drain()
    assert log.since(8)[0]["text"] == "late line"


# ---- translation ----


async def test_translation_of_agent_events(tmp_path: Path) -> None:
    log = EventLog(tmp_path / "events.jsonl", "r1", asyncio.get_running_loop())
    tr = Translator(log, JsonlEventSink(tmp_path / "raw.jsonl"), tmp_path)

    def ev(kind: str, **data: Any) -> None:
        tr.emit(AgentEvent(kind, "chipin", data))  # type: ignore[arg-type]

    ev("agent_start", backend="claude_cli")
    ev("text", text="Reading the brief.")
    ev("thinking", text="hidden")
    ev("tool_call", tool="Bash", input={"command": "./progress stage spec started"}, call_id="p1")
    ev("tool_result", call_id="p1", output="ok", is_error=False)
    ev("tool_call", tool="Bash", input={"command": "python train.py\n--epochs 3"}, call_id="b1")
    ev("tool_result", call_id="b1", output="Traceback: boom", is_error=True)
    ev("cost", usd=0.12, input_tokens=100, output_tokens=20)
    ev("error", message="API error 500")
    types = [e["type"] for e in log.since(1)]
    assert types == ["status", "message", "tool", "tool", "cost", "error"]
    started, failed = log.since(3)[0], log.since(4)[0]
    assert (started["summary"], started["state"]) == ("Ran python train.py", "started")
    assert (failed["state"], failed["detail"], failed["name"]) == ("failed", "Traceback: boom", "Bash")
    assert log.since(5)[0] == {**log.since(5)[0], "usd": 0.12, "tokens_in": 100, "tokens_out": 20}
    assert tr.error_emitted
    assert len((tmp_path / "raw.jsonl").read_text().splitlines()) == 9
    ev("tool_call", tool="Bash", input={"command": "cat log"}, call_id="b2")
    ev(
        "tool_result",
        call_id="b2",
        output=f"\x1b[38;5;174mClaude\x1b[39m at {tmp_path}/spec.md\x07",
        is_error=False,
    )
    ev("text", text="Done: three designs.")
    assert log.since(8)[0]["detail"] == "Claude at spec.md"
    assert tr.last_text == "Done: three designs."


def test_tool_summaries(tmp_path: Path) -> None:
    assert tool_summary("Read", {"file_path": str(tmp_path / "a" / "b.py")}, tmp_path) == "Read a/b.py"
    assert tool_summary("Bash", {"command": "ls", "description": "List files"}) == "Ran List files"
    assert (
        tool_summary("WebSearch", {"query": "EEG seizure dataset"})
        == "Searched the web for EEG seizure dataset"
    )
    assert len(tool_summary("Bash", {"command": "x" * 500})) <= 120


# ---- restart ----


async def test_a_run_left_running_is_closed_on_load(config: BackendConfig) -> None:
    folder = config.resolved_runs_dir() / "20260101-000000-abcdef"
    (folder / "workspace").mkdir(parents=True)
    record = {
        "id": folder.name,
        "prompt": "p",
        "status": "running",
        "started_at": "2026-01-01T00:00:00+00:00",
    }
    (folder / API_RECORD_FILE).write_text(json.dumps(record))
    RunDir(folder).write_record(RunRecord(run_id=folder.name, run_mode="flex", agent={}, status="running"))
    (folder / "events.jsonl").write_text(
        json.dumps({"seq": 1, "type": "run.started", "run_id": folder.name}) + "\n"
    )
    manager = RunManager(_config(config), _api(0.01))
    manager.load()
    item = manager.get(folder.name)
    assert item.record["status"] == "failed"
    assert [e["type"] for e in item.log.since(1)] == ["run.started", "error", "run.finished"]
    assert item.log.since(3)[0]["seq"] == 3
    assert RunDir(folder).read_record().status == "failed"
