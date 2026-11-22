"""Chippy's read tools: what the helper may look at, all read-only, all bounded.

Every tool reads run folders under one runs folder and nothing else. A run id
must be one safe folder name; a file path must resolve inside that run's
folder, must not pass through a hidden folder and must not name an
instruction or key file. Every result leaves through :func:`clip_result`, so
no tool can put more than ``max_result_bytes`` into the model's context.

Numbers carry a ``basis``: ``measured``, ``estimate`` or ``measured on
simulated data``, following the page's own marking (how-it-works, section 7).
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from chipin_backend.runs import is_safe_run_id

FACTS_PATH = Path(__file__).with_name("helper_facts.md")

#: File names never read, wherever they sit: instruction and key files.
REFUSED_NAMES = frozenset({"claude.md", "claude.local.md", "agents.md", ".env", ".env.local"})
#: Raw agent transcripts: not the contract events, and they can be large.
REFUSED_RUN_FILES = frozenset({"agent_events.jsonl"})
TEXT_SUFFIXES = frozenset(
    {".md", ".txt", ".json", ".jsonl", ".csv", ".py", ".v", ".sv", ".yaml", ".yml", ".log", ".sh", ""}
)

_ESTIMATE_KEY = re.compile(r"area|power|cost|timing|slack|_est\b|_est_|estimate|energy_pj|_eur\b", re.I)
_SCORE_KEY = re.compile(
    r"sensitiv|specific|fa_per|false_alarm|accura|_acc\b|^acc|caught|auc|f1|patients_pass|kappa|agree", re.I
)
_STAGES = ("spec", "reference", "propose", "finetune", "compile", "verify", "report")


class ToolError(ValueError):
    """A tool call the model got wrong; its text goes back to the model."""


@dataclass(frozen=True)
class ToolLimits:
    """Bounds on what one tool call may read and return."""

    max_result_bytes: int = 4096
    max_string_chars: int = 600
    max_rows: int = 60
    file_window_bytes: int = 3000
    max_event_bytes: int = 8_000_000
    max_search_hits: int = 10


# ---------------------------------------------------------------- run folders


@dataclass
class RunFolder:
    """One run folder, read lazily and only through the guarded helpers here."""

    path: Path

    @property
    def id(self) -> str:
        return self.path.name

    def _json(self, name: str) -> dict[str, Any]:
        target = self.path / name
        if not target.is_file():
            return {}
        try:
            data = json.loads(target.read_text(encoding="utf-8", errors="replace"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def record(self) -> dict[str, Any]:
        """``api.json`` (dashboard runs), else the plain fields of ``run.json``."""
        api = self._json("api.json")
        if api:
            return api
        run = self._json("run.json")
        agent = run.get("agent") if isinstance(run.get("agent"), dict) else {}
        prompts = agent.get("prompts") or [""]
        result = run.get("result") if isinstance(run.get("result"), dict) else {}
        return {
            "id": self.id,
            "status": run.get("status"),
            "prompt": prompts[-1] if prompts else "",
            "started_at": run.get("started_at") or run.get("created_at"),
            "finished_at": run.get("finished_at"),
            "summary": result.get("output") if isinstance(result.get("output"), str) else None,
        }

    def events(self, limit_bytes: int) -> list[dict[str, Any]]:
        """``events.jsonl`` as dicts, reading at most ``limit_bytes``."""
        target = self.path / "events.jsonl"
        if not target.is_file():
            return []
        out: list[dict[str, Any]] = []
        read = 0
        with target.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                read += len(line)
                if read > limit_bytes:
                    break
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(event, dict):
                    out.append(event)
        return out

    def designs_file(self) -> list[dict[str, Any]]:
        designs = self._json("designs.json").get("designs")
        return [d for d in designs if isinstance(d, dict)] if isinstance(designs, list) else []

    def spec(self) -> dict[str, Any]:
        return self._json("workspace/spec.json")


class RunStore:
    """Every run folder under ``root``; the only way tools reach the disk."""

    def __init__(self, root: Path, limits: ToolLimits | None = None) -> None:
        self.root = root.resolve()
        self.limits = limits or ToolLimits()

    def ids(self) -> list[str]:
        if not self.root.is_dir():
            return []
        found = [
            p.name
            for p in self.root.iterdir()
            if p.is_dir()
            and is_safe_run_id(p.name)
            and ((p / "events.jsonl").is_file() or (p / "run.json").is_file())
        ]
        return sorted(found, reverse=True)

    def get(self, run_id: Any) -> RunFolder:
        if not isinstance(run_id, str) or not is_safe_run_id(run_id):
            raise ToolError("run_id must be a run id from list_runs")
        path = (self.root / run_id).resolve()
        if path.parent != self.root or not path.is_dir():
            raise ToolError(f"no run {run_id!r}; call list_runs for the ids")
        return RunFolder(path)

    def file(self, run: RunFolder, rel: Any) -> Path:
        """The file ``rel`` inside ``run``; ``ToolError`` for anything outside or refused."""
        if not isinstance(rel, str) or not rel.strip() or "\x00" in rel:
            raise ToolError("path is required, as list_files gives it")
        rel = rel.strip()
        if rel.startswith(("/", "~")) or "\\" in rel:
            raise ToolError("path must be a run-folder path such as workspace/report.md")
        target = (run.path / rel).resolve()
        if not target.is_relative_to(run.path):
            raise ToolError("path is outside this run's folder")
        parts = target.relative_to(run.path).parts
        if any(p.startswith(".") for p in parts) or target.name.lower() in REFUSED_NAMES:
            raise ToolError("that file is not readable by Chippy")
        if len(parts) == 1 and target.name in REFUSED_RUN_FILES:
            raise ToolError("raw agent transcripts are not read; use search_messages")
        if not target.is_file():
            raise ToolError(f"no file {rel!r}; call list_files for the paths")
        return target


# ---------------------------------------------------------------- derived facts


def metric_basis(key: str, simulated: bool) -> str:
    """How the page marks a number of this kind (how-it-works, section 7)."""
    if _ESTIMATE_KEY.search(key):
        return "estimate"
    if _SCORE_KEY.search(key):
        return "measured on simulated data" if simulated else "measured"
    return "measured"


def _simulated(run: RunFolder, designs: list[dict[str, Any]]) -> bool:
    spec = run.spec()
    used = spec.get("data_used") if isinstance(spec.get("data_used"), dict) else {}
    data = spec.get("data") if isinstance(spec.get("data"), dict) else {}
    if used.get("use") == "synthetic" or data.get("mode") == "simulate":
        return True
    brief = str(run.record().get("prompt") or "").lower()
    if re.search(r"\b(synthetic|simulated)\b", brief):
        return True
    return any(str(d.get("data", "")).lower() in ("synthetic", "simulated") for d in designs)


def _chosen(events: list[dict[str, Any]]) -> str | None:
    chosen = [e.get("chip") for e in events if e.get("type") == "chosen" and e.get("chip")]
    return str(chosen[-1]) if chosen else None


def stages_of(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Each stage's last state, first start, last end, rounds and skip reason."""
    out: dict[str, dict[str, Any]] = {}
    for e in events:
        if e.get("type") != "stage":
            continue
        name = str(e.get("name") or e.get("stage") or "")
        if not name:
            continue
        row = out.setdefault(name, {"stage": name, "state": None, "started": None, "ended": None})
        row["state"] = e.get("state")
        if e.get("state") == "started" and row["started"] is None:
            row["started"] = e.get("ts")
        if e.get("state") in ("done", "skipped"):
            row["ended"] = e.get("ts")
        if e.get("reason"):
            row["reason"] = e.get("reason")
        if isinstance(e.get("round"), int):
            row["rounds"] = max(row.get("rounds", 1), e["round"])
    order = {name: i for i, name in enumerate(_STAGES)}
    rows = sorted(out.values(), key=lambda r: order.get(r["stage"], 99))
    for name in _STAGES:
        if name not in out:
            rows.append({"stage": name, "state": "not reported"})
    return sorted(rows, key=lambda r: order.get(r["stage"], 99))


