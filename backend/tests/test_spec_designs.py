"""The run spec and the design records: request checks, the agent's input, the helper, the route, CORS."""

from __future__ import annotations

import asyncio
import copy
import json
import subprocess
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, ClassVar

import pytest
from aiohttp.test_utils import TestClient, TestServer

from chipin_backend.agents.base import BACKENDS, AgentBackend
from chipin_backend.agents.types import AgentResult, AgentSpec, EventSink
from chipin_backend.api import fanout as fanout_mod
from chipin_backend.api import manager as manager_mod
from chipin_backend.api import steer
from chipin_backend.api.config import ApiConfig, FanoutConfig, load_api_config
from chipin_backend.api.designs import DESIGNS_FILE, designs_view, validate_design
from chipin_backend.api.events import EventLog
from chipin_backend.api.manager import (
    ApiRun,
    RunManager,
    _first_prompt,
    standing_instructions,
    subagent_standing_instructions,
)
from chipin_backend.api.progress import MAX_DESIGNS_PER_CALL, ProgressTailer, write_helper
from chipin_backend.api.server import TOKEN_HEADER, create_app, origin_allowed
from chipin_backend.api.spec import SpecError, parse_spec, spec_instructions
from chipin_backend.cli import _parser, main
from chipin_backend.config import BackendConfig

TOKEN = "test-session-token"
AUTH = {TOKEN_HEADER: TOKEN}

SPEC: dict[str, Any] = {
    "brief": "A two-electrode patch that flags seizures at home.",
    "device": "behind-the-ear EEG patch",
    "signal": "EEG, 2 channels",
    "detect": "seizure onset",
    "task_types": ["monitoring"],
    "patient_group": "adults with focal epilepsy",
    "place": "home",
    "fa_unit": "night",
    "targets": [
        {"metric": "sensitivity", "op": "at_least", "value": 0.8, "unit": None},
        {"metric": "fa_per_hour", "op": "at_most", "value": 0.5, "unit": "/h"},
    ],
    "primary": "sensitivity",
    "constraints": {"channels": 2, "find_best": False, "battery_hours": 24, "reusable": True},
    "data": {"mode": "simulate", "dataset": None},
}


def record(design_id: str, channels: int, caught: tuple[int, int], **extra: Any) -> dict[str, Any]:
    """A consistent design record: two patients with ``caught`` events of 5 each, 1 false alarm each."""
    total = sum(caught)
    rec: dict[str, Any] = {
        "id": design_id,
        "label": f"{design_id} on {channels} channels",
        "budget": {"channels": channels, "name": f"{channels} electrodes"},
        "gates": None,
        "gates_est": 800 * channels,
        "depth": None,
        "metrics": {"sensitivity": total / 10, "specificity": 0.95, "fa_per_hour": 0.2},
        "basis": "test",
        "counts": {
            "events_caught": total,
            "events_total": 10,
            "negatives_correct": 380,
            "negatives_total": 400,
            "hours": 10,
            "patients": 2,
        },
        "per_patient": [
            {"id": "p1", "caught": caught[0], "total": 5, "false_alarms": 1, "hours": 5},
            {"id": "p2", "caught": caught[1], "total": 5, "false_alarms": 1, "hours": 5},
        ],
        "verified": None,
        "data": "synthetic",
        "note": "synthetic data",
    }
    rec.update(extra)
    return rec


# ---- the spec ----


