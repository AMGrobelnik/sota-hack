"""Fan-out: an orchestrator runs one batch of parallel subagents per stage through ``./subagent``.

Every test uses the scripted stub agent: an orchestrator whose brief holds
``$ `` lines runs them as shell commands, so it can start, wait for, merge
and list stub subagents exactly as a model would; without a script the stub
orchestrator runs all five batches itself. No model is called; the Pro and
Ultra batch sizes (10 and 20) are exercised here only.
"""

from __future__ import annotations

import asyncio
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
from aiohttp.test_utils import TestClient, TestServer

from chipin_backend.api.config import ApiConfig, FanoutConfig
from chipin_backend.api.events import STAGES
from chipin_backend.api.fanout import BATCH_STAGES, ID_ENV, STATE_FILE
from chipin_backend.api.manager import API_RECORD_FILE, ApiRun, RunManager, standing_instructions
from chipin_backend.api.server import TOKEN_HEADER, create_app
from chipin_backend.cli import _parser
from chipin_backend.config import BackendConfig
from chipin_backend.runs import RunDir

TOKEN = "test-session-token"
AUTH = {TOKEN_HEADER: TOKEN}
ON = {"enabled": True, "width": 2}


def _config(config: BackendConfig) -> BackendConfig:
    """Flex without the macOS check, so the suite runs on any host."""
    flex = config.compute.flex.model_copy(update={"require_macos": False})
    return config.model_copy(update={"compute": config.compute.model_copy(update={"flex": flex})})


def _api(step_s: float = 0.01, **fanout: Any) -> ApiConfig:
    return ApiConfig(
        progress_poll_s=0.02, stub_step_s=step_s, run_timeout_s=60, fanout=FanoutConfig(**fanout)
    )


def _manager(config: BackendConfig, step_s: float = 0.01, **fanout: Any) -> RunManager:
    return RunManager(_config(config), _api(step_s, **fanout), agent="stub", summary=False)


def _script(*lines: str) -> str:
    """An orchestrator brief: one ``$ `` shell line per command."""
    return "A seizure flag, scripted.\n" + "\n".join(f"$ {line}" for line in lines)


async def _run(
    manager: RunManager, prompt: str, fanout: Any = ON, preset: str | None = "lite"
) -> tuple[ApiRun, list[dict[str, Any]]]:
    body: dict[str, Any] = {"prompt": prompt, "preset": preset}
    if fanout is not None:
        body["fanout"] = fanout
    item = manager.start(body)
    assert item.task is not None
    async with asyncio.timeout(90):
        await item.task
    return item, item.log.since(1)


def _of(events: list[dict[str, Any]], type_: str, **match: Any) -> list[dict[str, Any]]:
    return [e for e in events if e["type"] == type_ and all(e.get(k) == v for k, v in match.items())]


def _outputs(item: ApiRun) -> str:
    """Everything the orchestrator's shell commands printed, in full (its raw agent events)."""
    raw = [json.loads(line) for line in item.run.events_path.read_text().splitlines()]
    return "\n".join(str(e["data"].get("output", "")) for e in raw if e["kind"] == "tool_result")