def designs_of(run: RunFolder, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The run's designs: ``designs.json`` when present, else metrics grouped by ``chip``."""
    listed = run.designs_file()
    simulated = _simulated(run, listed)
    chosen = _chosen(events)
    tagged: dict[str, dict[str, Any]] = {}
    for e in events:
        if e.get("type") == "metric" and e.get("chip") and isinstance(e.get("value"), int | float):
            key = str(e.get("key"))
            tagged.setdefault(str(e["chip"]), {})[key] = {
                "value": e["value"],
                "unit": e.get("unit"),
                "basis": metric_basis(key, simulated),
            }
    out: list[dict[str, Any]] = []
    if listed:
        for d in listed:
            design_id = str(d.get("id"))
            row: dict[str, Any] = {"id": design_id, "label": d.get("label"), "chosen": design_id == chosen}
            if isinstance(d.get("gates"), int | float):
                row["gates"] = {"value": d["gates"], "basis": "measured"}
            if isinstance(d.get("gates_est"), int | float):
                row["gates_estimated"] = {"value": d["gates_est"], "basis": "estimate"}
            if isinstance(d.get("depth"), int | float):
                row["depth"] = {"value": d["depth"], "basis": "measured"}
            scores = d.get("metrics") if isinstance(d.get("metrics"), dict) else {}
            row["scores"] = {
                k: {"value": round(v, 4), "basis": metric_basis(k, simulated)}
                for k, v in scores.items()
                if isinstance(v, int | float)
            }
            if d.get("basis"):
                row["scored_on"] = d.get("basis")
            for key in ("counts", "verified", "budget", "note", "data"):
                if d.get(key) is not None:
                    row[key] = d[key]
            if isinstance(d.get("per_patient"), list):
                row["patients"] = len(d["per_patient"])
            if design_id in tagged:
                row["metric_events"] = tagged[design_id]
            out.append(row)
        return out
    for design_id, metrics in tagged.items():
        row = {"id": design_id, "chosen": design_id == chosen, "metric_events": metrics}
        gates = metrics.get("gates")
        if gates:
            row["gates"] = {"value": gates["value"], "basis": "measured"}
        out.append(row)
    return out


def _gate_count(design: dict[str, Any]) -> float | None:
    gates = design.get("gates")
    return gates.get("value") if isinstance(gates, dict) else None


# ---------------------------------------------------------------- tools


class HelperTools:
    """The tool implementations; each takes keyword arguments from the model."""

    def __init__(self, store: RunStore) -> None:
        self.store = store
        self.limits = store.limits

    def _events(self, run: RunFolder) -> list[dict[str, Any]]:
        return run.events(self.limits.max_event_bytes)

    def list_runs(self, limit: int = 20) -> dict[str, Any]:
        rows = []
        for run_id in self.store.ids()[: _bound(limit, 1, 50)]:
            run = self.store.get(run_id)
            rec = run.record()
            events = self._events(run)
            rows.append(
                {
                    "id": run_id,
                    "status": rec.get("status"),
                    "brief": _clip(rec.get("prompt"), 160),
                    "started_at": rec.get("started_at"),
                    "preset": rec.get("preset"),
                    "chosen_chip": _chosen(events),
                }
            )
        return {"runs": rows}

    def get_run(self, run_id: str) -> dict[str, Any]:
        run = self.store.get(run_id)
        rec = run.record()
        events = self._events(run)
        designs = designs_of(run, events)
        finished = [e for e in events if e.get("type") == "run.finished"]
        costs = [e for e in events if e.get("type") == "cost" and "subagents_usd" in e] or [
            e for e in events if e.get("type") == "cost" and not e.get("agent")
        ]
        return {
            "id": run.id,
            "status": (finished[-1].get("status") if finished else None) or rec.get("status"),
            "started_at": rec.get("started_at"),
            "finished_at": rec.get("finished_at"),
            "preset": rec.get("preset"),
            "agent": rec.get("agent"),
            "brief": _clip(rec.get("prompt"), 500),
            "data": "simulated" if _simulated(run, run.designs_file()) else "not stated as simulated",
            "chosen_chip": _chosen(events),
            "designs": len(designs),
            "stages": {r["stage"]: r.get("state") for r in stages_of(events)},
            "cost_usd": (costs[-1].get("usd") if costs else (rec.get("cost") or {}).get("usd")),
            "events": len(events),
        }

    def get_spec(self, run_id: str) -> dict[str, Any]:
        run = self.store.get(run_id)
        spec = run.spec()
        out: dict[str, Any] = {"spec_json": spec or None}
        md = run.path / "workspace" / "spec.md"
        if md.is_file():
            out["spec_md"] = md.read_text(encoding="utf-8", errors="replace")[:1500]
        if not spec and "spec_md" not in out:
            out["note"] = "this run has no spec.json or spec.md"
        return out

    def get_stages(self, run_id: str) -> dict[str, Any]:
        run = self.store.get(run_id)
        return {"stages": stages_of(self._events(run))}

    def get_designs(self, run_id: str) -> dict[str, Any]:
        run = self.store.get(run_id)
        designs = designs_of(run, self._events(run))
        sized = [d for d in designs if _gate_count(d) is not None]
        smallest = min(sized, key=lambda d: _gate_count(d) or 0)["id"] if sized else None
        rows = [{k: v for k, v in d.items() if k not in ("metric_events", "budget")} for d in designs]
        return {"designs": rows, "smallest_by_gates": smallest, "chosen": _chosen(self._events(run))}

    def get_design(self, run_id: str, design_id: str) -> dict[str, Any]:
        run = self.store.get(run_id)
        events = self._events(run)
        design = next((d for d in designs_of(run, events) if d["id"] == design_id), None)
        if design is None:
            raise ToolError(f"run {run_id} has no design {design_id!r}; call get_designs")
        listed = next((d for d in run.designs_file() if str(d.get("id")) == design_id), {})
        if isinstance(listed.get("per_patient"), list):
            design["per_patient"] = listed["per_patient"][: self.limits.max_rows]
        targets = run.spec().get("targets")
        if isinstance(targets, list):
            design["targets"] = targets
        chip_dir = run.path / "workspace" / "chips" / design_id
        if chip_dir.is_dir():
            design["chip_files"] = sorted(
                str(p.relative_to(run.path)) for p in chip_dir.iterdir() if p.is_file()
            )[:20]
        return design

    def get_chosen(self, run_id: str) -> dict[str, Any]:
        run = self.store.get(run_id)
        events = self._events(run)
        chosen = _chosen(events)
        out: dict[str, Any] = {"chosen_chip": chosen}
        if chosen is None:
            out["note"] = "this run has no chosen event"
        else:
            out["design"] = next((d for d in designs_of(run, events) if d["id"] == chosen), None)
        finished = [e for e in events if e.get("type") == "run.finished"]
        if finished:
            out["final_summary"] = finished[-1].get("summary")
        return out

    def get_metrics(
        self, run_id: str, design_id: str | None = None, key: str | None = None
    ) -> dict[str, Any]:
        run = self.store.get(run_id)
        events = self._events(run)
        simulated = _simulated(run, run.designs_file())
        rows = []
        for e in events:
            if e.get("type") != "metric":
                continue
            if design_id and e.get("chip") != design_id:
                continue
            if key and key.lower() not in str(e.get("key", "")).lower():
                continue
            rows.append(
                {
                    "seq": e.get("seq"),
                    "key": e.get("key"),
                    "value": e.get("value"),
                    "unit": e.get("unit"),
                    "chip": e.get("chip"),
                    "basis": metric_basis(str(e.get("key")), simulated),
                }
            )
        return {"rows": rows[: self.limits.max_rows], "total": len(rows)}

    def get_summaries(self, run_id: str) -> dict[str, Any]:
        run = self.store.get(run_id)
        rec = run.record()
        events = self._events(run)
        finished = [e for e in events if e.get("type") == "run.finished"]
        evidence = [e for e in events if e.get("type") == "evidence"]
        out = {
            "final_summary": finished[-1].get("summary") if finished else rec.get("summary"),
            "bullets": (finished[-1].get("bullets") if finished else None) or rec.get("bullets"),
            "evidence": {k: v for k, v in evidence[-1].items() if k not in ("seq", "ts", "run_id", "type")}
            if evidence
            else None,
        }
        if not any(out.values()):
            out["note"] = "no summaries recorded for this run"
        return out

    def get_report(self, run_id: str, offset: int = 0) -> dict[str, Any]:
        run = self.store.get(run_id)
        target = run.path / "workspace" / "report.md"
        if not target.is_file():
            return {"note": "this run has no workspace/report.md"}
        return _window(target, "workspace/report.md", offset, self.limits.file_window_bytes)

    def list_files(self, run_id: str, query: str | None = None) -> dict[str, Any]:
        run = self.store.get(run_id)
        files = []
        for p in sorted(run.path.rglob("*")):
            rel = p.relative_to(run.path)
            if any(part.startswith(".") for part in rel.parts) or not p.is_file():
                continue
            if p.name.lower() in REFUSED_NAMES or (len(rel.parts) == 1 and p.name in REFUSED_RUN_FILES):
                continue
            if rel.parts[0] == "workspace" and str(rel) == "workspace/progress":
                continue
            if query and query.lower() not in str(rel).lower():
                continue
            files.append({"path": str(rel), "size": p.stat().st_size})
            if len(files) >= 400:
                break
        return {"files": files}

    def read_file(self, run_id: str, path: str, offset: int = 0) -> dict[str, Any]:
        run = self.store.get(run_id)
        target = self.store.file(run, path)
        if target.suffix.lower() not in TEXT_SUFFIXES:
            raise ToolError("only text files are read")
        return _window(target, str(target.relative_to(run.path)), offset, self.limits.file_window_bytes)

    def search_messages(self, run_id: str, query: str, limit: int = 8) -> dict[str, Any]:
        run = self.store.get(run_id)
        terms = [t for t in re.findall(r"[a-z0-9_.]+", str(query).lower()) if len(t) > 1][:8]
        if not terms:
            raise ToolError("query needs at least one word")
        hits = []
        for e in self._events(run):
            if e.get("type") not in ("message", "tool", "status", "error", "stage", "artifact"):
                continue
            text = _event_text(e)
            low = text.lower()
            score = sum(low.count(t) for t in terms)
            if score:
                hits.append((score, e, text))
        hits.sort(key=lambda h: (-h[0], h[1].get("seq", 0)))
        rows = [
            {"seq": e.get("seq"), "type": e.get("type"), "ts": e.get("ts"), "text": _snippet(text, terms)}
            for _, e, text in hits[: _bound(limit, 1, self.limits.max_search_hits)]
        ]
        return {"hits": rows, "total_hits": len(hits)}

    def compare_runs(self, run_a: str, run_b: str) -> dict[str, Any]:
        def side(run_id: str) -> dict[str, Any]:
            facts = self.get_run(run_id)
            run = self.store.get(run_id)
            designs = designs_of(run, self._events(run))
            chosen = next((d for d in designs if d.get("chosen")), None)
            sized = [d for d in designs if _gate_count(d) is not None]
            return {
                "id": run_id,
                "status": facts["status"],
                "brief": _clip(facts["brief"], 160),
                "data": facts["data"],
                "designs": len(designs),
                "chosen_chip": facts["chosen_chip"],
                "chosen_gates": chosen.get("gates") if chosen else None,
                "chosen_scores": chosen.get("scores") if chosen else None,
                "smallest_gates": min((_gate_count(d) for d in sized), default=None),
                "stages": facts["stages"],
                "cost_usd": facts["cost_usd"],
            }

        return {"runs": [side(run_a), side(run_b)]}

    def product_facts(self, topic: str | None = None) -> dict[str, Any]:
        sections = product_sections()
        if topic:
            key = topic.strip().lower()
            match = {k: v for k, v in sections.items() if key in k}
            if match:
                return {"sections": match}
            return {"topics": sorted(sections), "note": f"no section {topic!r}"}
        return {"topics": sorted(sections)}


def product_sections() -> dict[str, str]:
    """The fact sheet, split on ``## `` headings: topic -> text."""
    text = FACTS_PATH.read_text(encoding="utf-8")
    out: dict[str, str] = {}
    for block in re.split(r"^## ", text, flags=re.M)[1:]:
        title, _, body = block.partition("\n")
        out[title.strip().lower()] = body.strip()
    return out


# ---------------------------------------------------------------- schemas

_RUN = {"type": "string", "description": "Run id from list_runs; the open run is in the view context."}


def function_tool(
    name: str, description: str, properties: dict[str, Any], required: list[str]
) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required},
        },
    }


