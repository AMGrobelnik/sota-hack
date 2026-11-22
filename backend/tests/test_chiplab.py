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
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
import yaml
from aiohttp.test_utils import TestClient, TestServer
from loguru import logger

from chipin_backend.agents import AgentResult, AgentSpec, backend_for
from chipin_backend.agents.claude_cli import build_argv, plugin_dirs, transcript_path
from chipin_backend.agents.env import build_agent_env
from chipin_backend.api.config import ApiConfig
from chipin_backend.api.events import EventLog
from chipin_backend.api.manager import ApiAgent, RunManager, standing_instructions
from chipin_backend.api.progress import ProgressTailer, write_helper
from chipin_backend.api.server import TOKEN_HEADER, create_app
from chipin_backend.chiplab import (
    CHIPLAB_BIN_ENV,
    CLAUDE_PLUGIN_NAME,
    PROGRESS_CHIP_ENV,
    TOOLS_REFERENCE,
    chiplab_available,
    chiplab_env,
    chiplab_instructions,
    install_skill,
    lab_version,
    skill_files,
)
from chipin_backend.cli import main
from chipin_backend.compute import local as local_runner
from chipin_backend.compute.factory import runner_for
from chipin_backend.config import BackendConfig, ClaudeCliConfig
from chipin_backend.runs import RunDir

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
FAKE_CLAUDE = Path(__file__).with_name("fake_claude_cli.py")
#: What the fake lab prints for ``chiplab agent-doc`` (the real lab prints its AGENT.md).
LAB_REFERENCE = "# fake chip lab: interface for AI scientists\n\n### `synthesize`\n\nGates from a design."
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
if tool == "agent-doc":
    print({reference!r})
    sys.exit(0)
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
    source = FAKE_LAB.format(
        units=LAB_METRIC_UNITS, values=LAB_VALUES, files=LAB_FILES, design=DESIGN, reference=LAB_REFERENCE
    )
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


#: The sentence the agent must always have in view, word for word (whitespace normalised).
REQUIRED_CHIP_REPORT = (
    'Before you mark report done, call `chiplab chip-report --json \'{"design_id": '
    '"<the chip you chose>", "decision_rate_hz": <decisions per second>}\'` on the one chip you '
    "chose: the chip figures the user sees (area, power, energy, cost, verification) come from "
    "that call."
)


def _skill_md() -> str:
    """The packaged SKILL.md, read through the package's resources."""
    return (skill_files() / "SKILL.md").read_text(encoding="utf-8")


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
    # Always in view: the skill by name, when to use it, the required call and a fallback.
    for phrase in ("skill named `chiplab`", "compile stage", "chiplab agent-doc", "references/tools.md"):
        assert phrase in paragraph
    assert REQUIRED_CHIP_REPORT in " ".join(on.split())
    assert "chip-report" not in off and "chiplab" not in off
    # The detail moved into the skill.
    body = _skill_md()
    for phrase in ("ingest-model", "prove-equivalence", "decision_rate_hz", "progress_stages"):
        assert phrase in body
    assert "./progress stage compile started" in body


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
    assert "the chip against your model" in _skill_md()


