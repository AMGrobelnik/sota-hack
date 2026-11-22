"""Nothing private is served or sent to a model; cost events carry one meaning; design variants."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from aiohttp.test_utils import TestClient, TestServer

from chipin_backend import scrub
from chipin_backend.api import spec
from chipin_backend.api.config import ApiConfig
from chipin_backend.api.costs import annotate_costs
from chipin_backend.api.designs import validate_design
from chipin_backend.api.events import EventLog
from chipin_backend.api.helper import (
    Conversations,
    DailySpend,
    HelperConfig,
    HelperState,
    instructions,
    run_turn,
)
from chipin_backend.api.helper_model import OpenRouterLadder, Rung
from chipin_backend.api.helper_tools import HelperTools, RunStore
from chipin_backend.api.helper_ui import UiActions, parse_view
from chipin_backend.api.server import MANAGER, TOKEN_HEADER, create_app
from chipin_backend.api.summaries import LIMIT, SUMMARY, latest, replay, summarise_folder
from chipin_backend.config import BackendConfig
from chipin_backend.llm.summarise import Summary, load_summary_settings, summarise
from chipin_backend.scrub import Scrubber
from test_helper import RUN_B, Scripted, answer, call
from test_helper import runs as runs
from test_summaries import Script, settings
from test_summaries import Scripted as SummaryScript

HOME = "/Users/janedoe"
USER = "janedoe"
HOST = "janes-laptop"
EMAIL = "jane.doe@example.org"
PRIVATE = (HOME, USER, HOST, EMAIL)
TOKEN = "privacy-test-token"
AUTH = {TOKEN_HEADER: TOKEN}
LEAKY = f"Ran cd {HOME}/projects/chip && ls -la (owner {USER} on {HOST}, mail {EMAIL})"


@pytest.fixture(autouse=True)
def private_machine(monkeypatch: pytest.MonkeyPatch) -> Scrubber:
    """This machine's scrubber, as if its home, user and host were Jane's."""
    scrubber = Scrubber(home=HOME, host_names=(HOST,), user=USER)
    monkeypatch.setattr(scrub, "_default", scrubber)
    return scrubber


def assert_clean(text: str) -> None:
    for secret in PRIVATE:
        assert secret not in text, f"{secret!r} leaked"


# ---------------------------------------------------------------- B1: the API


def _flex(config: BackendConfig) -> BackendConfig:
    flex = config.compute.flex.model_copy(update={"require_macos": False})
    return config.model_copy(update={"compute": config.compute.model_copy(update={"flex": flex})})


@pytest.fixture
async def client(config: BackendConfig) -> AsyncIterator[TestClient]:
    api = ApiConfig(keepalive_s=0.2, progress_poll_s=0.02, stub_step_s=0.01, run_timeout_s=60)
    app = create_app(_flex(config), api, token=TOKEN, agent="stub")
    async with TestClient(TestServer(app)) as c:
        yield c


async def _events(client: TestClient, run_id: str) -> str:
    stream = await client.get(f"/api/runs/{run_id}/events", params={"token": TOKEN})
    return await stream.text()


async def test_every_display_route_is_scrubbed_and_file_paths_still_work(client: TestClient) -> None:
    resp = await client.post(
        "/api/runs", json={"prompt": f"Build it. {LEAKY}", "preset": "lite"}, headers=AUTH
    )
    run_id = str((await resp.json())["id"])
    await _events(client, run_id)  # to the end of the run
    item = client.app[MANAGER].get(run_id)
    item.log.reopen()
    item.log.append("tool", call_id="t9", name="Bash", state="done", summary=LEAKY, detail=f"{HOME}/x")
    item.log.append("run.finished", status="succeeded", summary="again")
    (item.run.workspace / "notes.md").write_text(f"written in {HOME}/projects by {EMAIL}\n")

    stream = await _events(client, run_id)
    assert "Ran cd ~/projects/chip" in stream and "[user]" in stream
    bodies = [stream]
    for path in (
        f"/api/runs/{run_id}",
        f"/api/runs/{run_id}/history",
        f"/api/runs/{run_id}/summaries",
        f"/api/runs/{run_id}/designs",
        "/api/runs",
        "/api/history",
    ):
        resp = await client.get(path, headers=AUTH)
        assert resp.status == 200, path
        bodies.append(await resp.text())
    files = await (await client.get(f"/api/runs/{run_id}/files", headers=AUTH)).json()
    assert "workspace/notes.md" in [f["path"] for f in files["files"]]
    note = await client.get(f"/api/runs/{run_id}/file", params={"path": "workspace/notes.md"}, headers=AUTH)
    assert note.status == 200
    text = await note.text()
    assert text.startswith("written in ~/projects by [removed]")
    for body in [*bodies, text]:
        assert_clean(body)
    # the log on disk stays as written
    assert HOME in (item.run.path / "events.jsonl").read_text()


@pytest.mark.parametrize(
    ("raw", "want"),
    [
        ("Janedoe ran it", "[user] ran it"),
        ("JANEDOE ran it", "[user] ran it"),
        ("see janedoe_tools and janedoe2 and 2janedoe", "see [user]_tools and [user]2 and 2[user]"),
        ("on Janes-Laptop.local and JANES-LAPTOP_2", "on [host].local and [host]_2"),
        ("open file:///x?p=%2FUsers%2Fjanedoe%2Fprojects%2Fa.md", "open file:///x?p=~%2Fprojects%2Fa.md"),
        ("p=%2fusers%2fJaneDoe%2fdocs", "p=~%2fdocs"),
        ("p=%2Fhome%2Fsomeone%2Fdocs and /USERS/someone/x", "p=~%2Fdocs and ~/x"),
        ("p=%2FUsers%2Fjane%40doe%2Fdocs", "p=~%2Fdocs"),
    ],
)
def test_names_in_any_case_beside_underscores_and_encoded_home_paths(raw: str, want: str) -> None:
    assert Scrubber(home=HOME, host_names=(HOST,), user=USER).text(raw) == want


def test_longer_words_holding_a_name_are_left() -> None:
    scrubber = Scrubber(home="/Users/mira", host_names=("orbit",), user="mira")
    text = "Admiral Miranda renamed miras in orbital mira9 and 9mira, but 10mira9 too"
    assert (
        scrubber.text(text)
        == "Admiral Miranda renamed miras in orbital [user]9 and 9[user], but 10[user]9 too"
    )
    digits = Scrubber(home="/Users/dev42", host_names=(), user="dev42")
    assert digits.text("dev42 dev420 dev42_x Dev42a") == "[user] dev420 [user]_x [user]a"


def test_the_names_come_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOGNAME", "quillon")
    monkeypatch.setenv("USER", "quillon")
    assert Scrubber(home="/nowhere", host_names=()).text("Quillon and QUILLON_x") == "[user] and [user]_x"


# ---------------------------------------------------------------- B1: what leaves the machine


def _leaky_run() -> Script:
    s = Script()
    s.add("run.started", prompt=f"A chip for {USER}", agent="claude", runner="local")
    s.stage("propose", "started")
    s.tool(LEAKY, detail=f"total 8\ndrwxr-xr-x  {USER}  staff  {HOME}/projects")
    s.say(f"I looked in {HOME}/projects/chip and wrote to {EMAIL} from {HOST}. " * 4)
    s.stage("propose", "done")
    s.add("run.finished", status="succeeded", summary=f"Done in {HOME}/projects")
    return s


class Recording:
    """A summariser that records every request it is sent."""

    def __init__(self) -> None:
        self.sent: list[str] = []

    def unavailable(self) -> str:
        return ""

    async def __call__(self, *, system: str, prompt: str, max_tokens: int) -> Summary:
        self.sent.append(system + prompt)
        data = json.loads(prompt)
        if isinstance(data, list):
            return Summary(text=json.dumps({d["key"]: "line" for d in data}), cost_usd=0.0001, model="m")
        if "part" not in data:
            return Summary(text=json.dumps(dict.fromkeys(data, "title")), cost_usd=0.0001, model="m")
        return Summary(text="A summary.", cost_usd=0.0001, model="m")


async def test_the_summary_model_never_reads_a_private_detail() -> None:
    recording = Recording()
    await replay(_leaky_run().events, settings(max_calls_per_minute=10_000), recording)
    assert recording.sent
    for request in recording.sent:
        assert_clean(request)


async def test_the_summary_request_builder_scrubs_what_it_sends(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-not-real")
    sent: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request.content.decode())
        body = {"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}], "usage": {"cost": 0}}
        return httpx.Response(200, json=body)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        reply = await summarise(
            prompt=LEAKY, system=f"About {USER}", settings=load_summary_settings(), client=http
        )
    assert reply.text == "ok" and sent
    assert_clean(sent[0])
    assert "~/projects/chip" in sent[0]


async def test_chippy_never_sends_or_shows_a_private_detail(runs: Path) -> None:
    events = runs / RUN_B / "events.jsonl"
    lines = events.read_text().splitlines()
    last = json.loads(lines[-1])
    leak = {"seq": last["seq"] + 1, "ts": last["ts"], "run_id": RUN_B, "type": "message"}
    events.write_text("\n".join([*lines, json.dumps({**leak, "role": "agent", "text": LEAKY})]) + "\n")
    model = Scripted([call("search_messages", run_id=RUN_B, query="projects"), answer("Found it.")])
    state = HelperState(
        config=HelperConfig(),
        tools=HelperTools(RunStore(runs)),
        conversations=Conversations(10, 10),
        daily=DailySpend(),
        model=model,
    )
    frames = [
        f
        async for f in run_turn(
            state,
            state.conversations.get("c"),
            conversation_id="c",
            text=f"I am {USER}, mail me at {EMAIL}",
            view_raw={"run_id": RUN_B},
        )
    ]
    assert frames[-1]["type"] == "done" and len(model.calls) == 2
    tool_result = [m for m in model.calls[1]["messages"] if m.get("role") == "tool"]
    assert tool_result and "~/projects/chip" in tool_result[0]["content"]
    for request in model.calls:
        assert_clean(json.dumps(request["messages"]))
    assert_clean(json.dumps(frames))


async def test_chippy_request_builder_scrubs_what_it_sends() -> None:
    sent: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request.content.decode())
        chunk = {"choices": [{"delta": {"content": "hi"}}]}
        return httpx.Response(200, content=f"data: {json.dumps(chunk)}\n\ndata: [DONE]\n\n".encode())

    ladder = OpenRouterLadder([Rung(model="m")], api_key="k", transport=httpx.MockTransport(handler))
    messages = [{"role": "user", "content": LEAKY}]
    got = [e async for e in ladder.stream(messages=messages, tools=[], tool_choice="auto")]
    assert got[-1]["reply"].text == "hi" and sent
    assert_clean(sent[0])


# ---------------------------------------------------------------- B2: summary budget tiers


def _wide_run(subagents: int = 9, messages: int = 30) -> Script:
    """A long fan-out run: many long messages and tools, three batches, seven stages."""
    s = Script()
    s.add("run.started", prompt="A seizure flag chip", agent="claude", runner="local")
    n = 0
    for stage in ("spec", "reference", "propose", "finetune", "compile", "verify", "report"):
        s.stage(stage, "started")
        for k in range(messages // 7 + 1):
            s.say(f"Step {k} of {stage}: I trained the model and checked the held-out windows again. " * 3)
            s.tool(f"Ran python step{k}.py", detail="ok " * 50)
            s.add("metric", key=f"m{k}", value=0.9)
        if stage in ("propose", "finetune", "compile"):
            ids = []
            for _ in range(subagents // 3):
                n += 1
                sid = f"a{n}"
                ids.append(sid)
                s.add("subagent.started", id=sid, name=f"route{n}", stage=stage, strategy=f"route {n}")
                for k in range(4):
                    s.say(f"Route {n} step {k}: fitted the integer weights and scored them. " * 3, agent=sid)
                    s.tool(f"Ran python fit{k}.py", agent=sid, detail="ok")
            for sid in ids:
                s.add("subagent.finished", id=sid, stage=stage, state="done", result="done")
            s.add("stage.merged", stage=stage, ids=ids, kept=ids[:1], why="best")
        s.stage(stage, "done")
    s.add("run.finished", status="succeeded", summary="done")
    return s


async def test_tools_files_and_metrics_never_call_the_model() -> None:
    recording = Recording()
    s = Script()
    s.stage("propose", "started")
    s.tool("Ran python train.py", detail="epoch 1 loss 0.3\n" * 40)
    s.add("artifact", name="w.json", kind="weights", path="workspace/w.json")
    s.add("metric", key="accuracy", value=0.97)
    s.say("Short and clear.")
    s.stage("propose", "done")
    out, _ = await replay(s.events, settings(), recording)
    items = [x for x in latest(out).values() if x["level"] == "item"]
    assert items and all(x["source"] == "verbatim" for x in items)
    assert not any(r.startswith("You write the entries") for r in recording.sent)


async def test_closing_lines_are_model_written_within_the_cap_when_steps_run_out() -> None:
    class Dear(Recording):
        async def __call__(self, *, system: str, prompt: str, max_tokens: int) -> Summary:
            reply = await super().__call__(system=system, prompt=prompt, max_tokens=max_tokens)
            items = len(json.loads(prompt)) if system.startswith("You write the entries") else 0
            reply.cost_usd = 0.001 * items if items else 0.0005  # a step call pays per item
            return reply

    cap = 0.05
    out, stats = await replay(
        _wide_run().events, settings(max_usd_per_run=cap, max_calls_per_minute=10_000), Dear()
    )
    assert stats["usd"] <= cap
    assert stats["step_usd"] <= cap / 2
    reasons = [x["reason"] for x in out if x["type"] == LIMIT]
    assert "steps" in reasons and "cost" not in reasons
    by_id = latest(out)
    closing = [by_id["run"], *(by_id[f"stage:{n}"] for n in ("compile", "verify", "report"))]
    assert all(x["final"] and x["source"] == "model" for x in closing)
    after_steps = out[next(i for i, x in enumerate(out) if x.get("reason") == "steps") :]
    assert any(x.get("level") == "group" and x.get("source") == "model" for x in after_steps)
    assert {x["source"] for x in after_steps if x.get("level") == "item"} <= {"verbatim", "fallback"}


async def test_closing_lines_stay_model_written_with_a_cost_model_twice_as_dear() -> None:
    class Dearer(Recording):
        """A summary call costs $0.001 and a step $0.0005 per item, both doubled.

        Under the old fixed reserve (a fifth of the cap) one stage's final line fell back.
        """

        async def __call__(self, *, system: str, prompt: str, max_tokens: int) -> Summary:
            reply = await super().__call__(system=system, prompt=prompt, max_tokens=max_tokens)
            items = len(json.loads(prompt)) if system.startswith("You write the entries") else 0
            reply.cost_usd = 2 * (0.0005 * items if items else 0.001)
            return reply

    cap = 0.05
    out, stats = await replay(
        _wide_run().events, settings(max_usd_per_run=cap, max_calls_per_minute=10_000), Dearer()
    )
    assert stats["usd"] <= cap
    reasons = [x["reason"] for x in out if x["type"] == LIMIT]
    assert "cost" not in reasons and "closing" not in reasons
    by_id = latest(out)
    stages = ("spec", "reference", "propose", "finetune", "compile", "verify", "report")
    closing = [by_id["run"], *(by_id[f"stage:{n}"] for n in stages)]
    assert all(x["final"] and x["source"] == "model" for x in closing), [x["source"] for x in closing]


async def test_the_reserve_is_kept_for_the_closing_lines() -> None:
    class Flat(Recording):
        async def __call__(self, *, system: str, prompt: str, max_tokens: int) -> Summary:
            reply = await super().__call__(system=system, prompt=prompt, max_tokens=max_tokens)
            reply.cost_usd = 0.002
            return reply

    cap = 0.03
    out, stats = await replay(
        _wide_run().events, settings(max_usd_per_run=cap, max_calls_per_minute=10_000), Flat()
    )
    assert stats["usd"] <= cap
    reasons = [x["reason"] for x in out if x["type"] == LIMIT]
    assert "parts" in reasons
    parts_at = next(i for i, x in enumerate(out) if x.get("reason") == "parts")
    assert out[parts_at]["spent_usd"] <= cap * 0.8
    final_run = [x for x in out if x.get("type") == SUMMARY and x["id"] == "run" and x["final"]]
    assert final_run[-1]["source"] == "model"


# ---------------------------------------------------------------- B4: cost events


def _cost(seq: int, usd: float, **fields: Any) -> dict[str, Any]:
    return {"seq": seq, "type": "cost", "usd": usd, **fields}


def test_cost_events_carry_the_run_total_and_the_agents_part() -> None:
    events = [
        _cost(1, 0.10, agent="a1"),
        _cost(2, 0.20, agent="a2"),
        _cost(3, 0.25, agent="a1"),  # a1's own spend so far, not more on top
        _cost(4, 1.00),  # the orchestrator alone
        _cost(5, 1.45, subagents_usd=0.45, summaries_usd=0.05),  # the closing total
        {"seq": 6, "type": "run.finished"},
        _cost(7, 1.50, subagents_usd=0.45, summaries_usd=0.05, turn_usd=0.05),  # a follow-up
        _cost(8, 1.60),  # an older follow-up event without its parts: a total too
    ]
    out = [e for e in annotate_costs(events) if e["type"] == "cost"]
    assert [e["run_total_usd"] for e in out] == [0.1, 0.3, 0.45, 1.45, 1.5, 1.55, 1.65]
    assert [e["agent_usd"] for e in out] == [0.1, 0.2, 0.25, 1.0, 1.0, 1.05, 1.15]
    sources = [x for x in events if x["type"] == "cost"]
    assert all(e["usd"] == src["usd"] for e, src in zip(out, sources, strict=True))


async def test_the_event_log_adds_cost_fields_live_and_to_older_runs(tmp_path: Path) -> None:
    loop = asyncio.get_running_loop()
    path = tmp_path / "events.jsonl"
    log = EventLog(path, "r", loop)
    log.append("cost", usd=0.2, agent="a1")
    log.append("cost", usd=1.2, subagents_usd=0.2)
    assert [e["run_total_usd"] for e in log.since(1)] == [0.2, 1.2]
    on_disk = [json.loads(line) for line in path.read_text().splitlines()]
    assert on_disk[-1]["run_total_usd"] == 1.2
    old = tmp_path / "old.jsonl"
    rows = [{"seq": 1, "type": "cost", "usd": 0.3, "agent": "a1"}, {"seq": 2, "type": "cost", "usd": 0.5}]
    old.write_text("".join(json.dumps(r) + "\n" for r in rows))
    reread = EventLog(old, "r", loop)
    assert [e["run_total_usd"] for e in reread.since(1)] == [0.3, 0.8]
    assert "run_total_usd" not in old.read_text()  # the old file is not rewritten


# ---------------------------------------------------------------- B5: design variants


def _record(**changes: Any) -> dict[str, Any]:
    base = {
        "id": "28ff27e4d369",
        "label": "3-feature integer linear",
        "budget": {"channels": 2, "name": "2 electrodes"},
        "metrics": {"sensitivity": 0.9},
        "basis": "validation",
        "data": "synthetic",
    }
    return {**base, **changes}


def test_a_design_can_name_the_design_it_is_a_variant_of() -> None:
    assert validate_design(_record(variant_of="p2-lin-05"))["variant_of"] == "p2-lin-05"
    assert "variant_of" not in validate_design(_record())
    for bad, why in (
        ({"variant_of": "28ff27e4d369"}, "another design"),
        ({"variant_of": ""}, "non-empty"),
        ({"variant_of": 5}, "non-empty"),
        ({"variant_of": "x", "previous_id": "x"}, "previous_id renames"),
    ):
        with pytest.raises(ValueError, match=why):
            validate_design(_record(**bad))


def test_the_design_instructions_mention_variant_of() -> None:
    text = (Path(spec.__file__).parent / "spec.md").read_text()
    assert "`variant_of`" in text


# ---------------------------------------------------------------- B3: Chippy's seek and batches


def test_a_stage_seek_lands_inside_the_stage(runs: Path) -> None:
    tools = HelperTools(RunStore(runs))
    stages = [r for r in tools.get_stages(RUN_B)["stages"] if isinstance(r.get("started_seq"), int)]
    assert stages
    row = stages[-1]
    ui = UiActions(tools, parse_view({"run_id": RUN_B}))
    by_stage, _ = ui.handle("ui_set_playback", {"stage": row["stage"]})
    assert by_stage["seq"] == row["started_seq"] and by_stage["seconds"] >= row["started_playback_s"]
    rounded_down, _ = ui.handle("ui_set_playback", {"seconds": int(row["started_playback_s"])})
    assert rounded_down["seconds"] >= row["started_playback_s"]
    with pytest.raises(Exception, match="no start"):
        ui.handle("ui_set_playback", {"stage": "nonsense"})


def test_chippy_is_told_to_read_every_route_and_name_no_backend() -> None:
    text = instructions()
    assert "every subagent line" in text and "internal backends" in text


async def test_a_batch_focus_lists_every_subagent_route(tmp_path: Path) -> None:
    run = tmp_path / "runs" / "20261122-000000-aaaaaa"
    (run / "workspace").mkdir(parents=True)
    s = Script()
    s.add("run.started", prompt="p", agent="claude", runner="local")
    s.stage("propose", "started")
    for n in (1, 2, 3):
        s.add("subagent.started", id=f"a{n}", name=f"r{n}", stage="propose", strategy=f"route number {n}")
    for n in (1, 2, 3):
        s.add("subagent.finished", id=f"a{n}", stage="propose", state="done", result=f"result {n}")
    s.add("stage.merged", stage="propose", ids=["a1", "a2", "a3"], kept=["a1"], why="best")
    s.stage("propose", "done")
    s.add("run.finished", status="succeeded")
    for e in s.events:
        e["run_id"] = run.name
    (run / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in s.events))
    (run / "api.json").write_text(json.dumps({"id": run.name, "prompt": "p", "status": "succeeded"}))
    await summarise_folder(run, settings(), SummaryScript())
    tools = HelperTools(RunStore(tmp_path / "runs"))
    out = tools.get_summaries(run.name, focus="batch:propose:1")
    assert [r["route"] for r in out["subagents"]] == ["route number 1", "route number 2", "route number 3"]
    assert "name every one" in out["read_all"]