def test_a_full_spec_is_accepted_and_normalised() -> None:
    run_spec = parse_spec(SPEC)
    assert run_spec.spec["targets"][1] == {
        "metric": "fa_per_hour",
        "op": "at_most",
        "value": 0.5,
        "unit": "/h",
    }
    assert run_spec.spec["constraints"] == {
        "channels": 2,
        "find_best": False,
        "battery_hours": 24,
        "reusable": True,
        "layout": None,
    }
    assert run_spec.data_used == {
        "use": "synthetic",
        "folder": None,
        "reason": "the user asked for simulated data",
    }
    assert run_spec.block.startswith("## The user's spec\n")
    for line in (
        "- Device: behind-the-ear EEG patch",
        "  - sensitivity at least 0.8",
        "  - fa_per_hour at most 0.5 /h",
    ):
        assert line in run_spec.block
    assert "per night (12 hours" in run_spec.block and "SYNTHETIC" in run_spec.block
    minimal = {k: SPEC[k] for k in ("device", "signal", "detect", "targets", "primary")} | {
        "data": {"mode": "simulate"}
    }
    assert parse_spec(minimal).spec["fa_unit"] == "hour"


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"device": None}, "spec is missing device"),
        ({"colour": "red"}, "spec has unknown field(s) colour"),
        ({"targets": []}, "spec.targets must be a list of 1 to 12 targets"),
        (
            {"targets": [{"metric": "sensitivity", "op": "above", "value": 1}]},
            "spec.targets[0].op must be one of",
        ),
        ({"targets": [{"metric": "Sens itivity", "op": "at_least", "value": 1}]}, "spec.targets[0].metric"),
        ({"targets": [{"metric": "sensitivity", "op": "at_least"}]}, "spec.targets[0].value is required"),
        ({"place": "car"}, "spec.place must be one of ward, home, patient"),
        ({"fa_unit": "week"}, "spec.fa_unit must be one of"),
        ({"task_types": ["triage"]}, "spec.task_types must be a list of"),
        ({"constraints": {"channels": 0}}, "spec.constraints.channels must be more than 0"),
        ({"constraints": {"find_best": "yes"}}, "spec.constraints.find_best must be true, false or null"),
        ({"constraints": {"wires": 2}}, "spec.constraints has unknown field(s) wires"),
        ({"constraints": {"layout": "no"}}, "spec.constraints.layout must be true, false or null"),
        ({"data": {"mode": "cloud"}}, "spec.data.mode must be one of public, own, simulate"),
        ({"data": {}}, "spec.data.mode is required"),
    ],
)
def test_a_bad_spec_is_refused_naming_the_field(change: dict[str, Any], message: str) -> None:
    with pytest.raises(SpecError) as err:
        parse_spec({**copy.deepcopy(SPEC), **change})
    assert message in str(err.value)


@pytest.mark.parametrize(
    ("brief", "layout"),
    [
        ("A single-lead ECG patch for AF. Use synthetic data; no physical layout needed.", False),
        ("An EEG patch, without a layout please", False),
        ("Seizure flag; the physical layout is not needed yet.", False),
        ("Skip layout. Just gates.", False),
        ("A seizure flag chip ready for tape-out", None),
        ("Make a clean layout of the report", None),
    ],
)
def test_a_brief_that_turns_layout_down_tells_the_agent_to_skip_it(brief: str, layout: bool | None) -> None:
    """The live run's brief said no physical layout, yet it drew a layout image and wrote a GDS file."""
    run_spec = parse_spec({**copy.deepcopy(SPEC), "brief": brief})
    assert run_spec.spec["constraints"]["layout"] is layout
    said = "- Physical layout: NOT wanted" in run_spec.block
    assert said is (layout is False)
    if said:
        assert "Do not call layout, timing-power, tt-package, tt-export or bitstream" in run_spec.block


def test_an_explicit_layout_choice_wins_over_the_brief() -> None:
    body = {**copy.deepcopy(SPEC), "brief": "no layout needed"}
    body["constraints"] = {**body["constraints"], "layout": True}
    run_spec = parse_spec(body)
    assert run_spec.spec["constraints"]["layout"] is True
    assert "- Physical layout: wanted" in run_spec.block


def test_data_modes_resolve_to_what_the_run_can_use(tmp_path: Path) -> None:
    folder = tmp_path / "chbmit"
    folder.mkdir()
    datasets = {"chb-mit": folder, "gone": tmp_path / "missing"}

    def used(mode: str, dataset: str | None) -> dict[str, Any]:
        return parse_spec({**SPEC, "data": {"mode": mode, "dataset": dataset}}, datasets).data_used

    assert used("public", "chb-mit") == {
        "use": "public:chb-mit",
        "folder": str(folder.resolve()),
        "reason": "set up on this server",
    }
    assert used("public", "tuh")["use"] == "synthetic" and "not set up" in used("public", "tuh")["reason"]
    assert "missing" in used("public", "gone")["reason"]
    assert "not available in this build" in used("own", None)["reason"]
    block = parse_spec({**SPEC, "data": {"mode": "public", "dataset": "chb-mit"}}, datasets).block
    assert str(folder.resolve()) in block and "SYNTHETIC" not in block
    assert load_api_config().datasets == {}, "no dataset is set up by default"