async def test_two_subagents_run_at_the_same_time(config: BackendConfig) -> None:
    manager = _manager(config)
    item, events = await _run(
        manager,
        _script(
            './subagent start propose "$ sleep 1; ./progress metric gates 120 gates --chip d-a; echo A" '
            "--name family-a",
            './subagent start propose "$ sleep 1; ./progress metric gates 90 gates --chip d-b; echo B" '
            "--name family-b",
            "./subagent wait --all",
        ),
    )
    assert item.record["status"] == "succeeded"
    seqs = [(e["type"], e.get("id")) for e in events]
    started = [seqs.index(("subagent.started", i)) for i in ("a1", "a2")]
    finished = [seqs.index(("subagent.finished", i)) for i in ("a1", "a2")]
    assert max(started) < min(finished), "both were running before either finished"
    first = _of(events, "subagent.started", id="a1")[0]
    assert (first["name"], first["stage"], first["harness"]) == ("family-a", "propose", "stub")
    assert first["strategy"].startswith("$ sleep 1; ./progress metric gates 120")
    assert "agent" not in first and first["brief"].startswith("$ sleep 1")
    tools = _of(events, "tool", state="started")
    assert {e.get("agent") for e in tools} == {None, "a1", "a2"}
    a1_done = next(i for i, e in enumerate(events) if e["type"] == "tool" and e.get("agent") == "a1")
    a2_start = next(i for i, e in enumerate(events) if e["type"] == "tool" and e.get("agent") == "a2")
    assert a2_start < finished[0], "the second's tool call began while the first was running"
    assert a1_done < finished[0]
    metrics = {(e["agent"], e["chip"], e["value"]) for e in _of(events, "metric")}
    assert metrics == {("a1", "d-a", 120), ("a2", "d-b", 90)}
    assert all("agent" not in e for e in _of(events, "stage")), "stages are the orchestrator's"
    done = {e["id"]: e for e in _of(events, "subagent.finished")}
    assert {e["state"] for e in done.values()} == {"done"} and done["a2"]["result"] == "ok B"
    assert "All 2 finished" in _outputs(item) and "folder: agents/a1" in _outputs(item)
    folder = item.run.workspace / "agents" / "a1"
    assert (folder / "brief.md").is_file() and (folder / "subagent-result.md").read_text().split() == [
        "ok",
        "A",
    ]
    assert not (folder / "subagent").exists(), "a subagent gets no ./subagent helper"


@pytest.mark.parametrize(("preset", "width"), [("lite", 3), ("pro", 10), ("ultra", 20)])
async def test_a_full_run_has_five_parallel_batches_each_merged(
    config: BackendConfig, preset: str, width: int
) -> None:
    """Per batch stage: every subagent started before the first finished, one merge, then done."""
    item, events = await _run(_manager(config), "A wristband that spots seizures", True, preset)
    assert item.record["status"] == "succeeded"
    assert item.record["fanout"]["width"] == item.record["fanout"]["max_parallel"] == width
    stages = [(e["name"], e["state"]) for e in _of(events, "stage")]
    assert stages == [(s, state) for s in STAGES for state in ("started", "done")]
    seq = {
        (e["type"], e.get("name"), e.get("state")): i for i, e in enumerate(events) if e["type"] == "stage"
    }
    for stage in BATCH_STAGES:
        begun, done = seq[("stage", stage, "started")], seq[("stage", stage, "done")]
        started = [i for i, e in enumerate(events) if e["type"] == "subagent.started" and e["stage"] == stage]
        finished = [
            i for i, e in enumerate(events) if e["type"] == "subagent.finished" and e["stage"] == stage
        ]
        merged = [i for i, e in enumerate(events) if e["type"] == "stage.merged" and e["stage"] == stage]
        assert len(started) == len(finished) == width, stage
        assert begun < min(started) and max(started) < min(finished), f"{stage}: the whole batch ran at once"
        assert len(merged) == 1 and max(finished) < merged[0] < done, stage
        record = events[merged[0]]
        assert record["started"] == record["done"] == width and len(record["kept"]) == 1
        assert record["kept"][0] in record["ids"] and record["seconds"] > 0
        assert all(f"for {stage}" in events[i]["strategy"] for i in started)
    for stage in ("spec", "report"):
        assert not [e for e in events if e["type"] == "subagent.started" and e["stage"] == stage]
    assert len(_of(events, "subagent.finished", state="done")) == 5 * width
    assert len({e["chip"] for e in _of(events, "metric") if e.get("agent")}) == 5 * width
    assert [m["stage"] for m in item.detail_view()["merges"]] == list(BATCH_STAGES)