def test_both_run_paths_get_the_same_instructions(
    tmp_path: Path, config: BackendConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name, value in _lab_env(tmp_path).items():
        monkeypatch.setenv(name, value)

    async def build() -> str:
        return RunManager(config, ApiConfig(), agent="claude").instructions

    assert asyncio.run(build()) == standing_instructions()
    assert "Chip lab" in standing_instructions()


# ---- the instructions reach both harnesses ----


def _flat(text: str) -> str:
    return " ".join(text.split())


async def _dashboard_spec(
    agent: ApiAgent, config: BackendConfig, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> AgentSpec:
    """The spec a dashboard run hands its agent, with the lab on (the agent itself not started)."""
    for name, value in _lab_env(tmp_path).items():
        monkeypatch.setenv(name, value)
    seen: list[AgentSpec] = []

    async def fake_run_agent(spec: AgentSpec, _config: BackendConfig, **kwargs: Any) -> Any:
        seen.append(spec)
        return kwargs["run"], AgentResult(agent=spec.name, final_text="ok")

    monkeypatch.setattr("chipin_backend.api.manager.run_agent", fake_run_agent)
    item = RunManager(config, ApiConfig(), agent=agent, summary=False).start(
        {"prompt": "a seizure detector", "preset": "pro"}
    )
    assert item.task is not None
    await item.task
    [spec] = seen
    return replace(spec, workdir=tmp_path / "work", timeout_s=120)


def _assert_carries_the_instructions(text: str) -> None:
    flat = _flat(text)
    assert _flat(standing_instructions()) in flat
    assert _flat(chiplab_instructions()) in flat
    assert "./progress stage" in flat and "chiplab agent-doc" in flat


async def test_claude_agent_is_typed_the_instructions_and_the_lab_page(
    tmp_path: Path, config: BackendConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = await _dashboard_spec("claude", config, tmp_path, monkeypatch)
    fake = tmp_path / "bin" / "claude"
    fake.parent.mkdir()
    fake.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{FAKE_CLAUDE}" "$@"\n')
    fake.chmod(0o755)
    cli = config.agents.claude_cli.model_copy(
        update={"cli_path": str(fake), "config_dir": tmp_path / "claude-config"}
    )
    agents = config.agents.model_copy(update={"claude_cli": cli})
    result = await backend_for("claude_cli", agents).run(spec, _Sink())
    assert not result.failed, result.error

    transcript = transcript_path(tmp_path / "claude-config", spec.workdir.resolve(), result.session_id)
    records = [json.loads(line) for line in transcript.read_text().splitlines()]
    typed = next(r["message"]["content"] for r in records if r.get("type") == "user")
    assert "<system-prompt>" in typed
    _assert_carries_the_instructions(typed)


async def test_openrouter_agent_gets_the_instructions_and_the_lab_page_as_its_system_message(
    tmp_path: Path, config: BackendConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("openhands.sdk")
    from openhands.sdk.llm import Message, MessageToolCall, TextContent
    from openhands.sdk.testing import TestLLM
    from pydantic import SecretStr

    from chipin_backend.agents.openrouter_agent import OpenRouterAgentBackend

    spec = await _dashboard_spec("openrouter", config, tmp_path, monkeypatch)
    sent: list[list[Any]] = []

    class RecordingLLM(TestLLM):
        def completion(self, messages: list[Any], *args: Any, **kwargs: Any) -> Any:
            sent.append(list(messages))
            return super().completion(messages, *args, **kwargs)

    def scripted_llm(
        self: Any, model: str, key: str, provider: Any, *, usage_id: str, fallback: Any = None
    ) -> Any:
        finish = MessageToolCall(
            id="call_1", name="finish", arguments=json.dumps({"message": "done"}), origin="completion"
        )
        reply = Message(role="assistant", content=[TextContent(text="")], tool_calls=[finish])
        return RecordingLLM.from_messages([reply], usage_id=usage_id, api_key=SecretStr(key))

    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-key")
    monkeypatch.setattr(OpenRouterAgentBackend, "_build_llm", scripted_llm)
    result = await backend_for("openrouter", config.agents).run(spec, _Sink())
    assert not result.failed, result.error

    system = [m for m in sent[0] if m.role == "system"]
    assert len(system) == 1
    text = "".join(getattr(c, "text", "") for c in system[0].content)
    _assert_carries_the_instructions(text)
    assert "OpenHands" in text  # the SDK's own system message is kept, not replaced


class _Sink:
    def emit(self, event: Any) -> None:
        return None


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
    assert not [p for p in (run_dir / "workspace").iterdir() if p.name.startswith(".")]


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


# ---- the chip-lab skill ----


def _front_matter(text: str) -> tuple[dict[str, Any], str]:
    _, head, body = text.split("---\n", 2)
    return yaml.safe_load(head), body


@pytest.mark.parametrize(
    ("harness", "folder"),
    [
        ("claude_cli", ".claude/plugins/chipin/skills/chiplab"),
        ("claude", ".claude/plugins/chipin/skills/chiplab"),
        ("openrouter", ".agents/skills/chiplab"),
    ],
)
def test_skill_installed_where_each_harness_finds_it(tmp_path: Path, harness: str, folder: str) -> None:
    workspace = tmp_path / "run" / "workspace"
    workspace.mkdir(parents=True)
    dest = install_skill(workspace, harness, _lab_env(tmp_path))
    assert dest == workspace / folder
    files = sorted(str(p.relative_to(workspace)) for p in workspace.rglob("*") if p.is_file())
    # The claude CLI loads the skill as a plugin: its manifest sits at the plugin root.
    manifest = [".claude/plugins/chipin/.claude-plugin/plugin.json"] if folder.startswith(".claude") else []
    assert files == [
        *manifest,
        f"{folder}/SKILL.md",
        f"{folder}/references/tools.md",
        f"{folder}/references/workflow.md",
    ]


def test_skill_contents(tmp_path: Path) -> None:
    dest = install_skill(tmp_path, "claude_cli", _lab_env(tmp_path))
    assert dest is not None
    meta, body = _front_matter((dest / "SKILL.md").read_text(encoding="utf-8"))
    assert meta["name"] == "chiplab" == dest.name
    description = " ".join(meta["description"].split())
    assert len(description) <= 1024
    for phrase in ("logic gates", "bit for bit", "formally equivalent", "layout", "power", "report"):
        assert phrase in description
    flat = " ".join(body.split())
    assert REQUIRED_CHIP_REPORT in flat
    for phrase in ("chiplab <tool> --json", "Exit codes: 0 ok", "**compile**", "**verify**", "**report**"):
        assert phrase in flat
    assert "--chip <design_id>" in flat and "./progress chosen <design_id>" in flat
    assert "references/tools.md" in flat and "chiplab agent-doc" in flat
    # Both harnesses run inline ``!`cmd` `` in a skill body; this one has none.
    assert "!`" not in body
    tools = (dest / TOOLS_REFERENCE).read_text(encoding="utf-8")
    header, rest = tools.split("\n", 1)
    assert header.startswith("> Copied from the installed chip lab (chiplab")
    assert "chiplab agent-doc" in header
    assert rest.strip() == LAB_REFERENCE


def test_skill_install_is_idempotent(tmp_path: Path) -> None:
    env = _lab_env(tmp_path)

    def snapshot() -> dict[str, bytes]:
        files = (p for p in (tmp_path / "ws").rglob("*") if p.is_file())
        return {str(p.relative_to(tmp_path / "ws")): p.read_bytes() for p in files}

    (tmp_path / "ws").mkdir()
    for harness in ("claude_cli", "openrouter"):
        install_skill(tmp_path / "ws", harness, env)
    first = snapshot()
    for harness in ("claude_cli", "openrouter"):
        install_skill(tmp_path / "ws", harness, env)
    assert snapshot() == first


def test_lab_off_installs_nothing(tmp_path: Path) -> None:
    off = {"HOME": str(tmp_path), "PATH": "/usr/bin:/bin"}
    for harness in ("claude_cli", "claude", "openrouter"):
        assert install_skill(tmp_path, harness, off) is None
    assert install_skill(tmp_path, "stub", _lab_env(tmp_path / "lab")) is None
    assert list(tmp_path.iterdir()) == [tmp_path / "lab"]
    assert "chiplab" not in standing_instructions(off)


def test_skill_without_the_labs_reference(tmp_path: Path) -> None:
    """A lab whose reference cannot be read: the skill is still installed, with a warning."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    command = bin_dir / "chiplab"
    command.write_text("#!/bin/sh\nexit 1\n")
    command.chmod(0o755)
    warnings: list[str] = []
    sink = logger.add(lambda m: warnings.append(m.record["message"]), level="WARNING")
    try:
        dest = install_skill(tmp_path / "ws", "openrouter", {"PATH": "/bin", CHIPLAB_BIN_ENV: str(bin_dir)})
    finally:
        logger.remove(sink)
    assert dest is not None and (dest / "SKILL.md").is_file()
    assert not (dest / TOOLS_REFERENCE).exists()
    assert "chiplab agent-doc" in (dest / "SKILL.md").read_text()
    assert any("agent-doc failed" in w for w in warnings)
    assert any("has no tools.md" in w for w in warnings)


def test_lab_version_follows_the_launcher(tmp_path: Path) -> None:
    lab = tmp_path / "chiplab"
    (lab / "pyproject.toml").parent.mkdir()
    (lab / "pyproject.toml").write_text('[project]\nname = "chiplab"\nversion = "9.9.1"\n')
    venv_command = lab / ".venv" / "bin" / "chiplab"
    venv_command.parent.mkdir(parents=True)
    venv_command.write_text("#!/usr/bin/env python3\n")
    launcher = tmp_path / "local-bin" / "chiplab"
    launcher.parent.mkdir()
    launcher.write_text(f'#!/bin/sh\nexec "{venv_command}" "$@"\n')
    assert lab_version(launcher) == "chiplab 9.9.1"
    assert lab_version(venv_command) == "chiplab 9.9.1"
    assert lab_version(tmp_path / "nowhere" / "chiplab") == "chiplab, version unknown"


def test_skill_ships_as_package_data() -> None:
    """The skill is found through the package's resources, wherever the package is installed."""
    root = skill_files()
    assert root.is_dir()
    names = {p.name for p in root.iterdir()}
    assert {"SKILL.md", "references"} <= names
    assert (root / "references" / "workflow.md").is_file()
    assert not (root / "references" / "tools.md").is_file()  # copied from the lab at install time


class _SkillCheckBackend:
    """Stands in for a harness: records the skill folders present when it starts."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.seen: list[str] = []

    async def run(self, spec: AgentSpec, sink: Any) -> AgentResult:
        assert spec.workdir is not None
        self.seen = sorted(str(p.relative_to(spec.workdir)) for p in spec.workdir.rglob("SKILL.md"))
        return AgentResult(agent=spec.name)

    async def close(self) -> None:
        return None


@pytest.mark.parametrize(
    ("harness", "expected"),
    [
        ("claude_cli", [".claude/plugins/chipin/skills/chiplab/SKILL.md"]),
        ("openrouter", [".agents/skills/chiplab/SKILL.md"]),
        ("stub", []),
    ],
)
async def test_the_runner_installs_the_skill_before_the_agent_starts(
    tmp_path: Path, config: BackendConfig, monkeypatch: pytest.MonkeyPatch, harness: str, expected: list[str]
) -> None:
    for name, value in _lab_env(tmp_path).items():
        monkeypatch.setenv(name, value)
    backend = _SkillCheckBackend(harness)
    monkeypatch.setattr(local_runner, "backend_for", lambda *a, **k: backend)
    run = RunDir.create(config.resolved_runs_dir(), "skill-run")
    await runner_for(config, "local").run(AgentSpec(name="a", prompts=["p"]), run)
    assert backend.seen == expected
    # A working folder outside the run folder gets nothing.
    outside = tmp_path / "elsewhere"
    spec = AgentSpec(name="a", prompts=["p"], backend=harness, workdir=outside)
    await runner_for(config, "local").run(spec, RunDir.create(config.resolved_runs_dir(), "other"))
    assert backend.seen == []


async def test_the_runner_installs_nothing_with_the_lab_off(
    tmp_path: Path, config: BackendConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    monkeypatch.delenv(CHIPLAB_BIN_ENV, raising=False)
    backend = _SkillCheckBackend("claude_cli")
    monkeypatch.setattr(local_runner, "backend_for", lambda *a, **k: backend)
    run = RunDir.create(config.resolved_runs_dir(), "off-run")
    await runner_for(config, "local").run(AgentSpec(name="a", prompts=["p"]), run)
    assert backend.seen == []
    assert list(run.workspace.iterdir()) == []


def test_claude_loads_the_skill_as_a_plugin_without_setting_sources(tmp_path: Path) -> None:
    """The skill comes in by ``--plugin-dir``; the setting sources stay as configured.

    The ``project`` source would load every CLAUDE.md above the run folder and
    the user's own, so a run with the skill must not add it.
    """
    cli = ClaudeCliConfig()
    workdir = tmp_path / "ws"
    spec = AgentSpec(name="a", prompts=["p"], workdir=workdir)
    argv = build_argv(spec, cli, session_id="sid", resume=False)
    assert plugin_dirs(spec) == [] and "--plugin-dir" not in argv
    install_skill(workdir, "claude_cli", _lab_env(tmp_path / "lab"))
    root = (workdir / ".claude" / "plugins" / CLAUDE_PLUGIN_NAME).resolve()
    assert plugin_dirs(spec) == [root]
    manifest = json.loads((root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["name"] == CLAUDE_PLUGIN_NAME
    assert (root / "skills" / "chiplab" / "SKILL.md").is_file()
    for resume in (False, True):
        argv = build_argv(spec, cli, session_id="sid", resume=resume)
        assert argv[argv.index("--plugin-dir") + 1] == str(root)
        assert argv[argv.index("--setting-sources") + 1] == ""
    configured = cli.model_copy(update={"setting_sources": ["user"]})
    argv = build_argv(spec, configured, session_id="sid", resume=False)
    assert argv[argv.index("--setting-sources") + 1] == "user"


def test_openhands_agent_gets_the_skill_in_its_context(tmp_path: Path, config: BackendConfig) -> None:
    """The agent a run builds lists the skill (name, description) and can load its body."""
    pytest.importorskip("openhands.sdk")
    from chipin_backend.agents.openrouter_agent import OpenRouterAgentBackend, workspace_skills
    from chipin_backend.llm.providers import resolve_provider

    workdir = tmp_path / "ws"
    workdir.mkdir()
    assert workspace_skills(workdir) == []
    install_skill(workdir, "openrouter", _lab_env(tmp_path / "lab"))
    [skill] = workspace_skills(workdir)
    assert skill.name == "chiplab" and skill.is_agentskills_format
    assert REQUIRED_CHIP_REPORT in " ".join(skill.content.split())
    backend = OpenRouterAgentBackend(config.agents)
    spec = AgentSpec(name="a", prompts=["p"], workdir=workdir)
    provider = resolve_provider(config.providers, None)
    agent = backend._build_agent(spec, "openrouter/openai/gpt-4o-mini", "not-a-key", provider)
    assert [s.name for s in agent.agent_context.skills] == ["chiplab"]
    context = agent.dynamic_context or ""
    assert "<available_skills>" in context and "<name>chiplab</name>" in context
    assert "invoke_skill" in context


def test_skill_export_command(
    tmp_path: Path, run_config: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    for name, value in _lab_env(tmp_path).items():
        monkeypatch.setenv(name, value)
    target = tmp_path / "project" / ".claude" / "skills"
    assert main(["skill", "export", str(target), "--config", str(run_config)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out == {"skill": str(target / "chiplab"), "tools_reference": True}
    assert (target / "chiplab" / "SKILL.md").read_text() == _skill_md()
    assert (target / "chiplab" / TOOLS_REFERENCE).read_text().rstrip().endswith(LAB_REFERENCE)
    # Never into a tool folder of the home directory.
    home = tmp_path / "home"
    for folder in (home / ".claude" / "skills", home / ".agents" / "skills", home / ".openhands"):
        assert main(["skill", "export", str(folder), "--config", str(run_config)]) == 2
    assert not home.exists()
    # With the lab off the skill is still written, without the lab's reference.
    monkeypatch.delenv(CHIPLAB_BIN_ENV)
    plain = tmp_path / "plain"
    assert main(["skill", "export", str(plain), "--config", str(run_config)]) == 0
    assert json.loads(capsys.readouterr().out)["tools_reference"] is False
    assert (plain / "chiplab" / "SKILL.md").is_file()