TOOL_SCHEMAS: list[dict[str, Any]] = [
    function_tool("list_runs", "The runs on this server, newest first.", {"limit": {"type": "integer"}}, []),
    function_tool(
        "get_run",
        "One run's facts: status, brief, data kind, chosen chip, stage states, cost.",
        {"run_id": _RUN},
        ["run_id"],
    ),
    function_tool(
        "get_spec",
        "The run's spec (spec.json and spec.md): targets, constraints, data.",
        {"run_id": _RUN},
        ["run_id"],
    ),
    function_tool(
        "get_stages",
        "The seven stages: state, start, end, rounds, skip reason.",
        {"run_id": _RUN},
        ["run_id"],
    ),
    function_tool(
        "get_designs",
        "Every design of a run with gates, scores, verification and basis; names the smallest and chosen.",
        {"run_id": _RUN},
        ["run_id"],
    ),
    function_tool(
        "get_design",
        "One design in full: scores, per-patient results, targets, verification, chip files.",
        {"run_id": _RUN, "design_id": {"type": "string"}},
        ["run_id", "design_id"],
    ),
    function_tool(
        "get_chosen",
        "The run's chosen chip, its design and the run's final summary.",
        {"run_id": _RUN},
        ["run_id"],
    ),
    function_tool(
        "get_metrics",
        "Metric events, optionally for one design or a key fragment, each with its basis.",
        {"run_id": _RUN, "design_id": {"type": "string"}, "key": {"type": "string"}},
        ["run_id"],
    ),
    function_tool(
        "get_summaries",
        "The run's final summary, bullets and evidence summaries.",
        {"run_id": _RUN},
        ["run_id"],
    ),
    function_tool(
        "get_report",
        "A window of the run's report.md; page with offset = next_offset.",
        {"run_id": _RUN, "offset": {"type": "integer"}},
        ["run_id"],
    ),
    function_tool(
        "list_files",
        "The run's files as run-folder paths; 'query' filters by a name fragment.",
        {"run_id": _RUN, "query": {"type": "string"}},
        ["run_id"],
    ),
    function_tool(
        "read_file",
        "A window of one text file; 'path' exactly as list_files gave it. Page with next_offset.",
        {"run_id": _RUN, "path": {"type": "string"}, "offset": {"type": "integer"}},
        ["run_id", "path"],
    ),
    function_tool(
        "search_messages",
        "Ranked search over a run's messages, tool calls, status lines and stages.",
        {"run_id": _RUN, "query": {"type": "string"}, "limit": {"type": "integer"}},
        ["run_id", "query"],
    ),
    function_tool(
        "compare_runs",
        "Two runs side by side: chosen chip, its gates and scores, smallest design, stages, cost.",
        {"run_a": {"type": "string"}, "run_b": {"type": "string"}},
        ["run_a", "run_b"],
    ),
    function_tool(
        "product_facts",
        "ChipIn's own explanations. Topics: product, stages, marks (measured, estimate, simulated), "
        "tabs, flow, presets, checks, limits, chippy. No topic lists them.",
        {"topic": {"type": "string"}},
        [],
    ),
]

