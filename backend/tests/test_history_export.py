"""Playback support: the run list for a picker, a run's whole event history, and the static export."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from aiohttp.test_utils import TestClient, TestServer

from chipin_backend.api.config import ApiConfig
from chipin_backend.api.history import history_page, run_facts, title_of
from chipin_backend.api.server import TOKEN_HEADER, create_app
from chipin_backend.cli import main
from chipin_backend.config import BackendConfig
from chipin_backend.export import ExportError, Scrubber, build_export, export_run

TOKEN = "test-session-token"
AUTH = {TOKEN_HEADER: TOKEN}
HOME = "/Users/someone"
KEY = "sk-or-v1-" + "a1b2c3d4" * 6
EMAIL = "someone.private@example.org"


def _config(config: BackendConfig) -> BackendConfig:
    flex = config.compute.flex.model_copy(update={"require_macos": False})
    return config.model_copy(update={"compute": config.compute.model_copy(update={"flex": flex})})


@pytest.fixture
async def client(config: BackendConfig) -> AsyncIterator[TestClient]:
    api = ApiConfig(keepalive_s=0.2, progress_poll_s=0.02, stub_step_s=0.01, run_timeout_s=60)
    app = create_app(_config(config), api, token=TOKEN, agent="stub")
    async with TestClient(TestServer(app)) as c:
        yield c


async def _finished_run(client: TestClient, prompt: str) -> tuple[str, list[dict[str, Any]]]:
    resp = await client.post("/api/runs", json={"prompt": prompt, "preset": "lite"}, headers=AUTH)
    run_id = str((await resp.json())["id"])
    stream = await client.get(f"/api/runs/{run_id}/events", params={"token": TOKEN})
    events = [
        json.loads(line[6:]) for line in (await stream.text()).splitlines() if line.startswith("data: ")
    ]
    assert events[-1]["type"] == "run.finished"
    return run_id, events


async def test_history_lists_runs_with_picker_facts(client: TestClient) -> None:
    first, _ = await _finished_run(client, "first brief\nwith a second line")
    second, events = await _finished_run(client, "second brief")
    assert (await client.get("/api/history")).status == 401
    runs = (await (await client.get("/api/history", headers=AUTH)).json())["runs"]
    assert [r["id"] for r in runs] == [second, first]
    top = runs[0]
    assert top["title"] == "second brief" and runs[1]["title"] == "first brief"
    assert top["state"] == "succeeded" and top["preset"] == "lite" and top["agent"] == "stub"
    assert top["counts"]["events"] == len(events) and top["last_seq"] == events[-1]["seq"]
    assert top["counts"]["stages_done"] >= 1 and top["duration_s"] >= 0
    assert {"started_at", "finished_at", "counts"} <= set(top)
    # the live listing keeps its shape
    plain = (await (await client.get("/api/runs", headers=AUTH)).json())["runs"]
    assert set(plain[0]) == {"id", "prompt", "status", "started_at", "finished_at"}


async def test_history_returns_every_event_and_pages(client: TestClient) -> None:
    run_id, events = await _finished_run(client, "a brief")
    whole = await (await client.get(f"/api/runs/{run_id}/history", headers=AUTH)).json()
    assert whole["events"] == events and whole["next"] is None and whole["finished"] is True
    assert all("ts" in e for e in whole["events"]) and whole["state"] == "succeeded"
    got: list[dict[str, Any]] = []
    start: int | None = 1
    while start is not None:
        page = await (
            await client.get(
                f"/api/runs/{run_id}/history", params={"from": str(start), "limit": "7"}, headers=AUTH
            )
        ).json()
        assert len(page["events"]) <= 7
        got += page["events"]
        start = page["next"]
    assert got == events
    for bad in ({"limit": "0"}, {"limit": "x"}, {"from": "-1"}, {"limit": "999999"}):
        assert (await client.get(f"/api/runs/{run_id}/history", params=bad, headers=AUTH)).status == 400
    assert (await client.get("/api/runs/nope/history", headers=AUTH)).status == 404


def _ev(seq: int, ts: str, type_: str, **fields: Any) -> dict[str, Any]:
    return {"seq": seq, "ts": f"2026-11-22T02:{ts}+00:00", "run_id": "r1", "type": type_, **fields}


def _events() -> list[dict[str, Any]]:
    return [
        _ev(1, "00:00", "run.started", prompt="A seizure flag", agent="claude"),
        _ev(2, "00:05", "stage", stage="spec", name="spec", state="done"),
        _ev(3, "00:10", "design", design={"id": "a", "gates": 10}),
        _ev(4, "00:20", "design", design={"id": "b1", "prev_id": "a", "gates": 9}),
        _ev(5, "00:30", "design", design={"id": "c", "gates": 30}),
        _ev(6, "00:40", "chosen", chip="c"),
        _ev(7, "00:50", "chosen", chip="b1"),
        _ev(8, "01:00", "tool", call_id="t1", name="Bash", state="started", detail=f"cat {HOME}/x"),
        _ev(9, "01:05", "tool", call_id="t1", name="Bash", state="done"),
        _ev(10, "01:40", "run.finished", status="succeeded"),
    ]


def test_run_facts_counts_and_chosen() -> None:
    facts = run_facts({"id": "r1", "status": "succeeded", "preset": "pro"}, _events())
    assert facts["chosen"] == "b1" and facts["duration_s"] == 100.0 and facts["title"] == "A seizure flag"
    assert (
        facts["counts"]["designs"] == 2
        and facts["counts"]["tools"] == 1
        and facts["counts"]["stages_done"] == 1
    )
    assert title_of("x " * 80).endswith("…") and len(title_of("x " * 80)) <= 90
    page = history_page(_events(), start=4, limit=3)
    assert [e["seq"] for e in page["events"]] == [4, 5, 6] and page["next"] == 7 and page["finished"] is True


def test_scrubber_removes_private_details() -> None:
    s = Scrubber(home=HOME, host_names=("lab-mac-7",), user="someone")
    text = s.text(
        f"open {HOME}/proj and /home/other/x; key {KEY} token=abcdef123456 "
        f"mail {EMAIL} on lab-mac-7 by someone"
    )
    assert HOME not in text and "/home/other" not in text and KEY not in text and EMAIL not in text
    assert "abcdef123456" not in text and "lab-mac-7" not in text and "someone" not in text
    assert text.startswith("open ~/proj and ~/x")
    assert s.counts == {"home_paths": 2, "keys": 2, "emails": 1, "host": 1, "user": 1}


def _run_folder(root: Path) -> Path:
    folder = root / "20261122-020000-abcdef"
    (folder / "workspace").mkdir(parents=True)
    events = [
        *_events(),
        _ev(11, "01:41", "artifact", name="report.md", kind="report", path="workspace/report.md"),
        _ev(12, "01:42", "artifact", name="big.json", kind="file", path="workspace/big.json"),
        _ev(13, "01:43", "artifact", name="outside", kind="file", path="../secret.txt"),
        _ev(
            14,
            "01:44",
            "message",
            role="agent",
            text=f"Mail {EMAIL} with {KEY} from {HOME}/runs " + "x" * 2000,
        ),
    ]
    events[-1], events[9] = events[9], events[-1]  # run.finished stays last
    for i, ev in enumerate(events, 1):
        ev["seq"] = i
    (folder / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    (folder / "api.json").write_text(
        json.dumps(
            {
                "id": folder.name,
                "prompt": "A seizure flag",
                "status": "succeeded",
                "preset": "lite",
                "started_at": "2026-11-22T02:00:00+00:00",
                "summary": f"done in {HOME}/w",
            }
        ),
        encoding="utf-8",
    )
    (folder / "workspace" / "report.md").write_text(f"# Report\nContact {EMAIL}\n", encoding="utf-8")
    (folder / "workspace" / "big.json").write_text(json.dumps({"v": "y" * 50_000}), encoding="utf-8")
    (root / "secret.txt").write_text("not exported", encoding="utf-8")
    return folder


def test_export_is_scrubbed_bounded_and_indexed(tmp_path: Path) -> None:
    folder = _run_folder(tmp_path / "runs")
    out_dir = tmp_path / "site" / "runs"
    report = export_run(folder, out_dir / "r1.json", index=out_dir / "index.json")
    text = (out_dir / "r1.json").read_text(encoding="utf-8")
    doc = json.loads(text)
    assert doc["format"] == "chipin-recorded-run" and doc["run"]["chosen"] == "b1"
    assert len(doc["events"]) == 14 and doc["events"][-1]["type"] == "run.finished"
    assert "/Users/" not in text and KEY not in text and EMAIL not in text and "not exported" not in text
    assert [f["path"] for f in doc["files"]] == ["workspace/report.md", "workspace/big.json"]
    assert doc["redactions"]["emails"] >= 2 and doc["redactions"]["keys"] >= 1 and report["files"] == 2
    index = json.loads((out_dir / "index.json").read_text(encoding="utf-8"))
    assert index["runs"][0]["file"] == "r1.json" and index["runs"][0]["source"] == "recorded"
    export_run(folder, out_dir / "r1.json", index=out_dir / "index.json")
    assert len(json.loads((out_dir / "index.json").read_text(encoding="utf-8"))["runs"]) == 1

    small = build_export(folder, max_bytes=20_000)
    assert len(json.dumps(small)) <= 20_000 and [f["path"] for f in small["files"]] == ["workspace/report.md"]
    assert "detail" not in next(e for e in small["events"] if e["type"] == "tool")
    with pytest.raises(ExportError):
        build_export(folder, max_bytes=500)


def test_export_command(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    folder = _run_folder(tmp_path / "runs")
    out = tmp_path / "out" / "run.json"
    assert main(["export", str(folder), "--out", str(out)]) == 0
    assert json.loads(capsys.readouterr().out.strip().splitlines()[-1])["events"] == 14
    assert out.is_file()
    assert main(["export", str(tmp_path / "missing"), "--out", str(out)]) == 2