# ---- design records ----


def test_a_consistent_record_is_accepted() -> None:
    rec = record(
        "a", 2, (4, 4), verified={"vectors": 512, "mismatches": 0, "level": "bit-exact", "proved": True}
    )
    assert validate_design(rec) == rec


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"metrics": {"sensitivity": 80}}, "metrics.sensitivity must be a fraction from 0 to 1"),
        ({"gates": -3}, "gates must not be negative"),
        ({"gates": 12.5}, "gates must be a whole number"),
        ({"colour": "red"}, "unknown field(s) colour"),
        ({"basis": "train"}, "basis must be validation or test"),
        ({"data": "patients"}, "data must be synthetic or public:<dataset name>"),
        ({"budget": {"name": "two"}}, "budget needs exactly one of channels or sensors"),
        ({"label": None}, "missing field(s) label"),
        ({"metrics": {"sensitivity": 0.5, "specificity": 0.95, "fa_per_hour": 0.2}}, "does not match counts"),
        (
            {"metrics": {"sensitivity": 0.8, "specificity": 0.95, "fa_per_hour": 0.9}},
            "metrics.fa_per_hour (0.9)",
        ),
        ({"verified": {"vectors": 4, "mismatches": 5}}, "verified.mismatches is more than verified.vectors"),
    ],
)
def test_a_bad_record_is_refused_with_the_reason(change: dict[str, Any], message: str) -> None:
    with pytest.raises(ValueError) as err:
        validate_design({**record("a", 2, (4, 4)), **change})
    assert message in str(err.value)


def test_counts_must_agree_with_the_patients() -> None:
    rec = record("a", 2, (4, 4))
    rec["counts"]["events_total"] = 11
    with pytest.raises(ValueError, match=r"counts\.events_total"):
        validate_design(rec)


def _helper(workspace: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(workspace / "progress"), *args], capture_output=True, text=True, check=False, cwd=workspace
    )


async def test_helper_and_tailer_upsert_designs(tmp_path: Path) -> None:
    run_path = tmp_path / "run"
    workspace = run_path / "workspace"
    workspace.mkdir(parents=True)
    progress = run_path / "progress.jsonl"
    write_helper(workspace, progress)
    log = EventLog(run_path / "events.jsonl", "r1", asyncio.get_running_loop())
    tailer = ProgressTailer(progress, log, run_path, workspace)

    assert _helper(workspace, "design", json.dumps(record("own-a", 2, (4, 4)))).stdout.strip() == "ok"
    (workspace / "b.json").write_text(json.dumps(record("own-b", 1, (3, 2))))
    assert _helper(workspace, "design", "b.json").returncode == 0
    bad = _helper(workspace, "design", json.dumps({**record("own-c", 2, (4, 4)), "gates": -1}))
    assert bad.returncode == 2 and "design record refused: gates must not be negative" in bad.stderr
    assert _helper(workspace, "design", "{not json").returncode == 2
    compiled = record("lab-7", 2, (4, 4), gates=1450, previous_id="own-a")
    assert _helper(workspace, "design", json.dumps(compiled)).returncode == 0
    verified = {
        **compiled,
        "verified": {"vectors": 256, "mismatches": 0, "level": "bit-exact", "proved": None},
    }
    assert _helper(workspace, "design", json.dumps(verified)).returncode == 0
    with progress.open("a") as handle:  # a line that skipped the helper is checked again
        handle.write(json.dumps({"type": "design", **record("own-d", 2, (4, 4)), "basis": "train"}) + "\n")
    tailer.drain()

    designs = [e for e in log.since(1) if e["type"] == "design"]
    assert [(e["design"]["id"], e["revision"]) for e in designs] == [
        ("own-a", 1),
        ("own-b", 1),
        ("lab-7", 2),
        ("lab-7", 3),
    ]
    assert designs[2]["design"]["previous_id"] == "own-a"
    stored = json.loads((run_path / DESIGNS_FILE).read_text())["designs"]
    assert [d["id"] for d in stored] == ["lab-7", "own-b"], "the compiled record took over own-a's place"
    assert stored[0]["gates"] == 1450 and stored[0]["verified"]["vectors"] == 256
    assert stored[0]["revision"] == 3 and stored[0]["ts"]