TOOL_NAMES = frozenset(t["function"]["name"] for t in TOOL_SCHEMAS)


def run_tool(tools: HelperTools, name: str, arguments: Any) -> Any:
    """Run one read tool and return its clipped result; ``ToolError`` for a bad call."""
    handler: Callable[..., Any] | None = getattr(tools, name, None) if name in TOOL_NAMES else None
    if handler is None:
        raise ToolError(f"unknown tool {name!r}")
    if not isinstance(arguments, dict):
        raise ToolError(f"{name}: arguments must be an object")
    try:
        result = handler(**arguments)
    except TypeError as exc:
        raise ToolError(f"{name}: bad arguments ({exc})") from exc
    except OSError as exc:
        raise ToolError(f"{name}: could not read ({type(exc).__name__})") from exc
    return clip_result(result, tools.limits)


# ---------------------------------------------------------------- bounds


def _bound(value: Any, low: int, high: int) -> int:
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return high


def _clip(value: Any, chars: int) -> Any:
    if isinstance(value, str) and len(value) > chars:
        return value[:chars] + "…"
    return value


def _event_text(e: dict[str, Any]) -> str:
    parts = [
        str(e.get(k))
        for k in ("text", "name", "tool", "title", "message", "summary", "path", "reason")
        if e.get(k)
    ]
    for k in ("input", "output", "args", "result"):
        if e.get(k) is not None:
            parts.append(json.dumps(e[k], ensure_ascii=False, default=str)[:2000])
    return " ".join(parts)


