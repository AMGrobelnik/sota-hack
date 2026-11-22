"""Chippy, the helper agent: tools on recorded runs, bounds, actions, proposals,
suggestions, the HTTP stream and its limits. No model is called: a scripted
model stands in, and the OpenRouter ladder runs against a mock transport."""

from __future__ import annotations

import json
import shutil
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

import httpx
import pytest
from aiohttp.test_utils import TestClient, TestServer

from chipin_backend.api.config import ApiConfig, load_api_config
from chipin_backend.api.helper import HELPER, Conversations, HelperConfig
from chipin_backend.api.helper_model import ModelReply, OpenRouterLadder, Rung, ToolCall
from chipin_backend.api.helper_tools import (
    TOOL_NAMES,
    HelperTools,
    RunStore,
    ToolError,
    ToolLimits,
    clip_result,
    product_sections,
    run_tool,
)
from chipin_backend.api.helper_ui import ELEMENTS, UiActions, ViewContext, parse_view, suggestions
from chipin_backend.api.server import TOKEN_HEADER, create_app
from chipin_backend.config import BackendConfig

FIXTURES = Path(__file__).parent / "fixtures" / "helper_runs"
RUN_A = "20261122-024215-7904d4"  # three designs, designs.json, simulated data
RUN_B = "20261122-015547-0f2ac6"  # designs only from metric events
TOKEN = "helper-test-token"


@pytest.fixture
def runs(tmp_path: Path) -> Path:
    root = tmp_path / "runs"
    shutil.copytree(FIXTURES, root)
    return root


@pytest.fixture
def tools(runs: Path) -> HelperTools:
    return HelperTools(RunStore(runs))


class Scripted:
    """A model that plays canned replies, recording what it was sent."""

    def __init__(self, replies: list[ModelReply | Callable[[list[dict[str, Any]]], ModelReply]]) -> None:
        self.replies = list(replies)
        self.calls: list[dict[str, Any]] = []

    async def stream(
        self, *, messages: list[dict[str, Any]], tools: Any, tool_choice: str
    ) -> AsyncIterator[dict[str, Any]]:
        self.calls.append(
            {"messages": [dict(m) for m in messages], "tool_choice": tool_choice, "tools": tools}
        )
        nxt = self.replies.pop(0) if self.replies else ModelReply(text="(no more script)")
        reply = nxt(messages) if callable(nxt) else nxt
        if reply.text and not reply.tool_calls:
            for word in reply.text.split(" "):
                yield {"type": "delta", "text": word + " "}
            reply = ModelReply(text=reply.text, model=reply.model, usage=reply.usage, cost_usd=reply.cost_usd)
        yield {"type": "reply", "reply": reply}


def call(name: str, **arguments: Any) -> ModelReply:
    return ModelReply(tool_calls=[ToolCall(id=f"c-{name}", name=name, arguments=arguments)], cost_usd=0.001)


def answer(text: str, cost: float = 0.001) -> ModelReply:
    return ModelReply(text=text, model="scripted", cost_usd=cost, usage={"tokens_in": 10, "tokens_out": 5})


async def _client(
    config: BackendConfig, runs: Path, model: Any, helper: HelperConfig | None = None
) -> TestClient:
    cfg = config.model_copy(update={"runs_dir": runs})
    api = ApiConfig(helper=helper or HelperConfig())
    app = create_app(cfg, api, token=TOKEN, agent="stub")
    app[HELPER].model = model
    return TestClient(TestServer(app))


async def _ask(
    client: TestClient, text: str, view: dict[str, Any] | None = None, cid: str | None = "c1"
) -> list[dict[str, Any]]:
    body: dict[str, Any] = {"text": text, "view": view or {}}
    if cid is not None:
        body["conversation_id"] = cid
    resp = await client.post("/api/helper/messages", json=body, headers={TOKEN_HEADER: TOKEN})
    assert resp.status == 200, await resp.text()
    assert resp.headers["Content-Type"].startswith("text/event-stream")
    raw = await resp.text()
    return [json.loads(line[6:]) for line in raw.splitlines() if line.startswith("data: ")]


def _text(frames: list[dict[str, Any]]) -> str:
    return "".join(f["delta"] for f in frames if f["type"] == "text").strip()