async def test_fan_out_off_changes_nothing(config: BackendConfig) -> None:
    manager = _manager(config)
    off, off_events = await _run(manager, "A wristband that spots seizures", None)
    off2, off2_events = await _run(manager, "A wristband that spots seizures", {"enabled": False})
    for item, events in ((off, off_events), (off2, off2_events)):
        assert not (item.run.workspace / "subagent").exists()
        assert not (item.run.path / STATE_FILE).exists()
        assert all("agent" not in e for e in events if e["type"] != "run.started")
        assert not any(e["type"].startswith("subagent.") for e in events)
        record = json.loads(item.run.record_path.read_text())
        assert record["agent"]["system_prompt"] == standing_instructions()
        assert "subagents" not in record and "subagent_cost_usd" not in record
        api = json.loads((item.run.path / API_RECORD_FILE).read_text())
        assert "fanout" not in api and "subagents" not in api
        assert "subagents" not in item.detail_view()
    assert Counter(e["type"] for e in off_events) == Counter(e["type"] for e in off2_events)
    assert len(_of(off_events, "cost")) == 1


async def test_fan_out_on_adds_the_orchestrator_paragraph(config: BackendConfig) -> None:
    item, _ = await _run(_manager(config), _script("./subagent list"))
    prompt = json.loads(item.run.record_path.read_text())["agent"]["system_prompt"]
    assert prompt.startswith(standing_instructions().rstrip())
    assert "ONE BATCH of 2 subagents" in prompt and "./subagent merge <stage>" in prompt
    assert "the stub harness" in prompt and "Spec and report are yours alone" in prompt
    first = json.loads(item.run.record_path.read_text())["agent"]["prompts"][0]
    assert "You are this run's orchestrator" in first
    assert item.detail_view()["fanout"]["width"] == 2


async def test_max_parallel_queues_and_max_total_refuses(config: BackendConfig) -> None:
    manager = _manager(config, max_parallel=1, max_total=2)
    item, events = await _run(
        manager,
        _script(
            './subagent start propose "$ sleep 0.4; echo one"',
            './subagent start propose "$ echo two" 2>&1',
            './subagent start propose "$ echo three"; echo "exit=$?"',
            "./subagent wait a1 a2",
        ),
    )
    assert item.record["status"] == "succeeded"
    order = [(e["type"], e.get("id")) for e in events if e["type"].startswith("subagent.")]
    assert order == [
        ("subagent.started", "a1"),
        ("subagent.finished", "a1"),
        ("subagent.started", "a2"),
        ("subagent.finished", "a2"),
    ]
    out = _outputs(item)
    assert "a2 queued" in out
    assert "limit of 2 subagents" in out and "exit=1" in out
    state = json.loads((item.run.path / STATE_FILE).read_text())
    assert sorted(state["agents"]) == ["a1", "a2"]


async def test_a_failing_subagent_does_not_fail_the_run(config: BackendConfig) -> None:
    item, events = await _run(
        _manager(config),
        _script('./subagent start propose "$ echo trying; exit 3"', "./subagent wait a1"),
    )
    assert item.record["status"] == "succeeded"
    finished = _of(events, "subagent.finished", id="a1")[0]
    assert finished["state"] == "failed" and "exit status 3" in finished["error"]
    assert not _of(events, "error"), "a subagent's failure is not an error of the run"
    assert "failed" in _outputs(item)


async def test_wait_returns_at_its_timeout_and_says_wait_again(config: BackendConfig) -> None:
    item, events = await _run(
        _manager(config),
        _script(
            './subagent start propose "$ sleep 1.5; echo late"',
            "./subagent wait a1 --timeout 0.3",
            "./subagent wait a1",
        ),
    )
    first, second = [e["detail"] for e in _of(events, "tool", state="done") if "wait a1" in e["summary"]]
    assert "Still running: a1" in first and "wait a1 again" in first
    assert "All 1 finished" in second and "late" in second
    assert item.record["status"] == "succeeded"


