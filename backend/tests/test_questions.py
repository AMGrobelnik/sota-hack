"""Follow-up questions: the route, the checks on a model reply, the stub, and the answers on the run."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from aiohttp.test_utils import TestClient, TestServer

from chipin_backend.api.config import ApiConfig, load_api_config
from chipin_backend.api.questions import (
    QUESTIONS,
    QUESTIONS_LEDGER,
    Ask,
    QuestionsConfig,
    canned_questions,
    parse_questions,
    past_runs_digest,
    system_prompt,
)
from chipin_backend.api.server import MANAGER, TOKEN_HEADER, create_app
from chipin_backend.config import BackendConfig
from chipin_backend.llm.summarise import Summary

TOKEN = "test-session-token"
AUTH = {TOKEN_HEADER: TOKEN}
BRIEF = "A wristband that spots seizures in children at night"
ANSWERS = {"device": "Wristband", "signal": "accelerometer", "place": "home"}
SPEC = {
    "brief": BRIEF,
    "device": "Wristband",
    "signal": "accelerometer",
    "detect": "seizures",
    "targets": [{"metric": "sensitivity", "op": "at_least", "value": 0.9}],
    "primary": "sensitivity",
    "data": {"mode": "simulate"},
}
GOOD = {
    "questions": [
        {
            "id": "Alert Delay",
            "question": "How soon must the alert follow the event?",
            "why": "It sets the window the chip looks at.",
            "kind": "choice",
            "options": ["Within 10 seconds", "Within a minute", "Within a minute"],
            "default": "Within a minute",
        },
        {
            "id": "night_light",
            "question": "Can the band show a light or must it stay dark at night?",
            "why": "It decides whether an output pin is left free.",
            "kind": "text",
            "default": "It must stay dark",
        },
    ]
}


class FakeModel:
    """The summaries' model, scripted: a reply, a delay, a failure; the prompts it was sent."""

    def __init__(
        self, text: str = "", *, cost: float = 0.0012, delay: float = 0.0, missing: str = ""
    ) -> None:
        self.text, self.cost, self.delay, self.missing = text, cost, delay, missing
        self.prompts: list[str] = []
        self.systems: list[str] = []

    def unavailable(self) -> str:
        return self.missing

    async def __call__(self, *, system: str, prompt: str, max_tokens: int) -> Summary:
        self.prompts.append(prompt)
        self.systems.append(system)
        if self.delay:
            await asyncio.sleep(self.delay)
        if not self.text:
            return Summary(error="tier1 x: HTTP 500", cost_usd=self.cost)
        return Summary(text=self.text, cost_usd=self.cost, model="small-model")


def _config(config: BackendConfig) -> BackendConfig:
    flex = config.compute.flex.model_copy(update={"require_macos": False})
    return config.model_copy(update={"compute": config.compute.model_copy(update={"flex": flex})})


def _api(**questions: Any) -> ApiConfig:
    return ApiConfig(
        keepalive_s=0.2,
        progress_poll_s=0.02,
        stub_step_s=0.01,
        run_timeout_s=60,
        questions=QuestionsConfig(**questions),
    )


async def _client(config: BackendConfig, agent: str, model: FakeModel | None = None, **q: Any) -> TestClient:
    app = create_app(_config(config), _api(**q), token=TOKEN, agent=agent)  # type: ignore[arg-type]
    if model is not None:
        app[QUESTIONS].asker = model
    return TestClient(TestServer(app))


@pytest.fixture
async def stub(config: BackendConfig) -> AsyncIterator[TestClient]:
    async with await _client(config, "stub") as c:
        yield c


async def _ask(client: TestClient, **body: Any) -> dict[str, Any]:
    resp = await client.post(
        "/api/questions", json={"brief": BRIEF, "answers": ANSWERS, **body}, headers=AUTH
    )
    assert resp.status == 200, await resp.text()
    return dict(await resp.json())


# ---- the route ----


async def test_questions_need_the_token(stub: TestClient) -> None:
    resp = await stub.post("/api/questions", json={"brief": BRIEF})
    assert resp.status == 401
    resp = await stub.post("/api/questions", json={"brief": BRIEF}, headers={TOKEN_HEADER: "wrong"})
    assert resp.status == 401


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"brief": ""},
        {"brief": BRIEF, "answers": []},
        {"brief": BRIEF, "run_size": "huge"},
        {"brief": "x" * 5000},
    ],
)
async def test_bad_bodies_are_400(stub: TestClient, body: dict[str, Any]) -> None:
    resp = await stub.post("/api/questions", json=body, headers=AUTH)
    assert resp.status == 400
    assert (await resp.json())["error"]


