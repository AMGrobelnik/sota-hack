"""Chippy reads the levels of summaries and names moments on the dashboard's playback clock.

A synthetic run: a 45-minute silence in the middle (skipped by the clock),
summary events at every level (an interim stage line replaced by its final
one) and a run line written after the run in ``summaries.jsonl``. No model is
called; a scripted model drives the one HTTP turn.
"""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from chipin_backend.api.helper_model import ModelReply, ToolCall
from chipin_backend.api.helper_tools import HelperTools, RunStore, ToolError, run_tool
from chipin_backend.api.helper_ui import UiActions, ViewContext
from chipin_backend.api.playback import IDLE_GAP_S, PlaybackClock, playback_time
from chipin_backend.config import BackendConfig
from test_helper import FIXTURES, RUN_A, Scripted, _ask, _client, answer, call

RUN = "20261122-100000-abc123"
T0 = datetime(2026, 11, 22, 10, 0, 0, tzinfo=UTC)
SILENCE = 45 * 60


def _ts(seconds: float) -> str:
    return (T0 + timedelta(seconds=seconds)).isoformat()


def _summary(sid: str, level: str, text: str, **extra: Any) -> dict[str, Any]:
    return {"type": "summary", "id": sid, "level": level, "text": text, "source": "model", **extra}


def _events(items: int = 0) -> list[dict[str, Any]]:
    """seq -> wall seconds after T0; the silence sits between seq 6 and seq 7."""
    rows: list[tuple[float, dict[str, Any]]] = [
        (0, {"type": "run.started", "prompt": "A tiny seizure flag on synthetic data."}),
        (1, {"type": "stage", "stage": "spec", "state": "started"}),
        (5, {"type": "message", "text": "Writing the spec for the gate budget."}),
        (10, {"type": "stage", "stage": "spec", "state": "done"}),
        (12, {"type": "stage", "stage": "propose", "state": "started"}),
        (20, {"type": "tool", "tool": "Bash", "input": {"command": "chiplab compile"}, "call_id": "t1"}),
        (20 + SILENCE + 10, {"type": "tool", "tool": "Bash", "output": "verified ok", "call_id": "t1"}),
        (20 + SILENCE + 20, {"type": "metric", "key": "gates", "value": 237, "chip": "d1"}),
    ]
    late = 20 + SILENCE + 21
    lines = [
        _summary("i6", "item", "Compiled the line-length design.", parent="g1", stage="propose", final=True),
        _summary(
            "g1",
            "group",
            "Compiled and verified d1.",
            parent="stage:propose",
            covers=["i6", "i7"],
            final=True,
        ),
        _summary(
            "stage:spec", "stage", "Spec written: 2 channels, gate budget 300.", parent="run", final=True
        ),
        _summary("stage:propose", "stage", "Proposing designs (interim).", parent="run", final=False),
        _summary(
            "batch:propose:1", "batch", "Two subagents tried thresholds.", parent="stage:propose", final=True
        ),
        _summary("agent:a1", "agent", "a1 built an energy threshold.", parent="batch:propose:1", final=True),
        _summary("g2", "group", "a1 compiled its design.", parent="agent:a1", agent="a1", final=True),
        _summary(
            "stage:propose",
            "stage",
            "Three designs proposed; d1 smallest at 237 gates.",
            parent="run",
            final=True,
        ),
        _summary("run", "run", "Run going: spec done, designs proposed.", final=False),
    ]
    for k in range(items):
        lines.append(_summary(f"i{100 + k}", "item", f"Item {k}: " + "detail " * 40, parent="g1", final=True))
    rows += [(late, line) for line in lines]
    rows.append((late + 1, {"type": "run.finished", "status": "succeeded", "summary": "Chose d1."}))
    return [{"seq": i, "ts": _ts(s), "run_id": RUN, **e} for i, (s, e) in enumerate(rows, start=1)]


def _write_run(
    root: Path, events: list[dict[str, Any]], replayed: list[dict[str, Any]] | None = None
) -> None:
    run = root / RUN
    run.mkdir(parents=True)
    (run / "api.json").write_text(json.dumps({"id": RUN, "status": "succeeded", "prompt": "x"}))
    (run / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))
    if replayed:
        (run / "summaries.jsonl").write_text("".join(json.dumps(s) + "\n" for s in replayed))