# ---------------------------------------------------------------- tools on recorded runs


def test_list_runs_and_facts(tools: HelperTools) -> None:
    listed = tools.list_runs()["runs"]
    assert [r["id"] for r in listed] == [RUN_A, RUN_B]
    assert listed[0]["chosen_chip"] == "1b05ecf2359a"
    facts = tools.get_run(RUN_A)
    assert facts["status"] == "succeeded" and facts["data"] == "simulated" and facts["designs"] == 3
    assert facts["stages"]["verify"] == "done"
    assert tools.get_run(RUN_B)["data"] == "simulated"  # said in the brief


def test_spec_and_stages(tools: HelperTools) -> None:
    spec = tools.get_spec(RUN_A)["spec_json"]
    assert {t["metric"] for t in spec["targets"]} == {"sensitivity", "fa_per_hour"}
    stages = tools.get_stages(RUN_B)["stages"]
    assert [s["stage"] for s in stages] == [
        "spec",
        "reference",
        "propose",
        "finetune",
        "compile",
        "verify",
        "report",
    ]


def test_designs_name_the_smallest_and_the_chosen_with_their_basis(tools: HelperTools) -> None:
    out = tools.get_designs(RUN_A)
    assert out["smallest_by_gates"] == "e00baa02f14a" and out["chosen"] == "1b05ecf2359a"
    by_id = {d["id"]: d for d in out["designs"]}
    chosen = by_id["1b05ecf2359a"]
    assert chosen["chosen"] and chosen["gates"] == {"value": 237, "basis": "measured"}
    assert chosen["gates_estimated"]["basis"] == "estimate"
    assert chosen["scores"]["sensitivity"] == {"value": 1.0, "basis": "measured on simulated data"}
    assert by_id["e00baa02f14a"]["counts"]["events_caught"] == 0
    fallback = tools.get_designs(RUN_B)
    assert fallback["smallest_by_gates"] == "e51a3da485f2" and len(fallback["designs"]) == 2


def test_design_detail_chosen_metrics_summaries(tools: HelperTools) -> None:
    design = tools.get_design(RUN_A, "1b05ecf2359a")
    assert [p["id"] for p in design["per_patient"]] == ["p4", "p5"]
    assert design["per_patient"][1]["false_alarms"] == 1 and design["targets"]
    assert "workspace/chips/1b05ecf2359a/report.md" in design["chip_files"]
    with pytest.raises(ToolError):
        tools.get_design(RUN_A, "nope")
    chosen = tools.get_chosen(RUN_B)
    assert chosen["chosen_chip"] == "e51a3da485f2"
    assert chosen["design"]["metric_events"]["area_um2"]["basis"] == "estimate"
    rows = tools.get_metrics(RUN_B, design_id="e51a3da485f2", key="gates")["rows"]
    assert rows and all(r["chip"] == "e51a3da485f2" for r in rows)
    assert "1b05ecf2359a" in tools.get_summaries(RUN_A)["final_summary"]


def test_report_files_search_compare_facts(tools: HelperTools) -> None:
    report = tools.get_report(RUN_A)
    assert report["text"].startswith("# ChipIn report") and "next_offset" in report
    paths = [f["path"] for f in tools.list_files(RUN_A)["files"]]
    assert "workspace/report.md" in paths and "events.jsonl" in paths
    assert not any(p.startswith("workspace/.") or p == "agent_events.jsonl" for p in paths)
    assert tools.read_file(RUN_A, "workspace/spec.json")["text"].lstrip().startswith("{")
    hits = tools.search_messages(RUN_A, "EMG line length")["hits"]
    assert hits and "EMG" in hits[0]["text"]
    pair = tools.compare_runs(RUN_A, RUN_B)["runs"]
    assert [p["chosen_chip"] for p in pair] == ["1b05ecf2359a", "e51a3da485f2"]
    assert set(product_sections()) >= {
        "product",
        "stages",
        "marks",
        "tabs",
        "flow",
        "presets",
        "checks",
        "limits",
    }
    assert "estimate" in tools.product_facts("marks")["sections"]["marks"].lower()


# ---------------------------------------------------------------- bounds and path escapes


