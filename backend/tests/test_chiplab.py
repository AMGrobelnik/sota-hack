"""The optional chip lab: the agent's environment and instructions, and the lab's reports through ./progress.

The lab itself is mocked: a fake ``chiplab`` command that reports through the
run's real ``./progress`` helper exactly as the lab's bridge does
(``chiplab/chiplab/progress.py`` on ``ant/chip-lab``): one ``status`` line
before a tool, one ``metric <key> <number> <unit>`` per measured number, one
``artifact chips/<design_id>/<file> <kind>`` per copied file, and ``stage``
lines only when a call passes ``progress_stages``.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from aiohttp.test_utils import TestClient, TestServer

from chipin_backend.agents.env import build_agent_env
from chipin_backend.api.config import ApiConfig
from chipin_backend.api.events import EventLog
from chipin_backend.api.manager import RunManager, standing_instructions
from chipin_backend.api.progress import ProgressTailer, write_helper
from chipin_backend.api.server import TOKEN_HEADER, create_app
from chipin_backend.chiplab import (
    CHIPLAB_BIN_ENV,
    PROGRESS_CHIP_ENV,
    chiplab_available,
    chiplab_env,
    chiplab_instructions,
)
from chipin_backend.cli import main
from chipin_backend.config import BackendConfig

#: The lab's fixed metric keys and units: ``chiplab.progress.METRIC_KEYS``,
#: docs/CHIPIN_INTEGRATION.md section 2.
LAB_METRIC_UNITS = {
    "gates": "gates",
    "depth": "gates",
    "transistors": "transistors",
    "luts_ice40": "LUT4",
    "luts_xc7": "LUT6",
    "area_um2": "um2",
    "ge": "GE",
    "tt_tiles": "tiles",
    "cost_eur": "EUR",
    "vectors_checked": "vectors",
    "mismatches": "vectors",
    "verification_level": "level",
    "timing_slack_ns": "ns",
    "fmax_mhz": "MHz",
    "energy_pj": "pJ",
    "leakage_uw": "uW",
    "power_uw_at_rate": "uW",
    "candidates": "designs",
    "best_gates": "gates",
}
#: One value per key, in the forms the lab sends (ints, rounded floats, a negative slack).
LAB_VALUES: dict[str, int | float] = {
    "gates": 2285,
    "depth": 31,
    "transistors": 13710,
    "luts_ice40": 612,
    "luts_xc7": 301,
    "area_um2": 21004.5,
    "ge": 5250.25,
    "tt_tiles": 2,
    "cost_eur": 300,
    "vectors_checked": 4096,
    "mismatches": 0,
    "verification_level": 2,
    "timing_slack_ns": -0.125,
    "fmax_mhz": 48.7,
    "energy_pj": 3.25,
    "leakage_uw": 0.004512,
    "power_uw_at_rate": 0.0078,
    "candidates": 12,
    "best_gates": 1904,
}
DESIGN = "765fa47586bd"
#: (workspace path, artifact kind) the lab copies into a ChipIn workspace (section 5 of the guide).
LAB_FILES = [
    (f"chips/{DESIGN}/design.v", "file"),
    (f"chips/{DESIGN}/net.json", "file"),
    (f"chips/{DESIGN}/report.md", "report"),
    (f"chips/{DESIGN}/layout.png", "chip"),
]

FAKE_LAB = """
import json, os, subprocess, sys
from pathlib import Path

UNITS = {units!r}
VALUES = {values!r}
FILES = {files!r}
DESIGN = {design!r}


def helper():
    p = Path.cwd() / "progress"
    ok = p.is_file() and os.access(p, os.X_OK)
    if ok and "ChipIn progress helper" in p.read_text(errors="ignore")[:4000]:
        return p
    return None


def call(h, *args):
    argv = [str(h), *[str(a) for a in args]]
    subprocess.run(argv, cwd=h.parent, capture_output=True, text=True, timeout=30)


tool = sys.argv[1]
args = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {{}}
h = helper()
stages = bool(args.get("progress_stages"))
if h and stages:
    call(h, "stage", "compile", "started")
if h:
    call(h, "status", "ChipIn is synthesising chip " + DESIGN)
