"""Run evidence on small synthetic run folders: number tracing, weight bytes, stage timings, wiring."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml
from aiohttp.test_utils import TestClient, TestServer

from chipin_backend import cli
from chipin_backend import evidence as evidence_mod
from chipin_backend.api import server as server_mod
from chipin_backend.api.config import ApiConfig
from chipin_backend.api.server import TOKEN_HEADER, create_app
from chipin_backend.config import BackendConfig
from chipin_backend.evidence import (
    EVIDENCE_JSON,
    EVIDENCE_MD,
    build_evidence,
    emit_evidence,
    evidence_summary,
    render_markdown,
    stage_timings,
    trace_numbers,
    weight_bytes,
)

T0 = datetime(2026, 1, 1, tzinfo=UTC)
TOKEN = "evidence-test-token"


def _event(seq: int, at: float, type_: str, **fields: Any) -> dict[str, Any]:
    ts = (T0 + timedelta(seconds=at)).isoformat()
    return {"seq": seq, "ts": ts, "run_id": "r", "type": type_, **fields}


def _metric(seq: int, at: float, key: str, value: float, unit: str | None = None) -> dict[str, Any]:
    return _event(seq, at, "metric", key=key, value=value, **({"unit": unit} if unit else {}))


def _run(
    root: Path,
    events: list[dict[str, Any]],
    report: str | None = None,
    files: dict[str, Any] | None = None,
) -> Path:
    """A run folder: ``events.jsonl``, ``workspace/report.md`` and ``files`` (dicts become JSON)."""
    run = root / "run"
    (run / "workspace").mkdir(parents=True)
    (run / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    if report is not None:
        (run / "workspace" / "report.md").write_text(report, encoding="utf-8")
    for rel, content in (files or {}).items():
        path = run / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        text = content if isinstance(content, str) else json.dumps(content)
        path.write_text(text, encoding="utf-8")
    return run


def _by_text(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {entry["text"]: entry for entry in result["numbers"]}


# ---- A. number tracing ----


def test_numbers_traced_through_formatting(tmp_path: Path) -> None:
    events = [
        _event(1, 0, "run.started", prompt="A seizure alarm"),
        _metric(2, 1, "gates", 2367, "gates"),
        _metric(3, 2, "area_um2", 20042.9728, "um2"),
        _metric(4, 3, "power_uw_at_rate", 0.04986, "uW"),
        _metric(5, 4, "pass_fraction", 0.854),
    ]
    lab_answer = {"status": "ok", "design_id": "d1", "metrics": {"energy_per_decision_pj": 456.106}}
    report = (
        "The chip has 2,367 gates (about 2.4k gates), 20,043 µm² of area, draws 49.9 nW,\n"
        "spends 456 pJ per decision and passes 85.4% of the checks.\n"
    )
    run = _run(tmp_path, events, report, {"workspace/lab/d1.tp.json": lab_answer})
    found = _by_text(trace_numbers(run))

    assert found["2,367 gates"]["source"].startswith("metric gates = 2367")
    assert found["2.4k"]["class"] == "traced"
    assert found["20,043 µm²"]["source"].startswith("metric area_um2")
    assert found["49.9 nW"]["source"].startswith("metric power_uw_at_rate")
    assert found["456 pJ"]["source"] == "workspace/lab/d1.tp.json: metrics.energy_per_decision_pj = 456.106"
    assert found["85.4%"]["source"].startswith("metric pass_fraction")
    assert all(entry["class"] == "traced" for entry in found.values())


def test_a_planted_number_is_untraced_not_wrong(tmp_path: Path) -> None:
    run = _run(tmp_path, [_metric(1, 0, "gates", 2367, "gates")], "It has 2367 gates and lasts 731 days.\n")
    result = trace_numbers(run)
    found = _by_text(result)
    assert found["731"]["status"] == "untraced" and "source" not in found["731"]
    assert (result["traced"], result["untraced"]) == (1, 1)
    md = build_evidence(run)["numbers"]
    assert md["untraced"] == 1
    assert "not wrong" in (run / EVIDENCE_MD).read_text()


def test_non_claims_are_excluded(tmp_path: Path) -> None:
    events = [
        _event(1, 0, "run.started", prompt="It samples at 256 Hz from two leads."),
        _metric(2, 1, "x", 256),
    ]
    report = "\n".join(
        [
            "## 2. Results",
            "1. Measured on 2026-11-22 at 00:15 and again on 22 Nov 2026.",
            "Built with yosys 0.71+77 and lab v1.2.3, files run7.synth.json and chip_67301286c5e3.gds.",
            "The input is sampled at 256 Hz.",
            "```",
            "chiplab synthesize --json 4096",
            "```",
        ]
    )
    result = trace_numbers(_run(tmp_path, events, report))
    assert {entry["class"] for entry in result["numbers"]} == {"excluded"}
    reasons = {entry["text"]: entry["reason"] for entry in result["numbers"]}
    assert reasons["2"] == "list numbering"
    assert reasons["1"] == "list numbering"
    assert {reasons[k] for k in ("2026", "22")} == {"date"}
    assert reasons["00"] == "time"
    assert reasons["0.71+77"] == "version" and reasons["v1.2.3"]
    assert reasons["run7.synth.json"] == "identifier or file name"
    assert reasons["chip_67301286c5e3.gds"] == "identifier or file name"
    assert reasons["256 Hz"] == "quoted from the prompt"
    assert reasons["4096"] == "code block"
    assert result["traced"] == result["untraced"] == result["value_found_meaning_not_confirmed"] == 0


def test_small_integers_need_a_matching_key(tmp_path: Path) -> None:
    events = [_metric(1, 0, "tt_tiles", 2, "tiles"), _metric(2, 0, "mismatches", 0, "vectors")]
    report = "It fits in 2 tiles with 0 mismatches.\nWe tried 2 ideas.\n"
    result = trace_numbers(_run(tmp_path, events, report))
    statuses = [(e["line"], e["text"], e["class"]) for e in result["numbers"]]
    assert statuses == [(1, "2 tiles", "traced"), (1, "0", "traced"), (2, "2", "untraced")]
    assert "small integer" in result["numbers"][2]["reason"]
    assert result["untraced"] == 1 and result["value_found_meaning_not_confirmed"] == 0


def _lab(design: str, **fields: Any) -> dict[str, Any]:
    return {"status": "ok", "design_id": design, **fields}


def test_a_percent_matches_only_a_percentage_or_ratio(tmp_path: Path) -> None:
    report = "Sensitivity reached 93% on held-out subjects.\nThe optimiser cut the cost by 40% overall.\n"
    events = [_metric(1, 0, "alkaid_cost", 40)]
    files = {"workspace/lab/d1.tp.json": _lab("d1", seconds=93.4, cost=40)}
    found = _by_text(trace_numbers(_run(tmp_path / "a", events, report, files)))
    assert (found["93%"]["class"], found["40%"]["class"]) == ("untraced", "untraced")

    ratios = [_metric(1, 0, "sensitivity", 0.93), _metric(2, 0, "pass_fraction", 0.4)]
    found = _by_text(trace_numbers(_run(tmp_path / "b", ratios, report)))
    assert found["93%"]["class"] == "traced" and found["93%"]["source"].startswith("metric sensitivity")
    assert found["40%"]["class"] == "value_found_meaning_not_confirmed"  # a ratio, but of what?


def test_structural_fields_are_sources_only_when_named(tmp_path: Path) -> None:
    files = {"workspace/lab/A.compile.json": _lab("A", lines=41, seed=17, seconds=12.5)}
    report = (
        "Parameter counts (81, 41, 193), a measured line-length front-end.\n"
        "The netlist is 41 lines long, built from seed 17.\n"
    )
    numbers = trace_numbers(_run(tmp_path, [], report, files))["numbers"]
    by_line = {(e["line"], e["text"]): e for e in numbers}
    assert by_line[(1, "41")]["class"] == "untraced"
    assert by_line[(2, "41")]["class"] == "traced" and by_line[(2, "41")]["source"].endswith("lines = 41")
    assert by_line[(2, "17")]["class"] == "traced" and by_line[(2, "17")]["source"].endswith("seed = 17")


def test_a_counted_noun_must_agree_with_the_source(tmp_path: Path) -> None:
    events = [_metric(1, 0, "gates", 1356, "gates")]
    report = "We screened 1,356 patients.\nDesign C has 1,356 gates.\n"
    found = _by_text(trace_numbers(_run(tmp_path, events, report)))
    patients = found["1,356 patients"]
    assert patients["class"] == "untraced" and "source" not in patients
    assert "patients" in patients["reason"] and "metric gates = 1356" in patients["reason"]
    assert found["1,356 gates"]["class"] == "traced"


def test_parameter_counts_trace_to_model_files(tmp_path: Path) -> None:
    files = {
        "workspace/designs/A.ir.json": {
            "name": "A",
            "nodes": [{"id": "l0", "W": [[1, 2, 3, 4]] * 3, "b": [1, 2, 3]}],
            "meta": {"params": 15},
        },
        "workspace/designs/B.ir.json": {
            "name": "B",
            "nodes": [{"id": "l0", "W": [[1, -1, 0, 1, 0]] * 4, "b": [0, 0, 0, 0]}],
            "meta": {"params": 11},
        },
        "workspace/lab/A.compile.json": _lab("A", lines=15),
    }
    report = "Parameter counts are 15 and 11.\nB stores 24 parameters.\n"
    found = _by_text(trace_numbers(_run(tmp_path, [], report, files)))
    assert found["15"]["class"] == "traced"
    assert found["15"]["source"].startswith("workspace/designs/A.ir.json (model A): 15 stored weight values")
    assert "meta.params declares the same" in found["15"]["source"]
    assert found["11"]["class"] == "value_found_meaning_not_confirmed"
    assert "declares 11, but the arrays store 24" in found["11"]["source"]
    assert found["24"]["class"] == "traced" and found["24"]["source"].startswith(
        "workspace/designs/B.ir.json"
    )


def test_the_classes_are_separate_everywhere(tmp_path: Path) -> None:
    events = [_metric(1, 0, "gates", 2367, "gates"), _metric(2, 0, "depth", 57)]
    report = "It has 2367 gates.\nWe tried 57 things.\nIt lasts 731 days.\n"
    run = _run(tmp_path, events, report)
    evidence = build_evidence(run)
    numbers = evidence["numbers"]
    counts = {k: numbers[k] for k in ("traced", "value_found_meaning_not_confirmed", "untraced", "excluded")}
    assert counts == {"traced": 1, "value_found_meaning_not_confirmed": 1, "untraced": 1, "excluded": 0}
    assert numbers["classes"]["traced"] == "traced (value and meaning agree)"
    assert evidence_summary(evidence)["numbers"] == counts
    md = (run / EVIDENCE_MD).read_text()
    summary = "Traced (value and meaning agree): 1; value found, meaning not confirmed: 1; untraced: 1"
    assert f"{summary}; excluded: 0." in md
    assert "### Value found, meaning not confirmed: 1" in md and "never added together" in md


def _sweep_fixture(root: Path) -> tuple[Path, str]:
    """A run whose sources hold every integer 11..199 under many unrelated keys."""
    rows = [
        {"gates": n, "lines": n, "seconds": n + 0.4, "cost": n, "seed": n, "count": n, "total": n,
         "value": n, "depth": n, "area_um2": n, "power_uw": n, "pass_fraction": n / 100}
        for n in range(11, 200)
    ]  # fmt: skip
    events = [_metric(i + 1, 0, "vectors_checked", n) for i, n in enumerate(range(11, 200))]
    files = {
        "workspace/lab/sweep.tp.json": _lab("d1", rows=rows),
        "workspace/designs/M.ir.json": {"nodes": [{"id": "l0", "W": [[1] * 9] * 9}], "meta": {"params": 81}},
    }
    base = "# Report\n\nThe chip has 2,367 gates and passed 100% of checks.\n"
    return _run(root, [*events, _metric(999, 0, "gates", 2367, "gates")], base, files), base


def test_no_bare_number_with_a_neutral_noun_is_traced(tmp_path: Path) -> None:
    run, base = _sweep_fixture(tmp_path)
    report, first_new = run / "workspace" / "report.md", len(base.splitlines()) + 1
    traced = []
    for n in range(11, 200):
        report.write_text(f"{base}\nWe counted {n} of the widgets.\n", encoding="utf-8")
        planted = [e for e in trace_numbers(run)["numbers"] if e["line"] >= first_new]
        assert [e["text"] for e in planted] == [str(n)]
        traced += [n for e in planted if e["class"] == "traced"]
    assert traced == []


# ---- B. weight bytes ----


def _chip(name: str, ir: dict[str, Any], cells: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        f"workspace/chips/{name}/ir.json": ir,
        f"workspace/chips/{name}/net.json": {"modules": {"top": {"cells": cells}}},
    }


def test_weight_bytes_for_a_float_model(tmp_path: Path) -> None:
    ir = {"nodes": [{"id": "l0", "op": "matvec", "W": [[0.5, -0.25], [1.5, 2.0]], "b": [0.1, 0.2]}]}
    run = _run(tmp_path, [], None, _chip("d1", ir, {"a": {"type": "$_AND_"}, "x": {"type": "$_XOR_"}}))
    result = weight_bytes(run)
    software = result["software"]
    assert (result["chip"], software["parameters"], software["bytes_per_decision"]) == ("d1", 6, 24)
    assert {t["bits"] for t in software["tensors"]} == {32}
    assert "nodes[l0].W" in software["sentence"] and "24 bytes" in software["sentence"]


def test_weight_bytes_for_a_one_bit_model(tmp_path: Path) -> None:
    ir = {
        "nodes": [{"id": "l0", "op": "matvec", "W": [[1, -1, 1, -1]] * 4, "b": [3, -2]}],
        "meta": {"params": 18},
    }
    run = _run(tmp_path, [], None, _chip("bnn", ir, {"a": {"type": "$_XNOR_"}}))
    software = weight_bytes(run)["software"]
    bits = {t["field"]: (t["count"], t["bits"], t["min_bits"]) for t in software["tensors"]}
    assert bits == {"nodes[l0].W": (16, 8, 1), "nodes[l0].b": (2, 8, 3)}
    assert software["bytes_per_decision"] == 18  # one rule: int8 per value, the smallest machine type
    assert software["bytes_at_minimal_widths"] == 3  # 16 x 1 bit + 2 x 3 bits = 22 bits
    assert software["parameters"] == software["declared_params"] == 18


def test_a_netlist_without_memory_fetches_no_weight_bytes(tmp_path: Path) -> None:
    ir = {"nodes": [{"id": "l0", "W": [[2, -3]], "b": [1]}]}
    run = _run(tmp_path, [], None, _chip("d1", ir, {"a": {"type": "$_AND_"}, "n": {"type": "$_NOT_"}}))
    chip = weight_bytes(run)["chip_netlist"]
    assert (chip["cells"], chip["memory_cells"], chip["flip_flops"]) == (2, 0, 0)
    assert chip["weight_bytes_fetched_per_decision"] == 0
    assert "constants wired into the logic" in chip["sentence"]


def test_a_netlist_with_a_memory_reports_its_bits(tmp_path: Path) -> None:
    ir = {"nodes": [{"id": "l0", "W": [[2, -3]], "b": [1]}]}
    cells = {
        "a": {"type": "$_AND_"},
        "rom": {"type": "$mem_v2", "parameters": {"WIDTH": "00000000000000000000000000001000", "SIZE": 16}},
        "q": {"type": "$_DFF_P_"},
    }
    chip = weight_bytes(_run(tmp_path, [], None, _chip("d1", ir, cells)))["chip_netlist"]
    assert (chip["memory_cells"], chip["memory_bits"], chip["flip_flops"]) == (1, 128, 1)
    assert chip["weight_bytes_fetched_per_decision"] is None
    assert "0 is not claimed" in chip["sentence"]


def test_the_chip_the_report_names_is_selected(tmp_path: Path) -> None:
    ir = {"nodes": [{"id": "l0", "W": [[2, -3]], "b": [1]}]}
    files = {**_chip("aaa", ir, {}), **_chip("bbb", ir, {"a": {"type": "$_AND_"}})}
    run = _run(tmp_path, [], "We picked chip bbb; aaa was larger. bbb ships.\n", files)
    result = weight_bytes(run)
    assert result["chip"] == "bbb" and "names this chip most often" in result["chip_selected_by"]


def test_one_width_rule_and_the_chip_named_in_plain_words(tmp_path: Path) -> None:
    shared = {"name": "B", "nodes": [{"id": "c", "W": [[1, 0, -1, 0]] * 4, "b": [200, -3, 0, 1]}]}
    floats = {"nodes": [{"id": "l0", "W": [[0.5, 1.5]], "b": [0.25]}]}
    files = {
        **_chip("aaa", {**shared, "meta": {"params": 7}}, {"a": {"type": "$_AND_"}}),
        **_chip("bbb", floats, {}),
        "workspace/chips/aaa/gates.v": "",
        "workspace/chips/bbb/gates.v": "",
    }
    events = [
        _event(1, 0, "artifact", kind="chip", path="workspace/chips/aaa/gates.v"),
        _event(2, 1, "artifact", kind="chip", path="workspace/chips/bbb/gates.v"),
    ]
    run = _run(tmp_path, events, "We built two chips.\n", files)
    result = weight_bytes(run)
    assert result["chip"] == "aaa"
    assert result["chip_selected_by"] == "the run named no chip; first laid-out design with weights"
    software = result["software"]
    widths = {t["field"]: (t["bits"], t["min_bits"]) for t in software["tensors"]}
    assert widths == {"nodes[c].W": (8, 2), "nodes[c].b": (16, 9)}  # ternary in int8; 200 needs int16
    assert (software["parameters"], software["declared_params"]) == (20, 7)
    assert software["bytes_per_decision"] == 16 + 8 and software["bytes_at_minimal_widths"] == 9
    assert "declares 7 parameters but its arrays store 20 values" in software["sentence"]
    other = result["other_laid_out_chips"][0]
    assert (other["chip"], other["software_bytes_per_decision"]) == ("bbb", 12)  # float32
    md = render_markdown(build_evidence(run, write=False))
    assert "These figures are for chip `aaa`. Why this chip: the run named no chip; first laid-out" in md


# ---- C. stage timings ----


def test_stage_timings_with_a_skip_and_a_run_cut_off() -> None:
    events = [
        _event(1, 0, "run.started", prompt="p"),
        _event(2, 0, "stage", name="spec", state="started"),
        _event(3, 10, "stage", name="spec", state="done"),
        _event(4, 10, "stage", name="reference", state="skipped", reason="no data"),
        _event(5, 10, "stage", name="compile", state="started"),
        _event(6, 11, "tool", call_id="a", name="Bash", summary="compile A", state="started"),
        _event(7, 12, "tool", call_id="b", name="Bash", summary="compile B", state="started"),
        _metric(8, 20, "gates", 100),
        _metric(9, 25, "gates", 120),
        _metric(10, 30, "gates", 90),
        _event(11, 30, "tool", call_id="a", name="Bash", summary="compile A", state="done"),
        _event(12, 35, "tool", call_id="b", name="Bash", summary="compile B", state="done"),
        _event(13, 40, "stage", name="compile", state="done"),
        _event(14, 40, "stage", name="verify", state="started"),
        _metric(15, 100, "vectors_checked", 600),
    ]
    result = stage_timings(events)
    stages = {s["stage"]: s for s in result["stages"]}
    assert result["run_finished"] is False and result["total_seconds"] == 100
    assert (stages["spec"]["seconds"], stages["spec"]["share"]) == (10, 0.1)
    assert (stages["reference"]["seconds"], stages["reference"]["state"]) == (0, "skipped")
    assert stages["compile"]["seconds"] == 30
    assert stages["compile"]["items"] == [{"item": "designs synthesised", "count": 3}]
    assert stages["verify"]["state"] == "open (no done event)" and stages["verify"]["seconds"] == 60
    assert stages["verify"]["items"] == [{"item": "vectors checked", "count": 600}]
    largest = result["largest"]
    assert largest["stage"] == "verify" and largest["share"] == 0.6
    assert largest["bound_if_others_free"] == pytest.approx(1.67)
    assert largest["bound_if_this_free"] == pytest.approx(2.5)
    assert "If every other stage cost nothing, the run would be at most 1.67x faster" in largest["sentence"]
    assert "if this stage cost nothing, at most 2.50x faster" in largest["sentence"]
    assert stages["spec"]["bound_if_this_stage_free"] == pytest.approx(1.11)
    assert "per_second" not in json.dumps(result)
    tools = result["tool_calls"]
    assert (tools["count"], tools["total_seconds"], tools["overlapping_calls"]) == (2, 42, 1)
    assert tools["longest"] == {"summary": "compile B", "seconds": 23}


# ---- wiring: CLI, API, the run's hook ----


def _sample_run(tmp_path: Path) -> Path:
    events = [
        _event(1, 0, "run.started", prompt="p"),
        _event(2, 0, "stage", name="compile", state="started"),
        _metric(3, 5, "gates", 2367, "gates"),
        _event(4, 10, "stage", name="compile", state="done"),
        _event(5, 11, "run.finished", status="succeeded"),
    ]
    return _run(tmp_path, events, "The chip has 2367 gates.\n")


def test_cli_prints_and_writes_the_evidence(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config = tmp_path / "cfg.yaml"
    config.write_text(yaml.safe_dump({"runs_dir": str(tmp_path), "log_dir": str(tmp_path / "logs")}))
    run = _sample_run(tmp_path)

    assert cli.main(["evidence", "--config", str(config), str(run), "--json"]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["numbers"]["traced"] == 1 and printed["run_finished"] is True
    assert json.loads((run / EVIDENCE_JSON).read_text()) == printed

    assert cli.main(["evidence", "--config", str(config), run.name]) == 0
    assert capsys.readouterr().out.startswith("# Run evidence: r\n")
    assert (run / EVIDENCE_MD).is_file()
    assert cli.main(["evidence", "--config", str(config), "no-such-run"]) == 2


def test_the_hook_swallows_an_evidence_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("evidence broke")

    appended: list[str] = []
    monkeypatch.setattr(evidence_mod, "build_evidence", boom)
    emit_evidence(tmp_path, lambda type_, **fields: appended.append(type_))
    assert appended == []


def _app(config: BackendConfig, step_s: float) -> TestClient:
    flex = config.compute.flex.model_copy(update={"require_macos": False})
    config = config.model_copy(update={"compute": config.compute.model_copy(update={"flex": flex})})
    api = ApiConfig(keepalive_s=0.2, progress_poll_s=0.02, stub_step_s=step_s, run_timeout_s=60)
    return TestClient(TestServer(create_app(config, api, token=TOKEN, agent="stub")))


@pytest.fixture
async def client(config: BackendConfig) -> AsyncIterator[TestClient]:
    async with _app(config, 0.01) as c:
        yield c


async def _start(client: TestClient) -> str:
    resp = await client.post(
        "/api/runs", json={"prompt": "A seizure wristband"}, headers={TOKEN_HEADER: TOKEN}
    )
    assert resp.status == 201
    return str((await resp.json())["id"])


async def _wait_finished(client: TestClient, run_id: str) -> None:
    async with asyncio.timeout(20):
        while True:
            resp = await client.get(f"/api/runs/{run_id}", headers={TOKEN_HEADER: TOKEN})
            if (await resp.json())["status"] != "running":
                return
            await asyncio.sleep(0.05)


async def test_api_route_and_the_evidence_event(client: TestClient, config: BackendConfig) -> None:
    run_id = await _start(client)
    await _wait_finished(client, run_id)
    lines = (config.resolved_runs_dir() / run_id / "events.jsonl").read_text().splitlines()
    types = [json.loads(line)["type"] for line in lines]
    assert types[-2:] == ["evidence", "run.finished"]
    event = json.loads(lines[-2])
    assert set(event) >= {"numbers", "weights", "stages"} and event["numbers"]["traced"] is not None
    assert set(event["numbers"]) == {"traced", "value_found_meaning_not_confirmed", "untraced", "excluded"}
    assert (config.resolved_runs_dir() / run_id / EVIDENCE_JSON).is_file()

    resp = await client.get(f"/api/runs/{run_id}/evidence", headers={TOKEN_HEADER: TOKEN})
    assert resp.status == 200
    body = await resp.json()
    assert body["run_finished"] is True and body["stages"]["stages"]
    assert (await client.get(f"/api/runs/{run_id}/evidence")).status == 401
    assert (await client.get("/api/runs/nope/evidence", headers={TOKEN_HEADER: TOKEN})).status == 404


async def test_api_evidence_failure_is_a_clean_error(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = await _start(client)
    await _wait_finished(client, run_id)

    def boom(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("evidence broke")

    monkeypatch.setattr(server_mod, "build_evidence", boom)
    resp = await client.get(f"/api/runs/{run_id}/evidence", headers={TOKEN_HEADER: TOKEN})
    assert resp.status == 500
    assert await resp.json() == {"error": "the evidence could not be computed (RuntimeError)"}


async def test_api_evidence_waits_for_the_run(config: BackendConfig) -> None:
    async with _app(config, 3.0) as slow:
        run_id = await _start(slow)
        resp = await slow.get(f"/api/runs/{run_id}/evidence", headers={TOKEN_HEADER: TOKEN})
        assert resp.status == 409
        await slow.post(f"/api/runs/{run_id}/stop", headers={TOKEN_HEADER: TOKEN})


async def test_a_failing_evidence_hook_never_fails_the_run(
    client: TestClient, config: BackendConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("evidence broke")

    monkeypatch.setattr(evidence_mod, "build_evidence", boom)
    run_id = await _start(client)
    await _wait_finished(client, run_id)
    lines = (config.resolved_runs_dir() / run_id / "events.jsonl").read_text().splitlines()
    last = json.loads(lines[-1])
    assert (last["type"], last["status"]) == ("run.finished", "succeeded")
    assert all(json.loads(line)["type"] != "evidence" for line in lines)