def test_file_reads_are_windowed_and_page_through(runs: Path) -> None:
    tools = HelperTools(RunStore(runs, ToolLimits(file_window_bytes=500)))
    size = (runs / RUN_A / "workspace" / "report.md").stat().st_size
    text, offset, reads = "", 0, 0
    while True:
        part = tools.read_file(RUN_A, "workspace/report.md", offset=offset)
        assert len(part["text"].encode()) <= 500
        text += part["text"]
        reads += 1
        if "next_offset" not in part:
            break
        offset = part["next_offset"]
    assert reads > 3 and len(text.encode()) == size


def test_every_result_fits_the_cap(tools: HelperTools) -> None:
    for name, args in [
        ("get_designs", {"run_id": RUN_A}),
        ("list_files", {"run_id": RUN_A}),
        ("get_metrics", {"run_id": RUN_A}),
        ("read_file", {"run_id": RUN_A, "path": "events.jsonl"}),
    ]:
        assert len(json.dumps(run_tool(tools, name, args), ensure_ascii=False).encode()) <= 4096
    huge = {"rows": [{"text": "x" * 900, "n": i} for i in range(500)]}
    clipped = clip_result(huge, ToolLimits())
    assert clipped["truncated"] and len(json.dumps(clipped).encode()) <= 4096
    wide = clip_result({f"k{i}": "v" * 500 for i in range(100)}, ToolLimits())
    assert "json_prefix" in wide and len(json.dumps(wide).encode()) <= 4096
    assert len(clip_result("y" * 50_000, ToolLimits())) <= 601


@pytest.mark.parametrize(
    "path",
    [
        "../" + RUN_B + "/api.json",
        "/etc/hosts",
        "workspace/../../" + RUN_B + "/api.json",
        "~/x",
        "workspace/.claude/settings.json",
        "workspace/CLAUDE.md",
        "agent_events.jsonl",
        "workspace\\report.md",
    ],
)
def test_reads_outside_the_run_are_refused(tools: HelperTools, runs: Path, path: str) -> None:
    (runs / RUN_A / "workspace" / ".claude").mkdir(exist_ok=True)
    (runs / RUN_A / "workspace" / ".claude" / "settings.json").write_text("{}")
    (runs / RUN_A / "workspace" / "CLAUDE.md").write_text("private")
    (runs / RUN_A / "agent_events.jsonl").write_text("{}")
    with pytest.raises(ToolError):
        tools.read_file(RUN_A, path)


def test_a_symlink_out_of_the_runs_folder_is_refused(tools: HelperTools, runs: Path, tmp_path: Path) -> None:
    secret = tmp_path / "outside.txt"
    secret.write_text("outside")
    (runs / RUN_A / "workspace" / "link.txt").symlink_to(secret)
    with pytest.raises(ToolError, match="outside"):
        tools.read_file(RUN_A, "workspace/link.txt")
    for bad in ("../x", "..", "a/b", "", 7):
        with pytest.raises(ToolError):
            tools.get_run(bad)  # type: ignore[arg-type]


def test_unknown_tools_and_bad_arguments_are_tool_errors(tools: HelperTools) -> None:
    with pytest.raises(ToolError):
        run_tool(tools, "delete_run", {"run_id": RUN_A})
    with pytest.raises(ToolError):
        run_tool(tools, "get_run", {"run": RUN_A})
    assert "list_runs" in TOOL_NAMES


# ---------------------------------------------------------------- actions and proposals


def test_view_actions_are_well_formed(tools: HelperTools) -> None:
    ui = UiActions(tools, parse_view({"route": f"#/run/{RUN_A}/overview"}))
    item, result = ui.handle("ui_switch_tab", {"tab": "Chip"})
    assert item == {
        "type": "action",
        "id": "a1",
        "kind": "switch_tab",
        "run_id": RUN_A,
        "tab": "chip",
        "label": "Chip",
        "route": f"#/run/{RUN_A}/chip",
    }
    assert result["ok"]
    selected = ui.handle("ui_select_design", {"design_id": "1b05ecf2359a"})[0]
    assert selected["design_id"] == "1b05ecf2359a" and selected["route"] == f"#/run/{RUN_A}/chip"
    assert (
        ui.handle("ui_open_run", {"run_id": RUN_B, "tab": "where it fails"})[0]["route"]
        == f"#/run/{RUN_B}/patients"
    )
    assert ui.handle("ui_set_playback", {"seconds": 42})[0]["seconds"] == 42.0
    assert ui.handle("ui_open_file", {"path": "workspace/report.md"})[0]["path"] == "workspace/report.md"
    assert ui.handle("ui_new_spec", {"brief": "An AF patch"})[0] == {
        "type": "action",
        "id": "a6",
        "kind": "new_spec",
        "brief": "An AF patch",
        "route": "#/new/1",
    }
    assert ui.handle("ui_highlight", {"element_id": "tchart"})[0]["label"] == ELEMENTS["tchart"]
    assert ui.handle("ui_go_to", {"route": "#/new/3"})[0]["route"] == "#/new/3"