async def test_stub_gives_canned_questions_from_the_brief(stub: TestClient) -> None:
    first = await _ask(stub, run_size="lite")
    again = await _ask(stub)
    assert first["source"] == "stub" and first["reason"] is None and first["cost_usd"] == 0
    assert first["questions"] == again["questions"]
    assert [q["id"] for q in first["questions"]] == ["alert_delay", "motion", "worst_mistake"]
    by_id = {q["id"]: q for q in first["questions"]}
    assert by_id["alert_delay"]["default"] == "Within 10 seconds"  # seizures are urgent
    assert by_id["motion"]["default"] == "Some, from daily activity"  # a wristband is worn
    calm = canned_questions(Ask("A bedside monitor for sleep stages", {}), QuestionsConfig())
    assert {q["id"]: q["default"] for q in calm}["motion"] == "Little, mostly at rest"
    for q in first["questions"]:
        assert q["kind"] in ("choice", "text") and q["why"] and q["default"]
        if q["kind"] == "choice":
            assert q["default"] in q["options"]


async def test_no_key_gives_an_empty_list_and_why(config: BackendConfig) -> None:
    async with await _client(config, "claude") as client:  # the real model, with no key set
        body = await _ask(client)
    assert body["questions"] == [] and body["source"] == "none"
    assert "OPENROUTER_API_KEY" in body["reason"]


async def test_model_questions_are_checked_and_costed(config: BackendConfig, tmp_path: Path) -> None:
    model = FakeModel(json.dumps(GOOD))
    async with await _client(config, "claude", model) as client:
        body = await _ask(client, run_size="pro")
    assert body["source"] == "model" and body["reason"] is None
    assert body["cost_usd"] == pytest.approx(0.0012)
    first = body["questions"][0]
    assert first["id"] == "alert_delay" and first["options"] == ["Within 10 seconds", "Within a minute"]
    assert [q["kind"] for q in body["questions"]] == ["choice", "text"]
    sent = json.loads(model.prompts[0])
    assert sent["brief"] == BRIEF and sent["answers_so_far"] == ANSWERS and sent["run_size"] == "pro"
    assert "Never" in model.systems[0] and "battery life" in model.systems[0]
    ledger = [json.loads(x) for x in (tmp_path / "runs" / QUESTIONS_LEDGER).read_text().splitlines()]
    assert ledger[-1]["id"] == body["id"] and ledger[-1]["usd"] == pytest.approx(0.0012)
    assert ledger[-1]["questions"] == 2 and "brief" not in ledger[-1]


async def test_a_slow_model_times_out_to_an_empty_list(config: BackendConfig) -> None:
    model = FakeModel(json.dumps(GOOD), delay=5.0)
    async with await _client(config, "claude", model, timeout_s=0.2) as client:
        started = asyncio.get_running_loop().time()
        body = await _ask(client)
        took = asyncio.get_running_loop().time() - started
    assert body["questions"] == [] and body["reason"] == "the model did not answer in time"
    assert took < 2.0


@pytest.mark.parametrize(
    ("text", "reason"),
    [("", "the model did not answer"), ("no json here", "the model gave no usable questions")],
)
async def test_a_failing_model_gives_an_empty_list(config: BackendConfig, text: str, reason: str) -> None:
    async with await _client(config, "claude", FakeModel(text)) as client:
        body = await _ask(client)
    assert body["questions"] == [] and body["reason"] == reason and body["source"] == "none"


async def test_the_daily_cap_stops_calls(config: BackendConfig) -> None:
    model = FakeModel(json.dumps(GOOD), cost=0.02)
    async with await _client(config, "claude", model, daily_usd=0.03) as client:
        assert (await _ask(client))["questions"]
        assert (await _ask(client))["questions"]
        third = await _ask(client)
    assert third["questions"] == [] and "spending limit" in third["reason"]
    assert len(model.prompts) == 2


async def test_the_model_reads_a_scrubbed_digest_of_past_runs(config: BackendConfig) -> None:
    model = FakeModel(json.dumps(GOOD))
    home = str(Path.home())
    async with await _client(config, "claude", model) as client:
        manager = client.server.app[MANAGER]
        from chipin_backend.api.events import EventLog
        from chipin_backend.api.manager import ApiRun
        from chipin_backend.runs import RunDir

        loop = asyncio.get_running_loop()
        for n, (prompt, chip) in enumerate(
            [(f"Old ECG patch kept in {home}/data", "d7"), ("Sleep band", None)]
        ):
            folder = config.resolved_runs_dir() / f"run{n}"
            folder.mkdir(parents=True)
            log = EventLog(folder / "events.jsonl", folder.name, loop)
            log.append("run.started", prompt=prompt)
            log.append("message", role="agent", text="private agent words")
            if chip:
                log.append("chosen", chip=chip)
            record = {"id": folder.name, "prompt": prompt, "started_at": f"2026-01-0{n + 1}T00:00:00+00:00"}
            manager.runs[folder.name] = ApiRun(RunDir(folder), record, log)
        await _ask(client)
    sent = json.loads(model.prompts[0])
    assert sent["past_runs"][0] == "Sleep band"  # newest first
    assert sent["past_runs"][1].endswith("(chose chip d7)")
    assert home not in model.prompts[0] and "private agent words" not in model.prompts[0]