async def test_a_list_of_estimated_candidates_lands_in_designs_json(tmp_path: Path) -> None:
    """One ``./progress design list.json`` call files every scored candidate of a batch, misses
    included, as estimated (hollow on the chart: ``gates`` null, ``gates_est`` set); a list
    over the cap or with one bad record files nothing."""
    run_path = tmp_path / "run"
    workspace = run_path / "workspace"
    workspace.mkdir(parents=True)
    progress = run_path / "progress.jsonl"
    write_helper(workspace, progress, subagent=True)
    log = EventLog(run_path / "events.jsonl", "r1", asyncio.get_running_loop())
    tailer = ProgressTailer(progress, log, run_path, workspace)

    def candidate(i: int, sens: float) -> dict[str, Any]:
        return {
            "id": f"mlp-h{i}",
            "label": f"MLP, {i} hidden",
            "budget": {"channels": 1, "name": "1 lead"},
            "gates": None,
            "gates_est": 120 * i,
            "depth": None,
            "metrics": {"sensitivity": sens, "specificity": 0.9, "fa_per_hour": 1.5},
            "basis": "validation",
            "verified": None,
            "data": "synthetic",
            "note": "estimated, not compiled; synthetic data",
        }

    batch = [candidate(i, s) for i, s in ((2, 0.62), (4, 0.81), (8, 0.93))]  # 0.62 misses the target
    (workspace / "candidates.json").write_text(json.dumps(batch))
    done = _helper(workspace, "design", "candidates.json")
    assert done.returncode == 0 and done.stdout.strip() == "ok, 3 design records"
    too_many = [candidate(i, 0.9) for i in range(1, MAX_DESIGNS_PER_CALL + 2)]
    (workspace / "many.json").write_text(json.dumps(too_many))
    over = _helper(workspace, "design", "many.json")
    assert over.returncode == 2 and f"1 to {MAX_DESIGNS_PER_CALL} records" in over.stderr
    (workspace / "bad.json").write_text(json.dumps([candidate(16, 0.9), {**candidate(32, 0.9), "gates": -1}]))
    bad = _helper(workspace, "design", "bad.json")
    assert bad.returncode == 2 and "(item 1)" in bad.stderr
    tailer.drain()

    stored = json.loads((run_path / DESIGNS_FILE).read_text())["designs"]
    assert [d["id"] for d in stored] == ["mlp-h2", "mlp-h4", "mlp-h8"]
    for d, want in zip(stored, batch, strict=True):
        assert d["gates"] is None and d["gates_est"] == want["gates_est"] > 0
        assert d["metrics"] == want["metrics"] and d["basis"] == "validation"
        assert d["budget"] == {"channels": 1, "name": "1 lead"} and "not compiled" in d["note"]
    assert len([e for e in log.since(1) if e["type"] == "design"]) == 3


# ---- a spec-driven run through the server ----


class SpecStub(AgentBackend):
    """A scripted agent that reads spec.json and reports design records through the real helper."""

    name: ClassVar[str] = "spec_stub"
    seen: ClassVar[list[AgentSpec]] = []
    answers: ClassVar[list[tuple[int, str]]] = []

    async def run(self, spec: AgentSpec, sink: EventSink) -> AgentResult:
        assert spec.workdir is not None
        SpecStub.seen.append(spec)
        workdir = spec.workdir
        user_spec = workdir / "spec.json"
        if user_spec.is_file():
            channels = json.loads(user_spec.read_text())["constraints"]["channels"]
            steps = [
                ["stage", "propose", "started"],
                ["design", json.dumps(record("a", channels, (4, 4)))],
                ["design", json.dumps(record("b", channels, (3, 3)))],
                ["design", json.dumps(record("c", 1, (2, 3)))],
                ["design", json.dumps({**record("d", 1, (2, 3)), "metrics": {"sensitivity": 50}})],
                ["design", json.dumps(record("a", channels, (4, 4), gates=1450))],
                ["chosen", "a"],
            ]
            for args in steps:
                proc = await asyncio.create_subprocess_exec(
                    str(workdir / "progress"), *args, cwd=workdir, stderr=asyncio.subprocess.PIPE
                )
                _, err = await proc.communicate()
                SpecStub.answers.append((proc.returncode or 0, err.decode()))
        return AgentResult(agent=spec.name, final_text="done")