async def test_a_subagent_timing_out_is_reported(config: BackendConfig) -> None:
    manager = _manager(config, subagent={"timeout_s": 1})
    _, events = await _run(manager, _script('./subagent start propose "$ sleep 5"', "./subagent wait a1"))
    assert _of(events, "subagent.finished", id="a1")[0]["state"] == "timed out"


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


async def test_stopping_the_run_stops_a_whole_ultra_batch_with_no_process_left(config: BackendConfig) -> None:
    manager = _manager(config)
    start = "./subagent start propose '$ sleep 60 & echo $! > pid; wait' >/dev/null &"
    item = manager.start(
        {"prompt": _script(" ".join([start] * 20) + " wait", "sleep 60"), "preset": "ultra", "fanout": True}
    )
    pids: list[Path] = []
    async with asyncio.timeout(30):
        while len(pids) < 20:
            pids = list((item.run.workspace / "agents").glob("a*/pid"))
            pids = [p for p in pids if p.read_text().strip()]
            await asyncio.sleep(0.1)
    sleepers = [int(p.read_text()) for p in pids]
    assert all(_alive(pid) for pid in sleepers)
    events = item.log.since(1)
    assert len(_of(events, "subagent.started")) == 20 and not _of(events, "subagent.finished")
    await manager.stop(item.id)
    assert item.task is not None
    async with asyncio.timeout(20):
        await item.task
    events = item.log.since(1)
    assert events[-1]["type"] == "run.finished" and events[-1]["status"] == "stopped"
    finished = _of(events, "subagent.finished")
    assert len(finished) == 20 and {e["state"] for e in finished} == {"stopped"}
    assert json.loads(item.run.record_path.read_text())["subagents"][0]["state"] == "stopped"
    for _ in range(50):
        if not any(_alive(pid) for pid in sleepers):
            break
        await asyncio.sleep(0.1)
    assert not [pid for pid in sleepers if _alive(pid)], "no subagent process is left"


async def test_costs_are_summed_and_the_run_lists_its_subagents(config: BackendConfig) -> None:
    item, events = await _run(
        _manager(config),
        _script(
            './subagent start propose "$ echo a # cost 0.01"',
            './subagent start compile "$ echo b # cost 0.02" --name second',
            "./subagent wait --all # cost 0.005",
        ),
    )
    tagged = {e["agent"]: e["usd"] for e in _of(events, "cost") if "agent" in e}
    assert tagged == {"a1": 0.01, "a2": 0.02}
    total = [e for e in _of(events, "cost") if "agent" not in e][-1]
    assert total["usd"] == pytest.approx(0.035) and total["subagents_usd"] == pytest.approx(0.03)
    assert item.record["cost"]["usd"] == pytest.approx(0.035)
    record = json.loads(item.run.record_path.read_text())
    assert record["subagent_cost_usd"] == pytest.approx(0.03)
    assert [(s["id"], s["stage"], s["state"]) for s in record["subagents"]] == [
        ("a1", "propose", "done"),
        ("a2", "compile", "done"),
    ]
    detail = item.detail_view()
    assert [s["name"] for s in detail["subagents"]] == ["propose-1", "second"]
    assert detail["subagents"][1]["cost_usd"] == 0.02


async def test_a_subagent_cannot_start_subagents_or_mark_stages(config: BackendConfig) -> None:
    _, events = await _run(
        _manager(config),
        _script(
            './subagent start propose "$ ../../subagent list"',
            './subagent start propose "$ ./progress stage propose started"',
            "./subagent wait --all",
        ),
    )
    finished = {e["id"]: e for e in _of(events, "subagent.finished")}
    assert finished["a1"]["state"] == "failed" and "exit status 1" in finished["a1"]["error"]
    assert "only the orchestrator" in finished["a1"]["result"]
    assert finished["a2"]["state"] == "failed" and "orchestrator does" in finished["a2"]["result"]
    assert all("agent" not in e for e in _of(events, "stage"))