def test_the_digest_is_capped() -> None:
    runs = [({"prompt": f"Run number {n}", "started_at": f"2026-01-{n + 10}"}, []) for n in range(20)]
    lines = past_runs_digest(runs, QuestionsConfig(max_past_runs=5))
    assert len(lines) == 5 and lines[0] == "Run number 19"
    assert len(past_runs_digest(runs, QuestionsConfig(digest_max_chars=30))) == 2


# ---- checking a reply ----


def test_malformed_and_repeated_questions_are_dropped() -> None:
    long = "Why " + "really " * 60 + "?"
    reply = (
        "Sure! "
        + json.dumps(
            {
                "questions": [
                    {
                        "id": "a",
                        "question": "How long must the battery last?",
                        "why": "x",
                        "kind": "text",
                        "default": "1 day",
                    },
                    {
                        "id": "b",
                        "question": "Which data set should it use?",
                        "why": "x",
                        "kind": "text",
                        "default": "any",
                    },
                    {
                        "id": "c",
                        "question": "Pick one",
                        "why": "x",
                        "kind": "choice",
                        "options": ["only"],
                        "default": "only",
                    },
                    {"id": "d", "question": "Q?", "why": "x", "kind": "slider", "default": "1"},
                    {"id": "", "question": "Q?", "why": "x", "kind": "text", "default": "1"},
                    {"id": "e", "question": "Q?", "why": "", "kind": "text", "default": "1"},
                    {"id": "f", "question": "Q?", "why": "x", "kind": "text", "default": ""},
                    "not an object",
                    {
                        "id": "g",
                        "question": long,
                        "why": "y " * 200,
                        "kind": "choice",
                        "options": ["A", "B"],
                        "default": "C",
                    },
                    {"id": "g", "question": "Duplicate id?", "why": "x", "kind": "text", "default": "1"},
                    {
                        "id": "h",
                        "question": "Is a vibration alert allowed?",
                        "why": "x",
                        "kind": "text",
                        "default": "Yes",
                    },
                    {"id": "i", "question": "Fourth good one?", "why": "x", "kind": "text", "default": "1"},
                    {"id": "j", "question": "Fifth good one?", "why": "x", "kind": "text", "default": "1"},
                ]
            }
        )
        + " Hope that helps."
    )
    config = QuestionsConfig()
    out = parse_questions(reply, config)
    assert [q["id"] for q in out] == ["g", "h", "i"]
    g = out[0]
    assert len(g["question"]) <= config.question_max_chars and len(g["why"]) <= config.why_max_chars
    assert g["default"] == "A"  # a default not among the options falls back to the first
    assert parse_questions("[]", config) == [] and parse_questions("", config) == []
    assert parse_questions('{"questions": "nope"}', config) == []


def test_questions_off_the_chip_design_are_dropped() -> None:
    def item(qid: str, question: str) -> dict[str, Any]:
        return {"id": qid, "question": question, "why": "x", "kind": "text", "default": "n/a"}

    reply = json.dumps(
        {
            "questions": [
                item("reg", "Which regulatory class should the device target?"),
                item("radio", "Which wireless interface should it use?"),
                item("size", "What is the maximum module size?"),
                item("cert", "Does it need certification for home use?"),
                item("price", "What unit price is acceptable?"),
                item("alert", "How fast must it alert after onset?"),
                item("miss", "Which matters more, a missed event or a false alarm?"),
                item("drop", "What should the chip do when a sensor drops out?"),
            ]
        }
    )
    out = parse_questions(reply, QuestionsConfig())
    assert [q["id"] for q in out] == ["alert", "miss", "drop"]


def test_option_keys_become_words_a_person_reads() -> None:
    """The live run showed missed_event, false_alarm and both_equal as buttons and on the spec card."""
    question = {
        "id": "error_priority",
        "question": "Which error is more critical to avoid?",
        "why": "It sets the threshold.",
        "kind": "choice",
        "options": ["missed_event", "false_alarm", "both_equal", "Low-noise mode"],
        "default": "missed_event",
    }
    out = parse_questions(json.dumps({"questions": [question]}), QuestionsConfig())
    assert out[0]["options"] == ["Missed event", "False alarm", "Both equal", "Low-noise mode"]
    assert out[0]["default"] == "Missed event"
    assert "never code keys" in system_prompt(QuestionsConfig())


