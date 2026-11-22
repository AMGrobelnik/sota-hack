"""The user's structured spec for a run: checked, saved as ``spec.json``, shown to the agent.

``POST /api/runs`` (and ``run --preset --spec-file``) may carry ``spec``::

    {"brief", "device", "signal", "detect",
     "task_types": ["monitoring" | "screening" | "grading"], "patient_group",
     "place": "ward" | "home" | "patient", "fa_unit": "hour" | "night" | "day",
     "targets": [{"metric", "op": "at_least" | "at_most", "value", "unit"}],
     "primary",
     "constraints": {"channels", "find_best", "battery_hours", "reusable", "layout"},
     "data": {"mode": "public" | "own" | "simulate", "dataset"}}

:func:`parse_spec` checks it (a ``SpecError`` names the field), and resolves
the data: ``simulate`` is synthetic data; ``public`` uses a dataset only when
the server's ``datasets`` setting maps its name to a local folder, else the
agent is told it is not available and falls back to synthetic data; ``own``
is not available in this build. ``constraints.layout`` false means no physical
layout (no layout, timing after layout, GDS or tape-out files); left out, it is
false when the brief says so ("no physical layout needed") and else unset. The
run gets ``workspace/spec.json``, a short
"The user's spec" block at the top of the agent's first message, and the
paragraph in ``spec.md`` added to its standing instructions.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SPEC_FILE = "spec.json"
SPEC_INSTRUCTIONS_PATH = Path(__file__).with_name("spec.md")
TASK_TYPES = ("monitoring", "screening", "grading")
PLACES = ("ward", "home", "patient")
FA_UNITS = ("hour", "night", "day")
# hours in one false-alarm unit, as the dashboard counts them: a night is 12 hours, a day 24
FA_UNIT_HOURS = {"hour": 1, "night": 12, "day": 24}
OPS = ("at_least", "at_most")
DATA_MODES = ("public", "own", "simulate")
FIELDS = (
    "brief",
    "device",
    "signal",
    "detect",
    "task_types",
    "patient_group",
    "place",
    "fa_unit",
    "targets",
    "primary",
    "constraints",
    "data",
)
REQUIRED = ("device", "signal", "detect", "targets", "primary", "data")
CONSTRAINT_FIELDS = ("channels", "find_best", "battery_hours", "reusable", "layout")
_METRIC = re.compile(r"[a-z][a-z0-9_]{0,59}")
#: A brief that turns physical layout down: "no physical layout needed", "without a layout", "skip layout".
_NO_LAYOUT = re.compile(
    r"\b(?:no|without(?: an?| any)?|skip(?: the)?|(?:do not|don't|doesn't|does not) need(?: an?| the| any)?)"
    r"\s+(?:physical\s+|chip\s+)?layout\b"
    r"|\b(?:physical\s+)?layout\s+(?:is\s+)?not\s+(?:needed|required|wanted)\b"
    r"|\bno need for (?:an? |the )?(?:physical )?layout\b",
    re.IGNORECASE,
)


class SpecError(ValueError):
    """A spec that cannot be used; the message names the field."""


@dataclass(frozen=True)
class RunSpec:
    """A checked spec, what data the run uses, and the block the agent reads."""

    spec: dict[str, Any]
    data_used: dict[str, Any]
    block: str

    def to_json(self) -> dict[str, Any]:
        """``spec.json``: the user's spec plus ``data_used``."""
        return {**self.spec, "data_used": self.data_used}


def _text(where: str, value: Any, limit: int, *, required: bool = False) -> str | None:
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value.strip():
        raise SpecError(f"spec.{where} must be a non-empty string")
    flat = " ".join(value.split())
    if len(flat) > limit:
        raise SpecError(f"spec.{where} is longer than {limit} characters")
    return flat


def _choice(where: str, value: Any, options: tuple[str, ...], default: str | None = None) -> str | None:
    if value is None:
        return default
    if value not in options:
        raise SpecError(f"spec.{where} must be one of {', '.join(options)}")
    return str(value)


def _number(where: str, value: Any, *, whole: bool = False, positive: bool = False) -> Any:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise SpecError(f"spec.{where} must be a number or null")
    if whole and not float(value).is_integer():
        raise SpecError(f"spec.{where} must be a whole number or null")
    if positive and value <= 0:
        raise SpecError(f"spec.{where} must be more than 0")
    return int(value) if whole else value


