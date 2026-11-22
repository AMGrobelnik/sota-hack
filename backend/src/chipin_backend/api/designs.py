"""Design records: one per candidate design the agent scores, for the dashboard's trade-off chart.

The agent reports each candidate with the run's helper::

    ./progress design design_a.json          # a file holding one JSON object
    ./progress design '{"id": "a", ...}'     # or the object itself

The helper checks the record with :func:`validate_design` (its source is
copied into the helper, so both sides apply the same rules) and refuses a bad
one with exit status 2 and the reason; nothing is written then. The progress
tailer checks it again, keeps the latest record per ``id`` in the run's
``designs.json`` and emits a ``design`` event carrying it. A record with
``previous_id`` takes over the record of that id (a candidate renamed to the
lab's design id once compiled). A record with ``variant_of`` is a design of
its own that is the same model as the design of that id compiled another way
(another lab route or option); both stay, and the page can group them.
``GET /api/runs/{id}/designs`` serves the file.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from chipin_backend.api.events import EventLog

DESIGNS_FILE = "designs.json"


def validate_design(record: Any) -> dict[str, Any]:
    """The checked, normalised design record; ``ValueError`` naming the first problem.

    Self-contained (standard library only, nothing from this module): the
    progress helper carries a copy of this function's source.
    """
    import math

    fraction_metrics = ("sensitivity", "specificity", "agreement", "ppv", "precision", "accuracy", "f1")
    top = {
        "id": True,
        "label": True,
        "budget": True,
        "metrics": True,
        "basis": True,
        "data": True,
        "gates": False,
        "gates_est": False,
        "depth": False,
        "counts": False,
        "per_patient": False,
        "verified": False,
        "note": False,
        "previous_id": False,
        "variant_of": False,
        "agent": False,
    }
    count_keys = (
        "events_caught",
        "events_total",
        "negatives_correct",
        "negatives_total",
        "hours",
        "patients",
    )
    patient_keys = ("id", "caught", "total", "false_alarms", "hours")
    verified_keys = ("vectors", "mismatches", "level", "proved")

    def fail(message: str) -> None:
        raise ValueError(message)

    def text(where: str, value: Any, limit: int, *, required: bool) -> str | None:
        if value is None and not required:
            return None
        if not isinstance(value, str) or not value.strip():
            fail(f"{where} must be a non-empty string")
        flat = " ".join(value.split())
        if len(flat) > limit:
            fail(f"{where} is longer than {limit} characters")
        return flat

    def number(where: str, value: Any, *, whole: bool = False, allow_none: bool = True) -> Any:
        if value is None and allow_none:
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            fail(f"{where} must be a {'whole number' if whole else 'finite number'}")
        if whole and not float(value).is_integer():
            fail(f"{where} must be a whole number")
        if value < 0:
            fail(f"{where} must not be negative")
        return int(value) if whole else value

    if not isinstance(record, dict):
        fail("a design record must be a JSON object")
    unknown = sorted(str(k) for k in record if k not in top)
    if unknown:
        fail(f"unknown field(s) {', '.join(unknown)}; the fields are {', '.join(top)}")
    missing = [k for k, required in top.items() if required and record.get(k) is None]
    if missing:
        fail(f"missing field(s) {', '.join(missing)}")

    out: dict[str, Any] = {
        "id": text("id", record["id"], 200, required=True),
        "label": text("label", record["label"], 120, required=True),
    }

    budget = record["budget"]
    if not isinstance(budget, dict):
        fail('budget must be an object such as {"channels": 2, "name": "2 electrodes"}')
    extra = sorted(str(k) for k in budget if k not in ("channels", "sensors", "name"))
    if extra:
        fail(f"budget has unknown field(s) {', '.join(extra)}; it takes channels or sensors, and name")
    sizes = [k for k in ("channels", "sensors") if budget.get(k) is not None]
    if len(sizes) != 1:
        fail("budget needs exactly one of channels or sensors")
    size = number(f"budget.{sizes[0]}", budget[sizes[0]], whole=True, allow_none=False)
    if size < 1:
        fail(f"budget.{sizes[0]} must be at least 1")
    out["budget"] = {sizes[0]: size, "name": text("budget.name", budget.get("name"), 60, required=True)}

    out["gates"] = number("gates", record.get("gates"), whole=True)
    out["gates_est"] = number("gates_est", record.get("gates_est"))
    out["depth"] = number("depth", record.get("depth"), whole=True)

    metrics = record["metrics"]
    if not isinstance(metrics, dict) or not metrics:
        fail("metrics must be a non-empty object of metric name to number")
    out["metrics"] = {}
    for key, value in metrics.items():
        name = text("a metric name", key, 60, required=True)
        out["metrics"][name] = number(f"metrics.{name}", value)
        if name in fraction_metrics and value is not None and value > 1:
            fail(f"metrics.{name} must be a fraction from 0 to 1, not {value}")

    if record["basis"] not in ("validation", "test"):
        fail("basis must be validation or test")
    out["basis"] = record["basis"]

    counts = record.get("counts")
    if counts is not None:
        if not isinstance(counts, dict):
            fail("counts must be an object")
        extra = sorted(str(k) for k in counts if k not in count_keys)
        if extra:
            fail(f"counts has unknown field(s) {', '.join(extra)}; it takes {', '.join(count_keys)}")
        counts = {
            k: number(f"counts.{k}", counts.get(k), whole=k != "hours") for k in count_keys if k in counts
        }
        for part, whole in (("events_caught", "events_total"), ("negatives_correct", "negatives_total")):
            if (
                counts.get(part) is not None
                and counts.get(whole) is not None
                and counts[part] > counts[whole]
            ):
                fail(f"counts.{part} ({counts[part]}) is more than counts.{whole} ({counts[whole]})")
    out["counts"] = counts

    per_patient = record.get("per_patient")
    if per_patient is not None:
        if not isinstance(per_patient, list) or len(per_patient) > 1000:
            fail("per_patient must be a list of at most 1000 objects")
        rows = []
        for i, row in enumerate(per_patient):
            where = f"per_patient[{i}]"
            if not isinstance(row, dict):
                fail(f"{where} must be an object")
            extra = sorted(str(k) for k in row if k not in patient_keys)
            if extra:
                fail(f"{where} has unknown field(s) {', '.join(extra)}; it takes {', '.join(patient_keys)}")
            pid = row.get("id")
            if isinstance(pid, int) and not isinstance(pid, bool):
                pid = str(pid)
            item = {"id": text(f"{where}.id", pid, 40, required=True)}
            for key in patient_keys[1:]:
                item[key] = number(f"{where}.{key}", row.get(key), whole=key != "hours", allow_none=False)
            if item["caught"] > item["total"]:
                fail(f"{where}.caught ({item['caught']}) is more than its total ({item['total']})")
            rows.append(item)
        if len({r["id"] for r in rows}) != len(rows):
            fail("per_patient ids must be unique")
        per_patient = rows
    out["per_patient"] = per_patient

    if counts and per_patient:
        for key, column in (("events_caught", "caught"), ("events_total", "total")):
            total = sum(r[column] for r in per_patient)
            if counts.get(key) is not None and counts[key] != total:
                fail(f"counts.{key} ({counts[key]}) differs from the per_patient sum of {column} ({total})")
        if counts.get("patients") is not None and counts["patients"] != len(per_patient):
            fail(
                f"counts.patients ({counts['patients']}) differs from the {len(per_patient)} per_patient rows"
            )
        hours = sum(r["hours"] for r in per_patient)
        if counts.get("hours") is not None and abs(counts["hours"] - hours) > max(0.01, 0.01 * hours):
            fail(f"counts.hours ({counts['hours']}) differs from the per_patient sum of hours ({hours:g})")
    if counts:
        for metric, part, whole in (
            ("sensitivity", "events_caught", "events_total"),
            ("specificity", "negatives_correct", "negatives_total"),
        ):
            value = out["metrics"].get(metric)
            if value is not None and counts.get(part) is not None and counts.get(whole):
                expected = counts[part] / counts[whole]
                if abs(value - expected) > 0.011:
                    fail(
                        f"metrics.{metric} ({value}) does not match counts.{part}/counts.{whole} "
                        f"({counts[part]}/{counts[whole]} = {expected:.3f})"
                    )
        fa = out["metrics"].get("fa_per_hour")
        if fa is not None and per_patient and counts.get("hours"):
            expected = sum(r["false_alarms"] for r in per_patient) / counts["hours"]
            if abs(fa - expected) > max(0.01, 0.02 * expected):
                fail(
                    f"metrics.fa_per_hour ({fa}) does not match the per_patient false alarms over "
                    f"counts.hours ({expected:.3f})"
                )

    verified = record.get("verified")
    if verified is not None:
        if not isinstance(verified, dict) or not verified:
            fail("verified must be an object with vectors, mismatches, level, proved (or null)")
        extra = sorted(str(k) for k in verified if k not in verified_keys)
        if extra:
            fail(f"verified has unknown field(s) {', '.join(extra)}; it takes {', '.join(verified_keys)}")
        checked: dict[str, Any] = {
            "vectors": number("verified.vectors", verified.get("vectors"), whole=True),
            "mismatches": number("verified.mismatches", verified.get("mismatches"), whole=True),
            "level": text("verified.level", verified.get("level"), 60, required=False),
            "proved": verified.get("proved"),
        }
        if checked["proved"] is not None and not isinstance(checked["proved"], bool):
            fail("verified.proved must be true, false or null")
        if (
            checked["vectors"] is not None
            and checked["mismatches"] is not None
            and checked["mismatches"] > checked["vectors"]
        ):
            fail("verified.mismatches is more than verified.vectors")
        verified = checked
    out["verified"] = verified

    data = record["data"]
    if not isinstance(data, str) or not (
        data == "synthetic" or (data.startswith("public:") and 0 < len(data[7:].strip()) <= 100)
    ):
        fail("data must be synthetic or public:<dataset name>")
    out["data"] = data
    out["note"] = text("note", record.get("note"), 500, required=False)
    previous = text("previous_id", record.get("previous_id"), 200, required=False)
    if previous is not None and previous != out["id"]:
        out["previous_id"] = previous
    variant = text("variant_of", record.get("variant_of"), 200, required=False)
    if variant is not None:
        if variant == out["id"]:
            fail("variant_of names another design (the same model compiled another way), not this one")
        if variant == previous:
            fail("variant_of and previous_id name the same design: previous_id renames, variant_of groups")
        out["variant_of"] = variant
    agent = text("agent", record.get("agent"), 100, required=False)
    if agent is not None:
        out["agent"] = agent
    return out


def read_designs(run_path: Path) -> list[dict[str, Any]]:
    """The run's latest record per design, in the order they were first reported."""
    path = run_path / DESIGNS_FILE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    designs = data.get("designs") if isinstance(data, dict) else None
    return designs if isinstance(designs, list) else []