@pytest.mark.parametrize(
    ("name", "args"),
    [
        ("ui_switch_tab", {"tab": "billing"}),
        ("ui_select_design", {"design_id": "zzz"}),
        ("ui_open_file", {"path": "events.jsonl"}),
        ("ui_open_file", {"path": "../x"}),
        ("ui_highlight", {"element_id": "body"}),
        ("ui_go_to", {"route": "https://example.org"}),
        ("ui_go_to", {"route": "#/run/nope/chip"}),
        ("ui_set_playback", {"seconds": -1}),
        ("ui_open_run", {"run_id": "../etc"}),
        ("ui_new_spec", {"brief": "  "}),
        ("ui_switch_tab", {"tab": "chip", "extra": 1}),
    ],
)
def test_invalid_actions_are_refused(tools: HelperTools, name: str, args: dict[str, Any]) -> None:
    ui = UiActions(tools, parse_view({"route": f"#/run/{RUN_A}/overview"}))
    with pytest.raises(ToolError):
        ui.handle(name, args)


def test_proposals_describe_a_request_and_need_a_running_run(tools: HelperTools, runs: Path) -> None:
    ui = UiActions(tools, parse_view({"route": f"#/run/{RUN_A}/overview"}))
    item, result = ui.handle("propose_start_run", {"brief": "A tiny AF patch", "preset": "pro"})
    assert item["type"] == "proposal" and item["executed"] is False
    assert item["request"] == {
        "method": "POST",
        "path": "/api/runs",
        "body": {"prompt": "A tiny AF patch", "preset": "pro"},
    }
    assert "nothing happens" in result["note"]
    with pytest.raises(ToolError, match="succeeded"):
        ui.handle("propose_stop_run", {})
    with pytest.raises(ToolError):
        ui.handle("propose_message_agent", {"text": "try a smaller model"})
    live = runs / "20261122-090000-aaaaaa"
    live.mkdir()
    (live / "api.json").write_text(json.dumps({"id": live.name, "status": "running", "prompt": "x"}))
    (live / "events.jsonl").write_text("")
    msg = ui.handle("propose_message_agent", {"text": "try fewer gates", "run_id": live.name})[0]
    assert msg["request"]["path"] == f"/api/runs/{live.name}/messages" and msg["executed"] is False
    assert ui.handle("propose_stop_run", {"run_id": live.name})[0]["request"]["path"].endswith("/stop")


# ---------------------------------------------------------------- suggestions


def test_suggestions_follow_the_view_and_the_run_state(tools: HelperTools, runs: Path) -> None:
    def ids(view: dict[str, Any]) -> list[str]:
        return [s["id"] for s in suggestions(tools, parse_view(view))]

    assert ids({"route": "#/"})[:2] == ["what", "latest"]
    assert ids({"route": "#/new/3"})[0] == "flow-targets"
    assert ids({"route": "#/new/spec", "spec_draft": {"device": "patch"}})[0] == "flow-spec"
    finished = suggestions(tools, parse_view({"route": f"#/run/{RUN_A}/overview"}))
    assert [s["id"] for s in finished][:3] == ["chosen", "smallest", "skipped"]
    assert RUN_A in finished[0]["prompt"]
    picked = ids({"route": f"#/run/{RUN_A}/overview", "design_id": "c5a5f861d110"})
    assert picked[:2] == ["design", "design-chip"]
    fails = suggestions(tools, parse_view({"route": f"#/run/{RUN_A}/patients"}))
    assert fails[0]["id"] == "fails" and "1b05ecf2359a" in fails[0]["prompt"]
    live = runs / "20261122-090000-aaaaaa"
    live.mkdir()
    (live / "api.json").write_text(json.dumps({"id": live.name, "status": "running", "prompt": "x"}))
    (live / "events.jsonl").write_text("")
    assert ids({"route": f"#/run/{live.name}/overview"})[:2] == ["now", "so-far"]
    assert ids({"route": "#/configure"})[0] == "presets"
    assert all(
        len(ids(v)) <= 4 for v in ({"route": "#/"}, {"route": f"#/run/{RUN_A}/patients", "design_id": "x"})
    )