async def test_bad_starts_are_refused_with_a_reason(
    config: BackendConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-key-never-sent")
    manager = _manager(config, max_usd=0.0)
    item, events = await _run(
        manager,
        _script(
            './subagent start nonsense "x"; echo "exit=$?"',
            './subagent start propose "  "; echo "exit=$?"',
            './subagent start propose "x" --agent openrouter 2>&1; echo "exit=$?"',
        ),
    )
    out = _outputs(item)
    assert out.count("exit=2") == 2, "the helper checks its own arguments"
    assert "spending limit" in out and "exit=1" in out
    assert item.record["status"] == "succeeded"
    assert not _of(events, "subagent.started")


async def test_an_openrouter_subagent_without_its_key_is_refused(config: BackendConfig) -> None:
    item, _ = await _run(
        _manager(config), _script('./subagent start propose "x" --agent openrouter 2>&1; echo "exit=$?"')
    )
    out = _outputs(item)
    assert "OPENROUTER_API_KEY" in out and "exit=1" in out


async def test_file_routes_serve_a_subagents_files(config: BackendConfig) -> None:
    app = create_app(_config(config), _api(), token=TOKEN, agent="stub")
    async with TestClient(TestServer(app)) as client:
        body = {
            "prompt": _script(
                './subagent start propose "$ echo hello > note.md && ./progress artifact note.md file"',
                "./subagent wait a1",
            ),
            "fanout": ON,
        }
        resp = await client.post("/api/runs", json=body, headers=AUTH)
        assert resp.status == 201, await resp.text()
        run_id = (await resp.json())["id"]
        for _ in range(400):
            detail = await (await client.get(f"/api/runs/{run_id}", headers=AUTH)).json()
            if detail["status"] != "running":
                break
            await asyncio.sleep(0.05)
        assert detail["status"] == "succeeded"
        assert detail["subagents"][0]["path"] == "workspace/agents/a1"
        events_path = config.resolved_runs_dir() / run_id / "events.jsonl"
        events = [json.loads(line) for line in events_path.read_text().splitlines()]
        artifact = _of(events, "artifact", agent="a1")[0]
        assert artifact["path"] == "workspace/agents/a1/note.md"
        got = await client.get(f"/api/runs/{run_id}/file", params={"path": artifact["path"]}, headers=AUTH)
        assert got.status == 200 and (await got.text()) == "hello\n"
        files = {
            f["path"]
            for f in (await (await client.get(f"/api/runs/{run_id}/files", headers=AUTH)).json())["files"]
        }
        assert "workspace/agents/a1/note.md" in files and "workspace/agents/a1/brief.md" in files
        assert not {"workspace/subagent", "workspace/agents/a1/progress"} & files, "helpers are not listed"
        for bad in ("subagents.json", "subagents/a1/progress.jsonl", "workspace/agents/a1/../../../api.json"):
            refused = await client.get(f"/api/runs/{run_id}/file", params={"path": bad}, headers=AUTH)
            assert refused.status == 400, bad


async def test_fanout_requests_are_checked(config: BackendConfig) -> None:
    app = create_app(_config(config), _api(), token=TOKEN, agent="stub")
    async with TestClient(TestServer(app)) as client:
        for fanout in (
            {"width": 0},
            {"width": 99},
            {"colour": "red"},
            "yes",
            {"subagent": {"agent": "gpt"}},
            {"max_usd": 99},
        ):
            resp = await client.post("/api/runs", json={"prompt": "x", "fanout": fanout}, headers=AUTH)
            assert resp.status == 400, fanout
        runs = config.resolved_runs_dir()
        assert not runs.exists() or not any(runs.iterdir()), "no run folder for a refused request"


@pytest.mark.parametrize(
    ("preset", "width", "total", "usd", "timeout"),
    [
        ("lite", 3, 17, 0.85, 600),
        ("pro", 10, 52, 2.6, 1200),
        ("max", 15, 78, 3.9, 1500),
        ("ultra", 20, 104, 5.2, 1800),
        (None, 3, 17, 0.85, 1200),
    ],
)
async def test_the_preset_sets_the_batch_size_and_its_limits(
    config: BackendConfig, preset: str | None, width: int, total: int, usd: float, timeout: int
) -> None:
    item, _ = await _run(_manager(config), _script("./subagent list"), True, preset)
    plan = item.record["fanout"]
    assert (plan["width"], plan["max_parallel"], plan["max_total"]) == (width, width, total)
    assert (plan["max_usd"], plan["timeout_s"]) == (pytest.approx(usd), timeout)
    assert plan["stages"] == list(BATCH_STAGES)
    assert f"limits: width {width}, max_parallel {width}, max_total {total}" in _outputs(item)


async def test_automatic_models_put_the_subagents_on_the_smaller_claude_model(
    config: BackendConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Orchestrator on the large Claude model, subagents on the small one, unless the request names them."""
    seen: list[Any] = []

    async def fake_drive(self: Any, item: Any, spec: Any, translator: Any) -> None:
        seen.append(spec)

    monkeypatch.setattr(RunManager, "_drive", fake_drive)
    manager = RunManager(_config(config), _api(), agent="claude", summary=False)

    async def plan_of(body: dict[str, Any]) -> dict[str, Any]:
        item = manager.start(body)
        assert item.task is not None
        await item.task
        return item.record["fanout"]

    plan = await plan_of({"prompt": "x", "preset": "lite", "fanout": True})
    assert plan["orchestrator"] == {
        "agent": "claude",
        "model": config.agents.claude_cli.model,
        "effort": "low",
    }
    assert plan["subagent"] == {"agent": "claude", "model": "claude-sonnet-5-5", "effort": "low"}
    assert config.agents.claude_cli.model == "claude-opus-5-5" and seen[0].model is None
    named = await plan_of({"prompt": "x", "model": "sonnet", "fanout": {"subagent": {"model": "haiku"}}})
    assert (named["orchestrator"]["model"], named["subagent"]["model"]) == ("sonnet", "haiku")
    assert seen[1].model == "sonnet"
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-key-never-sent")
    other = await plan_of({"prompt": "x", "fanout": {"subagent": {"agent": "openrouter"}}})
    assert other["subagent"]["agent"] == "openrouter" and other["subagent"]["provider"] == "openrouter"
    assert other["subagent"]["model"] == config.agents.openrouter.model


async def test_merge_is_refused_while_a_subagent_of_the_stage_runs(config: BackendConfig) -> None:
    item, events = await _run(
        _manager(config),
        _script(
            './subagent start propose "$ sleep 1.5; echo slow" --name slow',
            './subagent start propose "$ echo quick" --name quick',
            './subagent merge propose --kept a2 --why "too early" 2>&1; echo "exit=$?"',
            './subagent merge verify --kept none --why "no batch" 2>&1; echo "exit=$?"',
            "./subagent wait --stage propose",
            './subagent merge propose --kept a3 --why "not in it" 2>&1; echo "exit=$?"',
            './subagent merge propose --kept a1,a2 --why "both kept: slow is smaller"',
            './subagent merge propose --kept a1 --why "again" 2>&1; echo "exit=$?"',
            './subagent start propose "$ echo retry" --name retry',
            "./subagent wait --stage propose",
            './subagent merge propose --kept a3 --why "the retry batch is merged on its own"',
            "./subagent list",
        ),
    )
    assert item.record["status"] == "succeeded"
    out = _outputs(item)
    assert "a1 of the propose batch still running" in out and "no subagents were started for verify" in out
    assert "a3 not in the propose batch" in out and "already merged" in out
    assert out.count("exit=1") == 4
    merged = _of(events, "stage.merged")
    assert len(merged) == 2 and (merged[1]["ids"], merged[1]["kept"]) == (["a3"], ["a3"])
    assert {k: merged[0][k] for k in ("stage", "started", "ids", "kept", "why")} == {
        "stage": "propose",
        "started": 2,
        "ids": ["a1", "a2"],
        "kept": ["a1", "a2"],
        "why": "both kept: slow is smaller",
    }
    assert merged[0]["seconds"] >= 1.0
    assert "merged propose: kept a1, a2" in out


async def test_a_failing_subagent_is_reported_and_the_batch_still_merges(config: BackendConfig) -> None:
    item, events = await _run(
        _manager(config),
        _script(
            "./subagent start propose '$ sleep 0.3; echo A' --name a",
            "./subagent start propose '$ echo trying; exit 3' --name broken",
            "./subagent start propose '$ sleep 0.3; echo C' --name c",
            "./subagent wait --stage propose",
            './subagent merge propose --kept a1 --why "a2 failed; a1 is smaller than a3"',
        ),
    )
    assert item.record["status"] == "succeeded" and not _of(events, "error")
    states = {e["id"]: e["state"] for e in _of(events, "subagent.finished")}
    assert states == {"a1": "done", "a2": "failed", "a3": "done"}
    merged = _of(events, "stage.merged")[0]
    assert (merged["started"], merged["done"], merged["kept"]) == (3, 2, ["a1"])


async def test_old_events_files_and_records_still_load(config: BackendConfig) -> None:
    """A run folder written before fan-out existed loads and reads as before."""
    folder = config.resolved_runs_dir() / "20260101-000000-abcdef"
    (folder / "workspace").mkdir(parents=True)
    head = {"ts": "2026-01-01T00:00:00+00:00", "run_id": folder.name}
    old = [
        {"seq": 1, **head, "type": "run.started", "prompt": "x"},
        {"seq": 2, **head, "type": "metric", "key": "gates", "value": 3},
        {"seq": 3, **head, "type": "run.finished", "status": "succeeded"},
    ]
    (folder / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in old))
    (folder / API_RECORD_FILE).write_text(
        json.dumps({"id": folder.name, "prompt": "x", "status": "succeeded"})
    )
    (folder / "run.json").write_text(json.dumps({"run_id": folder.name, "run_mode": "flex", "agent": {}}))
    manager = _manager(config)
    manager.load()
    item = manager.get(folder.name)
    assert item.log.since(1) == old
    assert "subagents" not in item.detail_view()
    record = RunDir(folder).read_record()
    assert record.subagents is None and "subagents" not in record.to_dict()


def test_run_takes_fanout_options() -> None:
    args = _parser().parse_args(
        [
            "run",
            "--fanout",
            "3",
            "--subagent-agent",
            "openrouter",
            "--subagent-model",
            "inkling-mini",
            "--subagent-max-usd",
            "0.2",
            "--prompt",
            "x",
        ]
    )
    assert (args.fanout, args.subagent_agent, args.subagent_model) == (3, "openrouter", "inkling-mini")
    assert args.subagent_max_usd == 0.2
    assert _parser().parse_args(["run", "--preset", "pro", "--fanout", "--prompt", "x"]).fanout == 0


def test_the_subagent_helper_refuses_inside_a_subagent(tmp_path: Path) -> None:
    import os
    import subprocess

    from chipin_backend.api.fanout import write_subagent_helper

    helper = write_subagent_helper(tmp_path, tmp_path, wait_s=5, agents=("stub",))
    got = subprocess.run(
        [str(helper), "list"], capture_output=True, text=True, env={**os.environ, ID_ENV: "a1"}, timeout=30
    )
    assert got.returncode == 1 and "only the orchestrator" in got.stderr
    usage = subprocess.run([str(helper)], capture_output=True, text=True, timeout=30)
    assert usage.returncode == 2 and "./subagent start <stage>" in usage.stderr