def emit_design(log: EventLog, run_path: Path, item: dict[str, Any], *, agent: str | None = None) -> None:
    """Check one ``design`` progress line, upsert it in ``designs.json`` and emit a ``design`` event.

    ``agent``: the fan-out subagent that reported it; its id replaces any ``agent`` in the record.
    """
    record = validate_design({k: v for k, v in item.items() if k not in ("type", "ts")})
    if agent is not None:
        record["agent"] = agent
    designs = read_designs(run_path)
    index = {d.get("id"): i for i, d in enumerate(designs)}
    same, taken_over = index.get(record["id"]), index.get(record.get("previous_id"))
    if same is None and taken_over is None:
        at, revision = len(designs), 1
        designs.append({})
    else:
        at = same if same is not None else taken_over
        revision = int(designs[at].get("revision", 1)) + 1
        if same is not None and taken_over is not None and taken_over != same:
            designs.pop(taken_over)
            at -= 1 if taken_over < at else 0
    event = log.append("design", design=record, revision=revision, agent=record.get("agent"))
    designs[at] = {**record, "revision": revision, "ts": event["ts"] if event else None}
    path = run_path / DESIGNS_FILE
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"designs": designs}, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def designs_view(run_path: Path, log: EventLog) -> dict[str, Any]:
    """``GET /api/runs/{id}/designs``: every design's latest record and the run's chosen chip."""
    chosen = [e["chip"] for e in log.since(1) if e.get("type") == "chosen" and e.get("chip")]
    return {"designs": read_designs(run_path), "chosen": chosen[-1] if chosen else None}


__all__ = ["DESIGNS_FILE", "designs_view", "emit_design", "read_designs", "validate_design"]