def test_view_context_is_parsed_and_bounded() -> None:
    view = parse_view(
        {
            "route": f"#/run/{RUN_A}/patients",
            "design_id": "1b05ecf2359a",
            "playback_s": 12.345,
            "spec_draft": {"brief": "x" * 10_000},
        }
    )
    assert (view.page, view.run_id, view.tab, view.playback_s) == ("run", RUN_A, "patients", 12.35)
    assert "truncated" in view.spec_draft  # type: ignore[operator]
    assert view.for_prompt()["tab_label"] == "Where it fails"
    assert parse_view("nonsense") == ViewContext()
    assert parse_view({"route": "#/new/2"}).flow_step == "2"


# ---------------------------------------------------------------- the HTTP route


async def test_helper_routes_need_the_token(config: BackendConfig, runs: Path) -> None:
    async with await _client(config, runs, Scripted([])) as client:
        for path in ("/api/helper/messages", "/api/helper/suggestions"):
            resp = await client.post(path, json={"text": "hi"})
            assert resp.status == 401
            resp = await client.post(path, json={"text": "hi"}, headers={TOKEN_HEADER: "wrong"})
            assert resp.status == 401


async def test_a_turn_streams_tools_actions_and_an_answer(config: BackendConfig, runs: Path) -> None:
    model = Scripted(
        [
            call("get_chosen", run_id=RUN_A),
            ModelReply(
                tool_calls=[
                    ToolCall(id="s1", name="ui_select_design", arguments={"design_id": "1b05ecf2359a"}),
                    ToolCall(id="s2", name="ui_switch_tab", arguments={"tab": "chip"}),
                ]
            ),
            answer("Opened the Chip tab for `1b05ecf2359a`, 237 gates (measured)."),
        ]
    )
    async with await _client(config, runs, model) as client:
        frames = await _ask(
            client, "open the chip tab for the chosen design", {"route": f"#/run/{RUN_A}/overview"}
        )
    assert frames[0] == {"type": "start", "conversation_id": "c1"} and frames[-1]["type"] == "done"
    actions = [f for f in frames if f["type"] == "action"]
    assert [a["kind"] for a in actions] == ["select_design", "switch_tab"]
    assert actions[1]["route"] == f"#/run/{RUN_A}/chip"
    assert [f["name"] for f in frames if f["type"] == "tool"] == [
        "get_chosen",
        "ui_select_design",
        "ui_switch_tab",
    ]
    assert _text(frames).startswith("Opened the Chip tab")
    assert frames[-1]["cost_usd"] == pytest.approx(0.002)
    first = model.calls[0]["messages"]
    assert "Chippy" in first[0]["content"] and RUN_A in first[1]["content"]  # instructions, view and open run
    tool_msg = model.calls[1]["messages"][-1]
    assert tool_msg["role"] == "tool" and "1b05ecf2359a" in tool_msg["content"]