def _flag(where: str, value: Any) -> bool | None:
    if value is not None and not isinstance(value, bool):
        raise SpecError(f"spec.{where} must be true, false or null")
    return value


def _object(where: str, value: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    name = f"spec.{where}" if where else "spec"
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise SpecError(f"{name} must be an object")
    unknown = sorted(str(k) for k in value if k not in fields)
    if unknown:
        raise SpecError(f"{name} has unknown field(s) {', '.join(unknown)}; it takes {', '.join(fields)}")
    return value


def _targets(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not 1 <= len(value) <= 12:
        raise SpecError("spec.targets must be a list of 1 to 12 targets")
    out = []
    for i, raw in enumerate(value):
        where = f"targets[{i}]"
        target = _object(where, raw, ("metric", "op", "value", "unit"))
        metric = target.get("metric")
        if not isinstance(metric, str) or not _METRIC.fullmatch(metric):
            raise SpecError(f"spec.{where}.metric must be a metric name such as sensitivity or fa_per_hour")
        if target.get("value") is None:
            raise SpecError(f"spec.{where}.value is required")
        out.append(
            {
                "metric": metric,
                "op": _choice(f"{where}.op", target.get("op"), OPS) or _missing(f"{where}.op"),
                "value": _number(f"{where}.value", target["value"]),
                "unit": _text(f"{where}.unit", target.get("unit"), 20),
            }
        )
    return out


def _layout(value: Any, brief: Any) -> bool | None:
    """``constraints.layout`` as given, else false when the brief turns physical layout down."""
    given = _flag("constraints.layout", value)
    if given is not None:
        return given
    return False if isinstance(brief, str) and _NO_LAYOUT.search(brief) else None


def _missing(where: str) -> str:
    raise SpecError(f"spec.{where} is required")


def parse_spec(raw: Any, datasets: Mapping[str, Path] | None = None) -> RunSpec:
    """Check and normalise a request's ``spec``; ``SpecError`` names the first problem."""
    body = _object("", raw, FIELDS) if isinstance(raw, dict) else None
    if body is None:
        raise SpecError("spec must be an object")
    missing = [k for k in REQUIRED if body.get(k) is None]
    if missing:
        raise SpecError(f"spec is missing {', '.join(missing)}")
    task_types = body.get("task_types") or []
    if not isinstance(task_types, list) or any(t not in TASK_TYPES for t in task_types):
        raise SpecError(f"spec.task_types must be a list of {', '.join(TASK_TYPES)}")
    constraints = _object("constraints", body.get("constraints"), CONSTRAINT_FIELDS)
    data = _object("data", body["data"], ("mode", "dataset"))
    spec = {
        "brief": _text("brief", body.get("brief"), 4000),
        "device": _text("device", body["device"], 200, required=True),
        "signal": _text("signal", body["signal"], 200, required=True),
        "detect": _text("detect", body["detect"], 200, required=True),
        "task_types": list(dict.fromkeys(task_types)),
        "patient_group": _text("patient_group", body.get("patient_group"), 200),
        "place": _choice("place", body.get("place"), PLACES),
        "fa_unit": _choice("fa_unit", body.get("fa_unit"), FA_UNITS, default="hour"),
        "targets": _targets(body["targets"]),
        "primary": _text("primary", body["primary"], 60, required=True),
        "constraints": {
            "channels": _number(
                "constraints.channels", constraints.get("channels"), whole=True, positive=True
            ),
            "find_best": bool(_flag("constraints.find_best", constraints.get("find_best"))),
            "battery_hours": _number(
                "constraints.battery_hours", constraints.get("battery_hours"), positive=True
            ),
            "reusable": _flag("constraints.reusable", constraints.get("reusable")),
            "layout": _layout(constraints.get("layout"), body.get("brief")),
        },
        "data": {
            "mode": _choice("data.mode", data.get("mode"), DATA_MODES) or _missing("data.mode"),
            "dataset": _text("data.dataset", data.get("dataset"), 100),
        },
    }
    data_used = resolve_data(spec["data"], datasets or {})
    return RunSpec(spec=spec, data_used=data_used, block=render_block(spec, data_used))


def resolve_data(data: dict[str, Any], datasets: Mapping[str, Path]) -> dict[str, Any]:
    """What data the run uses: ``{"use": "synthetic" | "public:<name>", "folder", "reason"}``."""
    mode, name = data["mode"], data.get("dataset")
    folder = Path(datasets[name]).expanduser() if name in datasets else None
    if mode == "simulate":
        reason = "the user asked for simulated data"
    elif mode == "own":
        reason = "the user's own data is not available in this build"
    elif not name:
        reason = "public data was asked for without a dataset name"
    elif folder is None:
        reason = f"the dataset {name} is not set up on this server"
    elif not folder.is_dir():
        reason = f"the folder set up for the dataset {name} is missing"
    else:
        return {"use": f"public:{name}", "folder": str(folder.resolve()), "reason": "set up on this server"}
    return {"use": "synthetic", "folder": None, "reason": reason}


def _value(value: Any) -> str:
    return f"{value:g}" if isinstance(value, float) else str(value)


def render_block(spec: dict[str, Any], data_used: dict[str, Any]) -> str:
    """The short "The user's spec" block at the top of the agent's first message."""
    words = {"at_least": "at least", "at_most": "at most"}
    lines = ["## The user's spec", ""]
    for label, key in (("Device", "device"), ("Signal", "signal"), ("Detect", "detect")):
        lines.append(f"- {label}: {spec[key]}")
    if spec["task_types"]:
        lines.append(f"- Task: {', '.join(spec['task_types'])}")
    if spec["patient_group"]:
        lines.append(f"- Patients: {spec['patient_group']}")
    if spec["place"]:
        lines.append(f"- Where it is used: {spec['place']}")
    lines.append("- Targets (each is a bar the chosen design is judged against):")
    for t in spec["targets"]:
        unit = f" {t['unit']}" if t["unit"] else ""
        lines.append(f"  - {t['metric']} {words[t['op']]} {_value(t['value'])}{unit}")
    lines.append(f"- Primary metric (the user's chart plots it): {spec['primary']}")
    hours = FA_UNIT_HOURS[spec["fa_unit"]]
    per = "hour" if hours == 1 else f"{spec['fa_unit']} ({hours} hours; per hour times {hours})"
    lines.append(f"- False alarms are counted per {per}")
    c = spec["constraints"]
    if c["find_best"]:
        lines.append("- Channels: find the best budget (compare designs at two or more channel counts)")
    elif c["channels"] is not None:
        lines.append(f"- Channels: {c['channels']} at most, every candidate")
    else:
        lines.append("- Channels: not stated; choose and say why")
    if c["battery_hours"] is not None:
        lines.append(f"- Battery: {_value(c['battery_hours'])} h")
    if c["reusable"] is not None:
        lines.append(f"- Reusable device: {'yes' if c['reusable'] else 'no'}")
    if c.get("layout") is False:
        lines.append(
            "- Physical layout: NOT wanted (the user said so). Do not call layout, timing-power, "
            "tt-package, tt-export or bitstream; report the synthesis-based chip figures and say "
            "layout was left out at the user's request."
        )
    elif c.get("layout") is True:
        lines.append("- Physical layout: wanted (run layout and timing-power on the chosen chip)")
    if data_used["use"] == "synthetic":
        lines.append(
            f"- Data: SYNTHETIC ({data_used['reason']}). Generate synthetic recordings and write "
            '"synthetic data" with every result; never call them patient data.'
        )
    else:
        lines.append(
            f"- Data: the public dataset {spec['data']['dataset']}, read-only at {data_used['folder']}. "
            "Read it from there; do not copy it into your working folder."
        )
    if spec["brief"]:
        lines.append(f"- In the user's words: {spec['brief']}")
    lines += [
        "",
        f"The full spec is `{SPEC_FILE}` in your working folder. Restate and check it; do not change it.",
    ]
    return "\n".join(lines)


def write_spec(workspace: Path, run_spec: RunSpec) -> Path:
    """Write ``workspace/spec.json``; returns its path."""
    path = workspace / SPEC_FILE
    path.write_text(json.dumps(run_spec.to_json(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def spec_instructions() -> str:
    """The standing-instructions paragraph for a run with a spec (``spec.md``)."""
    return SPEC_INSTRUCTIONS_PATH.read_text(encoding="utf-8")


__all__ = [
    "SPEC_FILE",
    "SPEC_INSTRUCTIONS_PATH",
    "RunSpec",
    "SpecError",
    "parse_spec",
    "render_block",
    "resolve_data",
    "spec_instructions",
    "write_spec",
]