def _snippet(text: str, terms: list[str], width: int = 240) -> str:
    low = text.lower()
    at = min((low.find(t) for t in terms if t in low), default=0)
    start = max(0, at - width // 3)
    return ("…" if start else "") + text[start : start + width] + ("…" if start + width < len(text) else "")


def _window(target: Path, rel: str, offset: Any, window: int) -> dict[str, Any]:
    """Up to ``window`` bytes of ``target`` from ``offset``, cut at a line end when possible."""
    size = target.stat().st_size
    start = _bound(offset, 0, max(0, size))
    with target.open("rb") as handle:
        handle.seek(start)
        data = handle.read(window)
    if start + len(data) < size:
        if b"\n" in data:
            data = data[: data.rfind(b"\n") + 1]
        else:
            cut = len(data)
            while cut > 0 and (data[cut - 1] & 0xC0) == 0x80:
                cut -= 1
            if cut > 0 and data[cut - 1] >= 0xC0:
                cut -= 1
            data = data[:cut] or data
    end = start + len(data)
    out: dict[str, Any] = {
        "path": rel,
        "size": size,
        "offset": start,
        "text": data.decode("utf-8", "replace"),
    }
    if end < size:
        out["next_offset"] = end
    return out


def _json_len(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False, default=str).encode("utf-8"))