@pytest.fixture
async def spec_client(config: BackendConfig, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[TestClient]:
    """A server whose claude agent is :class:`SpecStub` (so the standing instructions are built)."""
    monkeypatch.setitem(BACKENDS, "spec_stub", f"{__name__}:SpecStub")
    monkeypatch.setitem(manager_mod.AGENT_BACKENDS, "claude", "spec_stub")
    monkeypatch.setattr(SpecStub, "seen", [])
    monkeypatch.setattr(SpecStub, "answers", [])
    flex = config.compute.flex.model_copy(update={"require_macos": False})
    config = config.model_copy(update={"compute": config.compute.model_copy(update={"flex": flex})})
    api = ApiConfig(keepalive_s=0.2, progress_poll_s=0.02, run_timeout_s=60)
    async with TestClient(TestServer(create_app(config, api, token=TOKEN, agent="claude"))) as client:
        yield client


async def _run(client: TestClient, body: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    resp = await client.post("/api/runs", json=body, headers=AUTH)
    assert resp.status == 201, await resp.text()
    run_id = (await resp.json())["id"]
    stream = await client.get(f"/api/runs/{run_id}/events", params={"token": TOKEN})
    events: list[dict[str, Any]] = []
    async with asyncio.timeout(20):
        async for raw in stream.content:
            line = raw.decode()
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
                if events[-1]["type"] == "run.finished":
                    break
    return run_id, events


async def test_a_spec_driven_run_reports_and_serves_designs(
    spec_client: TestClient, config: BackendConfig
) -> None:
    run_id, events = await _run(spec_client, {"prompt": "A seizure patch", "preset": "lite", "spec": SPEC})

    agent_spec = SpecStub.seen[0]
    assert agent_spec.prompts[0].startswith("## The user's spec\n\n- Device: behind-the-ear EEG patch")
    assert agent_spec.prompts[0].endswith(_first_prompt("A seizure patch"))
    assert agent_spec.system_prompt == f"{standing_instructions().rstrip()}\n\n{spec_instructions()}"
    assert "For EVERY candidate design you score" in agent_spec.system_prompt
    assert events[0]["type"] == "run.started" and events[0]["spec"]["primary"] == "sensitivity"
    workspace = config.resolved_runs_dir() / run_id / "workspace"
    assert json.loads((workspace / "spec.json").read_text())["data_used"]["use"] == "synthetic"

    assert [code for code, _ in SpecStub.answers] == [0, 0, 0, 0, 2, 0, 0]
    assert "metrics.sensitivity must be a fraction from 0 to 1" in SpecStub.answers[4][1]
    designs = [e for e in events if e["type"] == "design"]
    assert [e["design"]["id"] for e in designs] == ["a", "b", "c", "a"], "the bad record d is not emitted"
    assert designs[-1]["design"]["gates"] == 1450 and designs[-1]["revision"] == 2
    assert [e["chip"] for e in events if e["type"] == "chosen"] == ["a"]

    served = await (await spec_client.get(f"/api/runs/{run_id}/designs", headers=AUTH)).json()
    assert [d["id"] for d in served["designs"]] == ["a", "b", "c"]
    assert served["designs"][0]["gates"] == 1450 and served["chosen"] == "a"
    assert (await spec_client.get(f"/api/runs/{run_id}/designs")).status == 401


async def test_a_bad_spec_is_a_400_and_starts_nothing(spec_client: TestClient, config: BackendConfig) -> None:
    resp = await spec_client.post(
        "/api/runs", json={"prompt": "x", "spec": {**SPEC, "fa_unit": "week"}}, headers=AUTH
    )
    assert resp.status == 400
    assert (await resp.json())["error"].startswith("spec.fa_unit must be one of hour, night, day")
    assert not SpecStub.seen and not list(config.resolved_runs_dir().glob("*"))


async def test_a_run_without_a_spec_is_unchanged(spec_client: TestClient, config: BackendConfig) -> None:
    run_id, events = await _run(spec_client, {"prompt": "A seizure patch", "preset": "lite"})
    agent_spec = SpecStub.seen[0]
    assert agent_spec.prompts == [_first_prompt("A seizure patch")]
    assert agent_spec.system_prompt == standing_instructions()
    assert set(events[0]) == {"seq", "ts", "run_id", "type", "prompt", "agent", "runner"}
    assert not any(e["type"] == "design" for e in events)
    run_path = config.resolved_runs_dir() / run_id
    assert not (run_path / "workspace" / "spec.json").exists() and not (run_path / DESIGNS_FILE).exists()
    served = await (await spec_client.get(f"/api/runs/{run_id}/designs", headers=AUTH)).json()
    assert served == {"designs": [], "chosen": None}


# ---- CORS, serve --site, run --spec-file ----


def test_origins_come_from_the_config() -> None:
    default = ApiConfig().allowed_origins
    assert default == load_api_config().allowed_origins
    for origin in ("https://chipin.space", "http://127.0.0.1:5500", "http://localhost", "http://[::1]:8000"):
        assert origin_allowed(origin, default), origin
    for origin in ("http://chipin.space", "https://chipin.space:444", "http://localhost.evil:80", "null", ""):
        assert not origin_allowed(origin, default), origin
    assert origin_allowed("https://example.org", ["https://example.org"])
    assert not origin_allowed("https://chipin.space", ["https://example.org"])


async def test_a_configured_origin_list_governs_the_api(config: BackendConfig) -> None:
    api = ApiConfig(allowed_origins=["https://dash.example"])
    async with TestClient(TestServer(create_app(config, api, token=TOKEN, agent="stub"))) as client:
        ok = await client.options(
            "/api/runs", headers={"Origin": "https://dash.example", "Access-Control-Request-Method": "POST"}
        )
        assert ok.status == 204 and ok.headers["Access-Control-Allow-Origin"] == "https://dash.example"
        refused = await client.get("/api/runs", headers={"Origin": "https://chipin.space", **AUTH})
        assert refused.status == 403


def test_serve_site_and_run_spec_file_options(tmp_path: Path) -> None:
    assert _parser().parse_args(["serve", "--site", "site"]).frontend == Path("site")
    assert _parser().parse_args(["serve", "--frontend", "site"]).frontend == Path("site")
    args = _parser().parse_args(["run", "--preset", "lite", "--prompt", "x", "--spec-file", "s.json"])
    assert args.spec_file == Path("s.json")
    env = tmp_path / "empty.env"
    env.write_text("")
    assert main(["run", "--prompt", "x", "--spec-file", "s.json", "--env-file", str(env)]) == 2


# ---- with fan-out and follow-ups: the spec and the records reach every agent ----


def _stub_manager(config: BackendConfig) -> RunManager:
    """Stub orchestrator and subagents, fan-out of two, flex without the macOS check."""
    flex = config.compute.flex.model_copy(update={"require_macos": False})
    config = config.model_copy(update={"compute": config.compute.model_copy(update={"flex": flex})})
    api = ApiConfig(progress_poll_s=0.02, stub_step_s=0.01, run_timeout_s=60, fanout=FanoutConfig())
    return RunManager(config, api, agent="stub", summary=False)


def _subagent_specs(monkeypatch: pytest.MonkeyPatch) -> list[AgentSpec]:
    """Every subagent's :class:`AgentSpec`, as handed to its runner."""
    seen: list[AgentSpec] = []
    real = fanout_mod.runner_for

    class Recording:
        def __init__(self, inner: Any) -> None:
            self.inner = inner

        async def run(self, spec: AgentSpec, run: Any) -> AgentResult:
            seen.append(spec)
            return await self.inner.run(spec, run)

        async def close(self) -> None:
            await self.inner.close()

    monkeypatch.setattr(fanout_mod, "runner_for", lambda *a, **k: Recording(real(*a, **k)))
    return seen


async def _finish(item: ApiRun) -> list[dict[str, Any]]:
    assert item.task is not None
    async with asyncio.timeout(60):
        await item.task
    return item.log.since(1)


async def test_a_subagent_reports_design_records_through_its_own_helper(
    config: BackendConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A fan-out subagent's records reach the event log and designs.json under its id."""
    subagents = _subagent_specs(monkeypatch)
    manager = _stub_manager(config)
    rec = json.dumps(record("sub-a", 2, (4, 4), agent="someone-else"))
    script = "\n".join(
        [
            "A seizure patch, scripted.",
            f"$ printf '%s' '{rec}' > sub-a.json",
            '$ ./subagent start propose "$ ./progress design ../../sub-a.json" --name family-a',
            "$ ./subagent wait --all",
        ]
    )
    item = manager.start(
        {"prompt": script, "preset": "lite", "spec": SPEC, "fanout": {"enabled": True, "width": 2}}
    )
    events = await _finish(item)
    assert item.record["status"] == "succeeded"
    [design] = [e for e in events if e["type"] == "design"]
    assert design["agent"] == "a1" and design["design"]["agent"] == "a1", "the subagent's id, not its claim"
    assert design["design"]["id"] == "sub-a" and design["revision"] == 1
    view = designs_view(item.run.path, item.log)
    assert [(d["id"], d["agent"]) for d in view["designs"]] == [("sub-a", "a1")]

    folder = item.run.workspace / "agents" / "a1"
    assert json.loads((folder / "spec.json").read_text()) == json.loads(
        (item.run.workspace / "spec.json").read_text()
    )
    [sub_spec] = subagents
    assert sub_spec.prompts[0].startswith("## The user's spec\n\n")
    assert sub_spec.system_prompt == f"{subagent_standing_instructions().rstrip()}\n\n{spec_instructions()}"


async def test_the_standing_instructions_reach_every_agent_with_the_spec(
    config: BackendConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Orchestrator, subagent and follow-up (live or rebuilt) carry the rules and the spec paragraph."""
    for rule in ("Choosing the chip", "fewest measured gates", "Never choose, or change the choice"):
        assert rule in standing_instructions(), rule
    for text in (standing_instructions(), subagent_standing_instructions()):
        assert "at least every couple" in text and "never invent" in text.lower()

    subagents = _subagent_specs(monkeypatch)
    manager = _stub_manager(config)
    item = manager.start(
        {
            "prompt": '$ ./subagent start propose "$ echo hi" --name family-a\n$ ./subagent wait --all',
            "preset": "lite",
            "spec": SPEC,
            "fanout": {"enabled": True, "width": 2},
        }
    )
    await _finish(item)
    orchestrator = json.loads(item.run.record_path.read_text())["agent"]
    with_spec = f"{standing_instructions().rstrip()}\n\n{spec_instructions()}"
    assert orchestrator["system_prompt"].startswith(with_spec.rstrip())
    assert "ONE BATCH of 2 subagents" in orchestrator["system_prompt"]
    assert orchestrator["prompts"][0].startswith("## The user's spec\n\n")
    [sub] = subagents
    assert sub.system_prompt == f"{subagent_standing_instructions().rstrip()}\n\n{spec_instructions()}"
    assert sub.prompts[0].startswith("## The user's spec\n\n")

    seen: list[AgentSpec] = []

    async def capture(_manager: Any, _item: Any, spec: AgentSpec, **_: Any) -> None:
        seen.append(spec)

    monkeypatch.setattr(steer, "_drive_follow_up", capture)
    body = {"prompt": "A seizure patch", "preset": "lite", "spec": SPEC}
    live = (await _finish(manager.start(body)))[0]["run_id"]
    on_disk = (await _finish(manager.start(body)))[0]["run_id"]
    assert (await manager.message(live, "Why that chip?"))["delivery"] == "follow_up"
    await asyncio.sleep(0)
    reloaded = _stub_manager(config)
    reloaded.load()
    assert (await reloaded.message(on_disk, "And the gates?"))["delivery"] == "follow_up"
    await asyncio.sleep(0)
    assert [s.system_prompt for s in seen] == [with_spec, with_spec], "live spec and spec rebuilt from disk"