RUN_FINAL = _summary(
    "run",
    "run",
    "Chose d1, 237 gates, after spec and three proposals.",
    final=True,
    covers=["stage:spec", "stage:propose"],
)


@pytest.fixture
def runs(tmp_path: Path) -> Path:
    root = tmp_path / "runs"
    shutil.copytree(FIXTURES, root)
    _write_run(root, _events(), [RUN_FINAL])
    return root


@pytest.fixture
def tools(runs: Path) -> HelperTools:
    return HelperTools(RunStore(runs))


# ---------------------------------------------------------------- the playback clock


def test_the_clock_skips_silences_as_the_page_does() -> None:
    events = _events()
    clock = PlaybackClock.from_events(events)
    assert clock.at_seq(1) == 0.0 and clock.at_seq(6) == 20.0
    assert clock.at_seq(7) == 20.0 and clock.at_seq(8) == 30.0  # 45 minutes stepped over
    assert clock.gaps == [{"t": 20.0, "idle_s": SILENCE + 10.0}]
    assert clock.total_s == 32.0  # last event, run.finished
    assert playback_time(events, seq=8) == 30.0


def test_a_timestamp_maps_onto_the_clock() -> None:
    clock = PlaybackClock.from_events(_events())
    assert clock.at_ts(_ts(-5)) == 0.0  # before the run
    assert clock.at_ts(_ts(3)) == 3.0  # between events, real time
    assert clock.at_ts(_ts(20 + 600)) == 20.0  # inside the silence: where it starts
    assert clock.at_ts(_ts(20 + SILENCE + 15)) == 25.0
    assert clock.at_ts((T0 + timedelta(seconds=7)).timestamp()) == 7.0  # epoch seconds too
    end = 20 + SILENCE + 22
    assert clock.at_ts(_ts(end + 60)) == 92.0  # a live run's clock runs on to now
    assert clock.at_ts(_ts(end + IDLE_GAP_S + 1)) == 32.0  # unless that stretch is idle
    assert clock.at_ts("not a time") is None


def test_a_silence_exactly_at_the_limit_is_not_skipped() -> None:
    events = [
        {"seq": 1, "ts": _ts(0), "type": "run.started"},
        {"seq": 2, "ts": _ts(IDLE_GAP_S), "type": "message"},
        {"seq": 3, "ts": "", "type": "message"},  # no time: left out, as on the page
    ]
    clock = PlaybackClock.from_events(events)
    assert clock.at_seq(2) == float(IDLE_GAP_S) and not clock.gaps and clock.seqs == [1, 2]


# ---------------------------------------------------------------- get_summaries


def test_run_and_stage_lines_come_first_with_level_final_and_time(tools: HelperTools) -> None:
    out = tools.get_summaries(RUN)
    lines = out["lines"]
    assert [x["id"] for x in lines] == ["run", "stage:spec", "stage:propose"]
    run, spec, propose = lines
    assert run["level"] == "run" and run["final"] is True  # summaries.jsonl replaced the interim line
    assert run["text"].startswith("Chose d1")
    assert run["playback_s"] == 32.0  # a line written after the run sits at its end
    assert propose["final"] is True and propose["text"].startswith("Three designs")  # interim replaced
    assert spec["level"] == "stage" and spec["playback_s"] == 31.0
    assert out["levels"] == {"item": 1, "group": 2, "agent": 1, "batch": 1, "stage": 2, "run": 1}
    assert "drill" in out and "final_summary" not in out


@pytest.mark.parametrize(
    ("focus", "children"),
    [
        ("propose", ["g1", "batch:propose:1"]),
        ("stage:propose", ["g1", "batch:propose:1"]),
        ("batch:propose:1", ["agent:a1"]),
        ("a1", ["g2"]),
        ("g1", ["i6"]),
        ("run", ["stage:spec", "stage:propose"]),
    ],
)
def test_focus_opens_one_line_down(tools: HelperTools, focus: str, children: list[str]) -> None:
    out = tools.get_summaries(RUN, focus=focus)
    assert [x["id"] for x in out["lines"]] == children
    assert out["focus"]["id"] in (focus, f"stage:{focus}", f"agent:{focus}")
    assert all({"level", "final", "playback_s"} <= set(x) for x in out["lines"])