def _clip_strings(value: Any, chars: int) -> Any:
    if isinstance(value, str):
        return _clip(value, chars)
    if isinstance(value, list):
        return [_clip_strings(v, chars) for v in value]
    if isinstance(value, dict):
        return {k: _clip_strings(v, chars) for k, v in value.items()}
    return value


def clip_result(value: Any, limits: ToolLimits) -> Any:
    """Bound a result to ``max_result_bytes``: rows first, then long strings, then a marked prefix."""
    cap = limits.max_result_bytes
    if _json_len(value) <= cap:
        return value
    if isinstance(value, dict):
        for key in ("runs", "rows", "files", "hits", "designs", "per_patient"):
            rows = value.get(key)
            if isinstance(rows, list) and rows:
                kept = rows[: limits.max_rows]
                while kept and _json_len({**value, key: kept}) > cap:
                    kept = kept[: len(kept) - max(1, len(kept) // 4)]
                if len(kept) < len(rows):
                    value = {**value, key: kept, "truncated": True, "rows_total": len(rows)}
                if _json_len(value) <= cap:
                    return value
        if isinstance(value.get("text"), str):
            text = value["text"]
            while text and _json_len({**value, "text": text}) > cap:
                text = text[: int(len(text) * 0.8)]
            value = {**value, "text": text, "truncated": True}
            if _json_len(value) <= cap:
                return value
    clipped = _clip_strings(value, limits.max_string_chars)
    if _json_len(clipped) <= cap:
        return clipped
    text = json.dumps(clipped, ensure_ascii=False, default=str)
    keep = cap
    while keep > 0:
        out = {"truncated": True, "json_prefix": text[:keep]}
        if _json_len(out) <= cap:
            return out
        keep -= max(1, keep // 8)
    return {"truncated": True, "json_prefix": ""}


__all__ = [
    "TOOL_NAMES",
    "TOOL_SCHEMAS",
    "HelperTools",
    "RunFolder",
    "RunStore",
    "ToolError",
    "ToolLimits",
    "clip_result",
    "designs_of",
    "metric_basis",
    "product_sections",
    "run_tool",
    "stages_of",
]