for rel, _ in FILES:
    Path(rel).parent.mkdir(parents=True, exist_ok=True)
    Path(rel).write_text("x")
if h:
    for key, value in VALUES.items():
        call(h, "metric", key, value, UNITS[key])
    call(h, "metric", "energy_pj", float("nan"), "pJ")
    for rel, kind in FILES:
        call(h, "artifact", rel, kind)
    if stages:
        call(h, "stage", "compile", "done")
print(json.dumps({{"status": "ok", "design_id": DESIGN, "metrics": {{"gates": VALUES["gates"]}}}}))
"""


def _fake_lab(bin_dir: Path) -> Path:
    bin_dir.mkdir(parents=True, exist_ok=True)
    source = FAKE_LAB.format(units=LAB_METRIC_UNITS, values=LAB_VALUES, files=LAB_FILES, design=DESIGN)
    command = bin_dir / "chiplab"
    command.write_text(f"#!{sys.executable}\n{source}", encoding="utf-8")
    command.chmod(0o755)
    return command


def _lab_env(tmp_path: Path) -> dict[str, str]:
    """A launcher environment naming a lab install outside the home folder."""
    _fake_lab(tmp_path / "lab-bin")
    return {
        "HOME": str(tmp_path / "home"),
        "PATH": "/usr/bin:/bin",
        CHIPLAB_BIN_ENV: str(tmp_path / "lab-bin"),
        "CHIPLAB_CONFIG": str(tmp_path / "lab" / "config.json"),
        "CHIPLAB_USER_DIR": str(tmp_path / "lab"),
        "DOCKER_HOST": "unix:///tmp/not-passed.sock",
        "RUNPOD_API_KEY": "never-passed",
    }


def _expected_lab_events() -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = [{"type": "status", "text": f"ChipIn is synthesising chip {DESIGN}"}]
    events += [
        {"type": "metric", "key": k, "value": v, "unit": LAB_METRIC_UNITS[k]} for k, v in LAB_VALUES.items()
    ]
    events += [
        {"type": "artifact", "name": Path(rel).name, "kind": kind, "path": f"workspace/{rel}"}
        for rel, kind in LAB_FILES
    ]
    return events


def _strip(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{k: v for k, v in e.items() if k not in {"seq", "ts", "run_id"}} for e in events]


# ---- environment and instructions ----


def test_lab_off_by_default(tmp_path: Path) -> None:
    base = {"HOME": str(tmp_path), "PATH": "/usr/bin:/bin", "CHIPLAB_CONFIG": "/x/config.json"}
    assert chiplab_env(base) == {}
    assert not chiplab_available(base)
    env = build_agent_env(base=base)
    assert env["PATH"] == "/usr/bin:/bin"
    assert "CHIPLAB_CONFIG" not in env
    assert PROGRESS_CHIP_ENV not in env
    assert "Chip lab" not in standing_instructions(base)


def test_lab_bin_puts_chiplab_on_the_agent_path(tmp_path: Path) -> None:
    base = _lab_env(tmp_path)
    env = build_agent_env(base=base)
    assert env["PATH"] == f"{tmp_path / 'lab-bin'}:/usr/bin:/bin"
    assert env["CHIPLAB_CONFIG"] == base["CHIPLAB_CONFIG"]
    assert env["CHIPLAB_USER_DIR"] == base["CHIPLAB_USER_DIR"]
    assert env[PROGRESS_CHIP_ENV] == "1"
    assert not {"RUNPOD_API_KEY", "DOCKER_HOST", CHIPLAB_BIN_ENV} & env.keys()
    proc = subprocess.run(
        ["chiplab", "agent-doc"], env=env, cwd=tmp_path, capture_output=True, text=True, timeout=30
    )
    assert proc.returncode == 0, proc.stderr


def test_lab_bin_without_a_command_leaves_the_lab_off(tmp_path: Path) -> None:
    base = {"PATH": "/bin", CHIPLAB_BIN_ENV: str(tmp_path / "empty"), "CHIPLAB_CONFIG": "/x"}
    assert chiplab_env(base) == {}
    assert build_agent_env(base=base)["PATH"] == "/bin"


def test_default_install_on_path_counts_as_present(tmp_path: Path) -> None:
    _fake_lab(tmp_path / "local-bin")
    base = {"PATH": f"{tmp_path / 'local-bin'}:/bin"}
    assert chiplab_env(base) == {"PATH": base["PATH"], PROGRESS_CHIP_ENV: "1"}
    assert chiplab_available(base)


def test_instructions_carry_the_lab_paragraph_only_when_the_lab_is_on(tmp_path: Path) -> None:
    on = standing_instructions(_lab_env(tmp_path))
    off = standing_instructions({"PATH": "/bin"})
    assert on.startswith(off.rstrip())
    paragraph = chiplab_instructions()
    assert on.endswith(paragraph)
    for phrase in (
        "chiplab agent-doc",
        "ingest-model",
        "prove-equivalence",
        "decision_rate_hz",
        "progress_stages",
    ):
        assert phrase in paragraph
    assert "./progress stage compile started" in paragraph
    must = (
        'Before you mark report done, call `chiplab chip-report --json \'{"design_id": '
        '"<the chip you chose>", "decision_rate_hz": <decisions per second>}\'` on the one chip you '
        "chose: the chip figures the user sees (area, power, energy, cost, verification) come from "
        "that call."
    )
    assert must in " ".join(on.split())
    assert "chip-report" not in off


def test_verify_stage_means_the_chip_against_its_model() -> None:
    """The base stage list and the lab paragraph agree on what verify is.

    A real run marked verify skipped after the lab's bit-exact and proof calls
    passed, because the stage list defined verify as patient recordings only.
    """
    text = standing_instructions({"PATH": "/bin"})
    stage = text.split("\n6. ", 1)[1].split("\n7. ", 1)[0]
    assert stage.startswith("verify:")
    assert "bit for bit" in stage
    assert "even with no recordings" in " ".join(stage.split())
    assert "the chip against your model" in chiplab_instructions()


def test_both_run_paths_get_the_same_instructions(
    tmp_path: Path, config: BackendConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name, value in _lab_env(tmp_path).items():
        monkeypatch.setenv(name, value)

    async def build() -> str:
        return RunManager(config, ApiConfig(), agent="claude").instructions

    assert asyncio.run(build()) == standing_instructions()
    assert "Chip lab" in standing_instructions()


# ---- the lab's reports -> progress.jsonl -> events ----


def _run_lab(workspace: Path, env: dict[str, str], args: dict[str, Any]) -> None:
    proc = subprocess.run(
        ["chiplab", "synthesize", "--json", json.dumps(args)],
        env=env,
        cwd=workspace,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["status"] == "ok"


async def test_lab_reports_become_events(tmp_path: Path) -> None:
    run_path = tmp_path / "run"
    workspace = run_path / "workspace"
    workspace.mkdir(parents=True)
    progress_file = run_path / "progress.jsonl"
    write_helper(workspace, progress_file)
    env = build_agent_env(base=_lab_env(tmp_path))
    _run_lab(workspace, env, {"design_id": DESIGN})
    _run_lab(workspace, env, {"design_id": DESIGN, "progress_stages": True})
    log = EventLog(run_path / "events.jsonl", "r1", asyncio.get_running_loop())
    ProgressTailer(progress_file, log, run_path, workspace).drain()
    got = _strip(log.since(1))
    lab = _expected_lab_events()
    stage = {"type": "stage", "name": "compile", "stage": "compile"}
    # the second call repeats metrics and status; artifacts are listed once per path
    assert got == [
        *lab,
        {**stage, "state": "started"},
        lab[0],
        *lab[1 : 1 + len(LAB_VALUES)],
        {**stage, "state": "done"},
    ]
    assert {e["key"] for e in got if e["type"] == "metric"} == set(LAB_METRIC_UNITS)
    for rel, _ in LAB_FILES:
        assert (workspace / rel).is_file()
    lines = [json.loads(x) for x in progress_file.read_text().splitlines()]
    assert not any(line.get("value") != line.get("value") for line in lines), "NaN was refused by the helper"


def test_helper_refuses_non_finite_numbers(tmp_path: Path) -> None:
    helper = write_helper(tmp_path, tmp_path / "progress.jsonl")
    for value in ("nan", "inf", "-inf"):
        proc = subprocess.run(
            [str(helper), "metric", "energy_pj", value], capture_output=True, text=True, timeout=30
        )
        assert proc.returncode == 2, value
    assert not (tmp_path / "progress.jsonl").exists()


async def test_tailer_refuses_non_finite_numbers(tmp_path: Path) -> None:
    progress_file = tmp_path / "progress.jsonl"
    progress_file.write_text('{"type": "metric", "key": "energy_pj", "value": NaN}\n')
    log = EventLog(tmp_path / "events.jsonl", "r1", asyncio.get_running_loop())
    ProgressTailer(progress_file, log, tmp_path, tmp_path).drain()
    assert log.since(1) == []


# ---- which chip a number belongs to: metric --chip and chosen ----


def _helper(helper: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(helper), *args], capture_output=True, text=True, timeout=30)


def _lines(progress_file: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in progress_file.read_text().splitlines()]


def test_helper_tags_a_metric_with_its_chip(tmp_path: Path) -> None:
    progress_file = tmp_path / "progress.jsonl"
    helper = write_helper(tmp_path, progress_file)
    for args in (
        ("metric", "gates", "2330", "--chip", DESIGN),
        ("metric", "gates", "2330", "gates", "--chip", DESIGN),
        ("metric", "area_um2", "-1.5", "um2", "--chip", DESIGN),
    ):
        proc = _helper(helper, *args)
        assert proc.returncode == 0, proc.stderr
    got = [{k: v for k, v in line.items() if k != "ts"} for line in _lines(progress_file)]
    assert got == [
        {"type": "metric", "key": "gates", "value": 2330, "chip": DESIGN},
        {"type": "metric", "key": "gates", "value": 2330, "unit": "gates", "chip": DESIGN},
        {"type": "metric", "key": "area_um2", "value": -1.5, "unit": "um2", "chip": DESIGN},
    ]


def test_helper_metric_without_chip_is_unchanged(tmp_path: Path) -> None:
    """Without --chip the line is byte for byte what the helper wrote before the flag existed."""
    progress_file = tmp_path / "progress.jsonl"
    helper = write_helper(tmp_path, progress_file)
    assert _helper(helper, "metric", "gates", "2330", "gates").returncode == 0
    assert _helper(helper, "metric", "candidates", "3").returncode == 0
    raw = progress_file.read_text().splitlines()
    stamps = [json.loads(x)["ts"] for x in raw]
    assert raw == [
        f'{{"ts": "{stamps[0]}", "type": "metric", "key": "gates", "value": 2330, "unit": "gates"}}',
        f'{{"ts": "{stamps[1]}", "type": "metric", "key": "candidates", "value": 3}}',
    ]


def test_helper_rejects_unknown_flags(tmp_path: Path) -> None:
    progress_file = tmp_path / "progress.jsonl"
    helper = write_helper(tmp_path, progress_file)
    for args in (
        ("metric", "gates", "2330", "--design", DESIGN),
        ("metric", "gates", "2330", "gates", "--foo"),
        ("metric", "gates", "2330", "--foo"),
        ("metric", "gates", "2330", "gates", "--chip", DESIGN, "--foo", "x"),
        ("metric", "--chip", DESIGN, "gates", "2330"),
    ):
        proc = _helper(helper, *args)
        assert proc.returncode == 2, args
        assert "progress: metric needs a key and a number" in proc.stderr, args
    for args in (("metric", "gates", "1", "--chip"), ("metric", "gates", "1", "--chip", "")):
        proc = _helper(helper, *args)
        assert proc.returncode == 2, args
        assert "--chip needs a design id" in proc.stderr
    for args in (("chosen",), ("chosen", "a", "b"), ("chosen", "")):
        assert _helper(helper, *args).returncode == 2, args
    assert not progress_file.exists()
    usage = _helper(helper).stderr
    assert "./progress metric <key> <number> [unit] [--chip <design_id>]" in usage
    assert "./progress chosen <design_id>" in usage


async def test_chip_tags_and_the_chosen_chip_become_events(tmp_path: Path) -> None:
    run_path = tmp_path / "run"
    workspace = run_path / "workspace"
    workspace.mkdir(parents=True)
    progress_file = run_path / "progress.jsonl"
    helper = write_helper(workspace, progress_file)
    for args in (
        ("metric", "gates", "2867", "gates", "--chip", "aaa111"),
        ("metric", "gates", "396", "--chip", "bbb222", "gates"),
        ("metric", "candidates", "3"),
        ("chosen", "aaa111"),
        ("chosen", "bbb222"),
    ):
        assert _helper(helper, *args).returncode == 0, args
    log = EventLog(run_path / "events.jsonl", "r1", asyncio.get_running_loop())
    ProgressTailer(progress_file, log, run_path, workspace).drain()
    got = _strip(log.since(1))
    assert got == [
        {"type": "metric", "key": "gates", "value": 2867, "unit": "gates", "chip": "aaa111"},
        {"type": "metric", "key": "gates", "value": 396, "unit": "gates", "chip": "bbb222"},
        {"type": "metric", "key": "candidates", "value": 3},
        {"type": "chosen", "chip": "aaa111"},
        {"type": "chosen", "chip": "bbb222"},
    ]
    # the backend keeps no run summary of the chosen chip: the last chosen event is the answer
    assert [e["chip"] for e in got if e["type"] == "chosen"][-1] == "bbb222"
    on_disk = [json.loads(x) for x in (run_path / "events.jsonl").read_text().splitlines()]
    assert _strip(on_disk) == got


async def test_tailer_refuses_a_bad_chip(tmp_path: Path) -> None:
    progress_file = tmp_path / "progress.jsonl"
    progress_file.write_text(
        '{"type": "metric", "key": "gates", "value": 1, "chip": 7}\n'
        '{"type": "chosen", "chip": ""}\n'
        '{"type": "chosen"}\n'
    )
    log = EventLog(tmp_path / "events.jsonl", "r1", asyncio.get_running_loop())
    ProgressTailer(progress_file, log, tmp_path, tmp_path).drain()
    assert log.since(1) == []


async def test_an_old_events_file_still_loads(tmp_path: Path) -> None:
    """A run stored before chip tags existed loads and replays unchanged."""
    old = [
        {"seq": 1, "ts": "2026-11-22T00:15:07+00:00", "run_id": "r0", "type": "run.started", "prompt": "p"},
        {"seq": 2, "ts": "2026-11-22T00:18:03+00:00", "run_id": "r0", "type": "metric", "key": "gates",
         "value": 2867, "unit": "gates"},
        {"seq": 3, "ts": "2026-11-22T00:20:00+00:00", "run_id": "r0", "type": "run.finished",
         "status": "succeeded"},
    ]  # fmt: skip
    path = tmp_path / "events.jsonl"
    text = "".join(json.dumps(e) + "\n" for e in old)
    path.write_text(text)
    log = EventLog(path, "r0", asyncio.get_running_loop())
    assert log.since(1) == old
    assert log.finished and log.last_seq == 3
    assert path.read_text() == text


# ---- the same events on the API's stream and in run --preset ----


async def test_lab_events_reach_the_api_stream(
    tmp_path: Path, config: BackendConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name, value in _lab_env(tmp_path).items():
        monkeypatch.setenv(name, value)
    flex = config.compute.flex.model_copy(update={"require_macos": False})
    config = config.model_copy(update={"compute": config.compute.model_copy(update={"flex": flex})})
    api = ApiConfig(keepalive_s=0.2, progress_poll_s=0.02, stub_step_s=0.3, run_timeout_s=60)
    token = "t"
    async with TestClient(TestServer(create_app(config, api, token=token, agent="stub"))) as client:
        resp = await client.post(
            "/api/runs", json={"prompt": "seizure band", "preset": "pro"}, headers={TOKEN_HEADER: token}
        )
        assert resp.status == 201
        run_id = (await resp.json())["id"]
        workspace = Path(config.runs_dir) / run_id / "workspace"
        await asyncio.to_thread(_run_lab, workspace, build_agent_env(), {"design_id": DESIGN})
        helper = workspace / "progress"
        await asyncio.to_thread(_helper, helper, "metric", "trial_gates", "48.7", "gates", "--chip", DESIGN)
        await asyncio.to_thread(_helper, helper, "chosen", DESIGN)
        stream = await client.get(f"/api/runs/{run_id}/events", params={"token": token})
        events: list[dict[str, Any]] = []
        async with asyncio.timeout(30):
            async for raw in stream.content:
                line = raw.decode().rstrip("\n")
                if line.startswith("data: "):
                    events.append(json.loads(line[6:]))
                    if events[-1]["type"] == "run.finished":
                        break
    lab_types = {"metric", "artifact", "status"}
    lab_keys = set(LAB_METRIC_UNITS)
    streamed = [e for e in _strip(events) if e["type"] in lab_types]
    from_lab = [
        e
        for e in streamed
        if (e["type"] == "metric" and e["key"] in lab_keys and e.get("unit"))
        or (e["type"] == "artifact" and e["path"].startswith("workspace/chips/"))
        or (e["type"] == "status" and DESIGN in e["text"])
    ]
    assert from_lab == _expected_lab_events()
    tagged = [e for e in _strip(events) if e.get("chip")]
    assert tagged == [
        {"type": "metric", "key": "trial_gates", "value": 48.7, "unit": "gates", "chip": DESIGN},
        {"type": "chosen", "chip": DESIGN},
    ]
    on_disk = [
        json.loads(x) for x in (Path(config.runs_dir) / run_id / "events.jsonl").read_text().splitlines()
    ]
    assert _strip(on_disk) == _strip(events)


@pytest.fixture
def run_config(tmp_path: Path) -> Path:
    """A config file keeping runs and logs under ``tmp_path``, flex without the macOS check."""
    cfg = tmp_path / "run.yaml"
    cfg.write_text(
        f"runs_dir: {tmp_path / 'runs'}\nlog_dir: {tmp_path / 'logs'}\n"
        "compute:\n  flex:\n    require_macos: false\n",
        encoding="utf-8",
    )
    return cfg


def test_run_preset_writes_a_dashboard_run(
    tmp_path: Path, run_config: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "a.md").write_text("A seizure band.", encoding="utf-8")
    (tmp_path / "b.md").write_text("Use the chip lab.", encoding="utf-8")
    argv = ["run", "--config", str(run_config), "--backend", "stub", "--preset", "lite", "--no-summary"]
    argv += ["--prompt-file", str(tmp_path / "a.md"), "--prompt-file", str(tmp_path / "b.md")]
    code = main(argv)
    out = json.loads(capsys.readouterr().out)
    assert code == 0, out
    assert out["status"] == "succeeded"
    run_dir = Path(out["run_dir"])
    assert (run_dir / "workspace" / "progress").is_file()
    assert "A seizure band.\n\nUse the chip lab." in (run_dir / "workspace" / "brief.md").read_text()
    events = [json.loads(x) for x in (run_dir / "events.jsonl").read_text().splitlines()]
    assert events[0]["type"] == "run.started" and events[-1]["type"] == "run.finished"
    assert {"compile", "verify"} <= {e["name"] for e in events if e["type"] == "stage"}
    assert json.loads((run_dir / "api.json").read_text())["preset"] == "lite"


def test_run_preset_refuses_other_machines(run_config: Path) -> None:
    base = ["run", "--config", str(run_config), "--preset", "pro", "--prompt", "hi"]
    assert main([*base, "--mode", "on_demand"]) == 2
    assert main([*base, "--backend", "stub", "--model", "x"]) == 2


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX shebangs")
def test_fake_lab_is_inert_without_a_helper(tmp_path: Path) -> None:
    env = build_agent_env(base=_lab_env(tmp_path))
    (tmp_path / "ws").mkdir()
    _run_lab(tmp_path / "ws", env, {"design_id": DESIGN})
    assert not (tmp_path / "ws" / "progress.jsonl").exists()
    assert os.listdir(tmp_path / "ws") == ["chips"]