def test_level_and_stage_filter(tools: HelperTools) -> None:
    assert [x["id"] for x in tools.get_summaries(RUN, level="group")["lines"]] == ["g1", "g2"]
    assert [x["id"] for x in tools.get_summaries(RUN, stage="propose")["lines"]] == ["i6", "stage:propose"]


def test_bad_focus_level_or_stage_is_a_tool_error(tools: HelperTools) -> None:
    for args in ({"focus": "stage:nope"}, {"level": "chapter"}, {"stage": "layout"}):
        with pytest.raises(ToolError, match=r"summary|level|stage"):
            run_tool(tools, "get_summaries", {"run_id": RUN, **args})


def test_many_lines_are_clipped_whole_to_the_cap(tmp_path: Path) -> None:
    _write_run(tmp_path, _events(items=80))
    tools = HelperTools(RunStore(tmp_path))
    out = run_tool(tools, "get_summaries", {"run_id": RUN, "focus": "g1"})
    assert len(json.dumps(out, ensure_ascii=False).encode()) <= tools.limits.max_result_bytes
    assert out["lines"] and out["more"] > 0 and len(out["lines"]) + out["more"] == 81
    assert all(x["text"].endswith(" ") or x["id"] == "i6" for x in out["lines"])  # whole, not cut


def test_a_run_without_summary_events_keeps_the_old_fields(tools: HelperTools) -> None:
    out = tools.get_summaries(RUN_A)
    assert "1b05ecf2359a" in out["final_summary"] and "lines" not in out


# ---------------------------------------------------------------- times in other tools and the action


def test_read_tools_give_playback_times(tools: HelperTools) -> None:
    stages = {r["stage"]: r for r in tools.get_stages(RUN)["stages"]}
    assert stages["spec"]["started_playback_s"] == 1.0 and stages["spec"]["ended_playback_s"] == 10.0
    assert tools.get_metrics(RUN)["rows"][0]["playback_s"] == 30.0
    hit = tools.search_messages(RUN, "verified")["hits"][0]
    assert hit["seq"] == 7 and hit["playback_s"] == 20.0
    facts = tools.get_run(RUN)
    assert facts["playback_total_s"] == 32.0 and facts["idle_gaps_skipped"] == 1


def test_set_playback_takes_seconds_or_an_event_seq(tools: HelperTools) -> None:
    ui = UiActions(tools, ViewContext(page="run", run_id=RUN))
    item, result = ui.handle("ui_set_playback", {"seq": 8})
    assert (item["kind"], item["seconds"], item["seq"]) == ("set_playback", 30.0, 8)
    assert result["playback_s"] == 30.0
    assert ui.handle("ui_set_playback", {"seconds": 12.5})[0]["seconds"] == 12.5
    for bad in ({}, {"seq": 0}, {"seq": True}, {"seconds": -1}):
        with pytest.raises(ToolError, match=r"seq|seconds"):
            ui.handle("ui_set_playback", bad)


async def test_a_turn_reads_summaries_and_jumps_to_the_moment(config: BackendConfig, runs: Path) -> None:
    model = Scripted(
        [
            call("get_summaries", run_id=RUN, focus="propose"),
            ModelReply(tool_calls=[ToolCall(id="p1", name="ui_set_playback", arguments={"seq": 7})]),
            answer("Jumped to where d1 was verified."),
        ]
    )
    async with await _client(config, runs, model) as client:
        frames = await _ask(
            client, "show me when the design was verified", {"route": f"#/run/{RUN}/overview"}
        )
    actions = [f for f in frames if f["type"] == "action"]
    assert [(a["kind"], a["seconds"]) for a in actions] == [("set_playback", 20.0)]
    tool_msg = model.calls[1]["messages"][-1]
    sent = json.loads(tool_msg["content"])["result"]
    assert [x["id"] for x in sent["lines"]] == ["g1", "batch:propose:1"]
    assert frames[-1]["type"] == "done"