def test_the_prompt_names_what_to_ask_and_what_to_skip() -> None:
    from chipin_backend.api.questions import system_prompt

    text = system_prompt(QuestionsConfig())
    for needle in ("how fast the chip must alert", "sampling rate", "drops out", "regulatory class"):
        assert needle in text


# ---- the answers on the run ----


async def _run(client: TestClient, **extra: Any) -> dict[str, Any]:
    body = {"prompt": BRIEF, "preset": "lite", **extra}
    resp = await client.post("/api/runs", json=body, headers=AUTH)
    assert resp.status == 201, await resp.text()
    run_id = (await resp.json())["id"]
    for _ in range(400):
        detail = await (await client.get(f"/api/runs/{run_id}", headers=AUTH)).json()
        if detail["status"] != "running":
            return dict(detail)
        await asyncio.sleep(0.05)
    raise AssertionError("the run did not finish")


FOLLOW = {
    "answers": [
        {
            "id": "alert_delay",
            "question": "How soon must the alert follow the event?",
            "answer": "Within 10 seconds",
        },
        {"id": "motion", "question": "How much movement will the recordings carry?", "answer": "A lot"},
    ]
}


async def test_answers_reach_the_spec_the_record_and_the_cost(
    stub: TestClient, config: BackendConfig
) -> None:
    asked = await _ask(stub)
    manager = stub.server.app[MANAGER]
    manager.question_ledger.record(asked["id"], usd=0.004, source="model", count=2)  # as a model call would
    detail = await _run(stub, spec=SPEC, follow_up={"id": asked["id"], **FOLLOW})
    folder = config.resolved_runs_dir() / detail["id"]
    spec = json.loads((folder / "workspace" / "spec.json").read_text())
    assert [a["answer"] for a in spec["follow_up"]] == ["Within 10 seconds", "A lot"]
    record = json.loads((folder / "api.json").read_text())
    assert record["follow_up"]["id"] == asked["id"] and record["follow_up"]["answers"][1]["id"] == "motion"
    assert detail["follow_up"]["answers"][0]["answer"] == "Within 10 seconds"
    assert detail["cost"]["questions_usd"] == pytest.approx(0.004)
    run_json = json.loads((folder / "run.json").read_text())
    assert run_json["questions_usd"] == pytest.approx(0.004)
    assert run_json["llm_cost_usd"] >= 0.004
    events = [json.loads(x) for x in (folder / "events.jsonl").read_text().splitlines()]
    started = next(e for e in events if e["type"] == "run.started")
    assert started["spec"]["follow_up"][0]["question"].startswith("How soon")
    costs = [e for e in events if e["type"] == "cost"]
    assert costs[-1]["run_total_usd"] >= 0.004
    prompt = json.loads((folder / "run.json").read_text())["agent"]["prompts"][0]
    assert "Follow-up answers" in prompt and "How much movement will the recordings carry? A lot" in prompt
    # the same id counts once: a second run with it adds no questions spend
    again = await _run(stub, spec=SPEC, follow_up={"id": asked["id"], **FOLLOW})
    assert "questions_usd" not in (again.get("cost") or {})


async def test_answers_without_a_spec_go_into_the_brief(stub: TestClient, config: BackendConfig) -> None:
    detail = await _run(stub, follow_up=FOLLOW["answers"])
    brief = (config.resolved_runs_dir() / detail["id"] / "workspace" / "brief.md").read_text()
    assert (
        "## Follow-up answers" in brief
        and "- How soon must the alert follow the event? Within 10 seconds" in brief
    )


@pytest.mark.parametrize(
    "follow_up",
    [
        "yes",
        {"answers": "yes"},
        {"answers": [{"question": "Q?"}]},
        {"answers": [{"answer": "A"}]},
        {"id": "bad id!", "answers": []},
        {"answers": [{"question": "Q?", "answer": "A"}] * 4},
    ],
)
async def test_bad_follow_up_is_400(stub: TestClient, follow_up: Any) -> None:
    resp = await stub.post("/api/runs", json={"prompt": BRIEF, "follow_up": follow_up}, headers=AUTH)
    assert resp.status == 400
    assert "follow_up" in (await resp.json())["error"]


def test_committed_api_yaml_has_the_questions_settings() -> None:
    q = load_api_config().questions
    assert q.enabled and q.max_questions == 3 and q.timeout_s < 12