async def test_proposals_are_never_executed_by_the_server(
    config: BackendConfig, runs: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from chipin_backend.api.manager import RunManager

    def forbidden(*_a: Any, **_k: Any) -> Any:
        raise AssertionError("the helper must not act on runs")

    for name in ("start", "message", "stop"):
        monkeypatch.setattr(RunManager, name, forbidden)
    before = sorted(p.name for p in runs.iterdir())
    model = Scripted(
        [
            ModelReply(
                tool_calls=[
                    ToolCall(
                        id="p1", name="propose_start_run", arguments={"brief": "AF patch", "preset": "lite"}
                    ),
                    ToolCall(id="p2", name="propose_stop_run", arguments={"run_id": RUN_A}),
                ]
            ),
            answer("Press the button to start it."),
        ]
    )
    async with await _client(config, runs, model) as client:
        frames = await _ask(client, "start a run for an AF patch and stop the old one")
    proposals = [f for f in frames if f["type"] == "proposal"]
    assert len(proposals) == 1 and proposals[0]["kind"] == "start_run" and proposals[0]["executed"] is False
    assert proposals[0]["request"]["path"] == "/api/runs"
    stop_result = json.loads(model.calls[1]["messages"][-1]["content"])
    assert "error" in stop_result and "succeeded" in stop_result["error"]
    assert sorted(p.name for p in runs.iterdir()) == before


async def test_suggestions_route(config: BackendConfig, runs: Path) -> None:
    async with await _client(config, runs, Scripted([])) as client:
        resp = await client.post(
            "/api/helper/suggestions",
            json={"view": {"route": f"#/run/{RUN_A}/overview"}},
            headers={TOKEN_HEADER: TOKEN},
        )
        body = await resp.json()
    assert resp.status == 200 and body["suggestions"][0]["id"] == "chosen"


async def test_no_key_gives_plain_error_text(config: BackendConfig, runs: Path) -> None:
    async with await _client(config, runs, None) as client:
        frames = await _ask(client, "hello")
        health = await (await client.get("/api/health")).json()
    errors = [f for f in frames if f["type"] == "error"]
    assert errors and "OPENROUTER_API_KEY is not set" in errors[0]["message"]
    assert frames[-1]["type"] == "done" and health["helper"] is False


async def test_a_failing_model_ends_in_plain_text(config: BackendConfig, runs: Path) -> None:
    class Broken:
        async def stream(self, **_k: Any) -> AsyncIterator[dict[str, Any]]:
            raise RuntimeError("boom")
            yield {}  # pragma: no cover

    for model in (Broken(), Scripted([ModelReply(error="no model answered")])):
        async with await _client(config, runs, model) as client:
            frames = await _ask(client, "hello")
        assert [f["type"] for f in frames][-2:] == ["error", "done"]
        assert "could not reach its model" in frames[-2]["message"]


async def test_conversation_and_daily_caps(config: BackendConfig, runs: Path) -> None:
    helper = HelperConfig(conversation_usd=0.002, daily_usd=0.004)
    model = Scripted([answer("one", 0.002), answer("two", 0.002), answer("three", 0.002)])
    async with await _client(config, runs, model, helper) as client:
        assert _text(await _ask(client, "q1", cid="a")) == "one"
        capped = await _ask(client, "q2", cid="a")
        assert "spending limit" in capped[1]["message"] and capped[-1]["finish_reason"] == "limit"
        assert _text(await _ask(client, "q3", cid="b")) == "two"
        daily = await _ask(client, "q4", cid="c")
        assert "today's spending limit" in daily[1]["message"]
    assert len(model.calls) == 2


async def test_history_is_kept_per_conversation_and_bounded(config: BackendConfig, runs: Path) -> None:
    helper = HelperConfig(history_messages=4)
    model = Scripted([answer(f"a{i}") for i in range(4)])
    async with await _client(config, runs, model, helper) as client:
        for i in range(3):
            await _ask(client, f"q{i}", cid="h")
        await _ask(client, "other", cid="k")
    third = [m["content"] for m in model.calls[2]["messages"][2:]]
    assert third == ["q0", "a0", "q1", "a1", "q2"]
    assert [m["content"] for m in model.calls[3]["messages"][2:]] == ["other"]
    store = Conversations(limit=2, history=4)
    for cid in ("x", "y", "z"):
        store.get(cid)
    assert list(store.items) == ["y", "z"]


async def test_tool_roundtrips_end_with_a_closing_answer(config: BackendConfig, runs: Path) -> None:
    helper = HelperConfig(max_tool_roundtrips=2)
    model = Scripted(
        [call("list_runs", limit=i + 1) for i in range(2)] + [answer("From what I read: two runs.")]
    )
    async with await _client(config, runs, model, helper) as client:
        frames = await _ask(client, "how many runs?")
    assert [c["tool_choice"] for c in model.calls] == ["auto", "auto", "none"]
    assert _text(frames) == "From what I read: two runs."


async def test_identical_calls_stop_the_turn(config: BackendConfig, runs: Path) -> None:
    model = Scripted([call("list_runs") for _ in range(5)])
    async with await _client(config, runs, model) as client:
        frames = await _ask(client, "loop")
    assert len(model.calls) == 3 and frames[-2]["type"] == "error" and "repeated" in frames[-2]["message"]


async def test_request_limits(config: BackendConfig, runs: Path) -> None:
    async with await _client(config, runs, Scripted([])) as client:
        h = {TOKEN_HEADER: TOKEN}
        assert (await client.post("/api/helper/messages", json={"text": ""}, headers=h)).status == 400
        assert (await client.post("/api/helper/messages", json={"text": "x" * 4001}, headers=h)).status == 413
        assert (await client.post("/api/helper/messages", data="x" * 70_000, headers=h)).status == 413
        bad_id = {"text": "hi", "conversation_id": "../x"}
        assert (await client.post("/api/helper/messages", json=bad_id, headers=h)).status == 400
        client.server.app[HELPER].conversations.get("busy").busy = True
        busy = {"text": "hi", "conversation_id": "busy"}
        assert (await client.post("/api/helper/messages", json=busy, headers=h)).status == 429
        frames = await _ask(client, "hi", cid=None)
    assert len(frames[0]["conversation_id"]) >= 12


def test_api_yaml_names_the_key_by_variable_only() -> None:
    cfg = load_api_config().helper
    assert cfg.key_env == "OPENROUTER_API_KEY"
    assert [r.model for r in cfg.rungs] == ["z-ai/glm-5.3-flash", "deepseek/deepseek-v4.1-flash"]
    assert cfg.rungs[0].providers == ["DigitalOcean", "Together"]


# ---------------------------------------------------------------- the OpenRouter ladder


def _sse_body(chunks: list[dict[str, Any]]) -> bytes:
    return b"".join(f"data: {json.dumps(c)}\n\n".encode() for c in chunks) + b"data: [DONE]\n\n"


async def test_ladder_pins_providers_streams_and_falls_back() -> None:
    sent: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        sent.append(payload)
        assert request.headers["Authorization"] == "Bearer test-key"
        if payload["provider"]["order"] == ["P1"]:
            return httpx.Response(503, text="busy")
        chunks = [
            {"choices": [{"delta": {"content": "Hel"}}]},
            {"choices": [{"delta": {"content": "lo"}}]},
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "t1",
                                    "function": {"name": "get_run", "arguments": '{"run_'},
                                }
                            ]
                        }
                    }
                ]
            },
            {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": 'id": "r"}'}}]}}]},
            {"choices": [], "usage": {"prompt_tokens": 100, "completion_tokens": 20, "cost": 0.00001}},
        ]
        return httpx.Response(200, content=_sse_body(chunks), headers={"content-type": "text/event-stream"})

    ladder = OpenRouterLadder(
        [Rung(model="m/one", providers=["P1", "P2"])],
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )
    events = [
        e
        async for e in ladder.stream(
            messages=[{"role": "user", "content": "hi"}], tools=[], tool_choice="auto"
        )
    ]
    assert [e["text"] for e in events if e["type"] == "delta"] == ["Hel", "lo"]
    reply = events[-1]["reply"]
    assert reply.text == "Hello" and reply.tool_calls[0].arguments == {"run_id": "r"}
    assert reply.cost_usd == pytest.approx(0.00001) and reply.usage == {"tokens_in": 100, "tokens_out": 20}
    assert [p["provider"] for p in sent] == [
        {"order": ["P1"], "allow_fallbacks": False},
        {"order": ["P2"], "allow_fallbacks": False},
    ]
    assert sent[0]["stream"] is True and sent[0]["usage"] == {"include": True} and sent[0]["model"] == "m/one"


async def test_ladder_reports_when_no_model_answers() -> None:
    ladder = OpenRouterLadder(
        [Rung(model="a", providers=["X"]), Rung(model="b", providers=["Y"])],
        api_key="k",
        transport=httpx.MockTransport(lambda _r: httpx.Response(500, text="down")),
    )
    events = [e async for e in ladder.stream(messages=[], tools=[], tool_choice="auto")]
    assert (
        events[-1]["reply"].error.startswith("no model answered") and "a via X" in events[-1]["reply"].error
    )
