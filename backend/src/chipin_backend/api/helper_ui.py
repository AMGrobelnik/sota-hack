"""What Chippy may do to the page: view actions, proposals, and example prompts.

The server never acts on the interface. A view action (go to a route, open a
run, switch tab, select a design, set the playback time, open a file, start a
new spec with a brief, highlight an element) is validated here against the
run folders and streamed to the page as an ``action`` item, which the page
carries out. Anything that changes more than the view (start a run, send a
message to the running agent, stop a run) is only a ``proposal``: the page
shows it as a button, and nothing happens unless the user presses it. The
request the button would send is part of the proposal, so the page needs no
second lookup; this module never sends it.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from chipin_backend.api.helper_tools import HelperTools, ToolError, function_tool
from chipin_backend.runs import is_safe_run_id

#: Run page tabs: route key -> label on the page (i1.html ``VIEWS``).
TABS: dict[str, str] = {
    "overview": "Overview",
    "patients": "Where it fails",
    "signal": "Signal",
    "chip": "Chip",
    "chat": "Chat",
    "sources": "Sources",
}
FLOW_STEPS: dict[str, str] = {
    "1": "The device",
    "2": "Who and where",
    "3": "Targets",
    "4": "Constraints",
    "5": "Data",
    "spec": "Your spec",
}
PRESETS = ("lite", "pro", "max", "ultra")
#: Elements Chippy may highlight, by their id on the page, with what each is.
ELEMENTS: dict[str, str] = {
    "prompt": "the brief box on the start page",
    "go": "the Chip in button on the start page",
    "pAg": "the agent and model pill on the start page",
    "gfH": "the heading of the current guided-flow step",
    "tgts": "the run's targets on the Overview",
    "tchart": "the trade-off chart (chip size against a metric) on the Overview",
    "ysel": "the metric picker above the trade-off chart",
    "legend": "the chart legend",
    "insp": "the selected-design panel on the Overview",
    "alog": "the decision path, replayed, beside the chart",
    "tiles": "the stage tiles on the Overview",
    "clk": "the run clock",
    "trk": "the playback track",
    "pbtn": "the play and pause button",
    "chipK": "the chip card on the Chip tab",
    "sigc": "the signal drawing on the Signal tab",
    "feed": "the message feed on the Chat tab",
    "msgs": "the recorded messages on the Chat tab",
    "sendN": "the send button for a note or message",
    "nopass": "the note shown when no design clears every target",
}
_TAB_ALIASES = {label.lower(): key for key, label in TABS.items()} | {
    "where it fails": "patients",
    "fails": "patients",
    "the chip": "chip",
}
_ROUTE_RE = re.compile(r"^#/(?:|new/(?:[1-5]|spec)|configure|run/([A-Za-z0-9._-]{1,128})/([a-z]+))$")
MAX_BRIEF_CHARS = 2000
MAX_MESSAGE_CHARS = 4000


# ---------------------------------------------------------------- view context


@dataclass
class ViewContext:
    """What the user is looking at, as the page reports it (all optional)."""

    route: str = ""
    page: str = "start"
    run_id: str | None = None
    tab: str | None = None
    design_id: str | None = None
    playback_s: float | None = None
    flow_step: str | None = None
    spec_draft: dict[str, Any] | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def for_prompt(self) -> dict[str, Any]:
        out: dict[str, Any] = {"page": self.page, "route": self.route}
        for key in ("run_id", "tab", "design_id", "playback_s", "flow_step", "spec_draft"):
            value = getattr(self, key)
            if value not in (None, "", {}):
                out[key] = value
        if self.tab:
            out["tab_label"] = TABS.get(self.tab, self.tab)
        if self.flow_step:
            out["flow_step_label"] = FLOW_STEPS.get(self.flow_step, self.flow_step)
        return out


def _text(value: Any, chars: int) -> str | None:
    return value.strip()[:chars] or None if isinstance(value, str) else None


def parse_view(raw: Any, max_draft_bytes: int = 4000) -> ViewContext:
    """A :class:`ViewContext` from the page's object; unknown or malformed fields are dropped."""
    if not isinstance(raw, dict):
        return ViewContext()
    view = ViewContext(route=_text(raw.get("route"), 300) or "")
    match = _ROUTE_RE.match(view.route)
    if view.route.startswith("#/new"):
        view.page = "new"
    elif view.route.startswith("#/configure"):
        view.page = "configure"
    elif match and match.group(1):
        view.page = "run"
        view.run_id, view.tab = match.group(1), match.group(2)
    run_id = _text(raw.get("run_id"), 128)
    if run_id and is_safe_run_id(run_id):
        view.run_id = run_id
        if view.page == "start" and not view.route:
            view.page = "run"
    tab = _text(raw.get("tab"), 40)
    if tab:
        view.tab = _TAB_ALIASES.get(tab.lower(), tab.lower())
    if view.tab not in TABS:
        view.tab = "overview" if view.page == "run" else None
    view.design_id = _text(raw.get("design_id") or raw.get("selected_design"), 64)
    playback = raw.get("playback_s", raw.get("playback_time"))
    if isinstance(playback, int | float) and not isinstance(playback, bool) and playback >= 0:
        view.playback_s = round(float(playback), 2)
    step = raw.get("flow_step")
    step = str(step) if isinstance(step, int | str) else None
    if step in FLOW_STEPS:
        view.flow_step = step
        view.page = "new"
    elif view.page == "new":
        tail = view.route.rsplit("/", 1)[-1]
        view.flow_step = tail if tail in FLOW_STEPS else None
    draft = raw.get("spec_draft")
    if isinstance(draft, dict):
        encoded = json.dumps(draft, ensure_ascii=False, default=str)
        view.spec_draft = (
            draft if len(encoded.encode()) <= max_draft_bytes else {"truncated": encoded[:max_draft_bytes]}
        )
    return view


# ---------------------------------------------------------------- actions and proposals

_RUN = {"type": "string", "description": "Run id; defaults to the open run."}

ACTION_SCHEMAS: list[dict[str, Any]] = [
    function_tool(
        "ui_go_to",
        "Move the page to a route: #/ (start), #/new/1 to #/new/5 and #/new/spec (guided flow), "
        "#/configure, #/run/<run_id>/<tab>.",
        {"route": {"type": "string"}},
        ["route"],
    ),
    function_tool(
        "ui_open_run",
        "Open a run, on a tab (default overview).",
        {"run_id": _RUN, "tab": {"type": "string"}},
        ["run_id"],
    ),
    function_tool(
        "ui_switch_tab",
        "Switch the run page's tab: overview, patients (Where it fails), signal, chip, chat, sources.",
        {"tab": {"type": "string"}, "run_id": _RUN},
        ["tab"],
    ),
    function_tool(
        "ui_select_design",
        "Select one design of a run on the page.",
        {"design_id": {"type": "string"}, "run_id": _RUN},
        ["design_id"],
    ),
    function_tool(
        "ui_set_playback",
        "Move the run's playback clock to this many seconds after the run started.",
        {"seconds": {"type": "number"}, "run_id": _RUN},
        ["seconds"],
    ),
    function_tool(
        "ui_open_file",
        "Open one of the run's workspace files on the page.",
        {"path": {"type": "string"}, "run_id": _RUN},
        ["path"],
    ),
    function_tool(
        "ui_new_spec",
        "Open the guided flow at step 1 with this brief filled in; the user goes on and starts the run.",
        {"brief": {"type": "string"}},
        ["brief"],
    ),
    function_tool(
        "ui_highlight",
        "Point at one element of the page by its id: "
        + ", ".join(f"{k} ({v})" for k, v in ELEMENTS.items())
        + ".",
        {"element_id": {"type": "string"}},
        ["element_id"],
    ),
]
PROPOSAL_SCHEMAS: list[dict[str, Any]] = [
    function_tool(
        "propose_start_run",
        "Offer a button that starts a new run with this brief. Nothing starts unless the user presses it.",
        {"brief": {"type": "string"}, "preset": {"type": "string", "enum": list(PRESETS)}},
        ["brief"],
    ),
    function_tool(
        "propose_message_agent",
        "Offer a button that sends this message to the RUNNING run's agent. Only for a run in progress.",
        {"text": {"type": "string"}, "run_id": _RUN},
        ["text"],
    ),
    function_tool("propose_stop_run", "Offer a button that stops a RUNNING run.", {"run_id": _RUN}, []),
]
ACTION_NAMES = frozenset(t["function"]["name"] for t in ACTION_SCHEMAS)
PROPOSAL_NAMES = frozenset(t["function"]["name"] for t in PROPOSAL_SCHEMAS)


class UiActions:
    """Validates Chippy's interface calls and turns them into page items."""

    def __init__(self, tools: HelperTools, view: ViewContext) -> None:
        self.tools = tools
        self.view = view
        self.count = 0

    def _run_id(self, run_id: Any) -> str:
        rid = run_id if isinstance(run_id, str) and run_id else self.view.run_id
        if not rid:
            raise ToolError("no run is open; pass run_id")
        self.tools.store.get(rid)
        return rid

    def _next_id(self, prefix: str) -> str:
        self.count += 1
        return f"{prefix}{self.count}"

    def _tab(self, tab: Any) -> str:
        key = _TAB_ALIASES.get(str(tab).strip().lower(), str(tab).strip().lower())
        if key not in TABS:
            raise ToolError(f"unknown tab {tab!r}; tabs are {', '.join(TABS)}")
        return key

    def handle(self, name: str, args: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        """``(page item, result for the model)``; ``ToolError`` when the call is not valid."""
        if not isinstance(args, dict):
            raise ToolError(f"{name}: arguments must be an object")
        try:
            if name in ACTION_NAMES:
                item = getattr(self, "_" + name.removeprefix("ui_"))(**args)
                item = {"type": "action", "id": self._next_id("a"), **item}
                self._follow(item)
                return item, {"ok": True, "done_on_page": item["kind"], "route": item.get("route")}
            if name in PROPOSAL_NAMES:
                item = getattr(self, "_" + name)(**args)
                item = {"type": "proposal", "id": self._next_id("p"), "executed": False, **item}
                note = "shown to the user as a button; nothing happens unless they press it"
                return item, {"ok": True, "proposed": item["kind"], "note": note}
        except TypeError as exc:
            raise ToolError(f"{name}: bad arguments ({exc})") from exc
        raise ToolError(f"unknown tool {name!r}")

    def _follow(self, item: dict[str, Any]) -> None:
        """Track where earlier actions of this turn left the page, so later ones build on it."""
        design = item.get("design_id") or self.view.design_id
        if item.get("route"):
            self.view = parse_view({"route": item["route"], "design_id": design})
        elif design:
            self.view.design_id = design

    # -- view actions

    def _go_to(self, route: str) -> dict[str, Any]:
        match = _ROUTE_RE.match(str(route).strip())
        if not match:
            raise ToolError("route must be #/, #/new/1..5, #/new/spec, #/configure or #/run/<id>/<tab>")
        if match.group(1):
            self.tools.store.get(match.group(1))
            self._tab(match.group(2))
        return {"kind": "go_to", "route": str(route).strip()}

    def _open_run(self, run_id: str, tab: str = "overview") -> dict[str, Any]:
        rid, key = self._run_id(run_id), self._tab(tab or "overview")
        return {"kind": "open_run", "run_id": rid, "tab": key, "route": f"#/run/{rid}/{key}"}

    def _switch_tab(self, tab: str, run_id: str | None = None) -> dict[str, Any]:
        rid, key = self._run_id(run_id), self._tab(tab)
        return {
            "kind": "switch_tab",
            "run_id": rid,
            "tab": key,
            "label": TABS[key],
            "route": f"#/run/{rid}/{key}",
        }

    def _select_design(self, design_id: str, run_id: str | None = None) -> dict[str, Any]:
        rid = self._run_id(run_id)
        ids = [d["id"] for d in self.tools.get_designs(rid)["designs"]]
        if design_id not in ids:
            raise ToolError(
                f"run {rid} has no design {design_id!r}; its designs are {', '.join(ids) or 'none'}"
            )
        tab = self.view.tab if self.view.run_id == rid and self.view.tab else "overview"
        return {"kind": "select_design", "run_id": rid, "design_id": design_id, "route": f"#/run/{rid}/{tab}"}

    def _set_playback(self, seconds: float, run_id: str | None = None) -> dict[str, Any]:
        rid = self._run_id(run_id)
        if not isinstance(seconds, int | float) or isinstance(seconds, bool) or seconds < 0:
            raise ToolError("seconds must be a number of seconds, 0 or more")
        return {"kind": "set_playback", "run_id": rid, "seconds": round(float(seconds), 2)}

    def _open_file(self, path: str, run_id: str | None = None) -> dict[str, Any]:
        rid = self._run_id(run_id)
        run = self.tools.store.get(rid)
        target = self.tools.store.file(run, path)
        rel = str(target.relative_to(run.path))
        if not rel.startswith("workspace/"):
            raise ToolError("the page opens workspace files only")
        return {"kind": "open_file", "run_id": rid, "path": rel}

    def _new_spec(self, brief: str) -> dict[str, Any]:
        text = str(brief).strip()
        if not text:
            raise ToolError("brief is empty")
        return {"kind": "new_spec", "brief": text[:MAX_BRIEF_CHARS], "route": "#/new/1"}

    def _highlight(self, element_id: str) -> dict[str, Any]:
        if element_id not in ELEMENTS:
            raise ToolError(f"unknown element {element_id!r}; ids are {', '.join(ELEMENTS)}")
        return {"kind": "highlight", "element_id": element_id, "label": ELEMENTS[element_id]}

    # -- proposals: described, never sent

    def _running(self, rid: str) -> None:
        status = self.tools.get_run(rid).get("status")
        if status != "running":
            raise ToolError(f"run {rid} is {status or 'not running'}; only a running run takes this")

    def _propose_start_run(self, brief: str, preset: str = "lite") -> dict[str, Any]:
        text = str(brief).strip()[:MAX_BRIEF_CHARS]
        if not text:
            raise ToolError("brief is empty")
        if preset not in PRESETS:
            raise ToolError(f"preset must be one of {', '.join(PRESETS)}")
        body = {"prompt": text, "preset": preset}
        return {
            "kind": "start_run",
            "label": f"Start a {preset.title()} run",
            "request": {"method": "POST", "path": "/api/runs", "body": body},
        }

    def _propose_message_agent(self, text: str, run_id: str | None = None) -> dict[str, Any]:
        rid = self._run_id(run_id)
        self._running(rid)
        message = str(text).strip()[:MAX_MESSAGE_CHARS]
        if not message:
            raise ToolError("text is empty")
        return {
            "kind": "message_agent",
            "run_id": rid,
            "label": "Send this to the agent",
            "request": {"method": "POST", "path": f"/api/runs/{rid}/messages", "body": {"text": message}},
        }

    def _propose_stop_run(self, run_id: str | None = None) -> dict[str, Any]:
        rid = self._run_id(run_id)
        self._running(rid)
        return {
            "kind": "stop_run",
            "run_id": rid,
            "label": "Stop this run",
            "request": {"method": "POST", "path": f"/api/runs/{rid}/stop", "body": {}},
        }


# ---------------------------------------------------------------- example prompts


def _s(sid: str, label: str, prompt: str) -> dict[str, str]:
    return {"id": sid, "label": label, "prompt": prompt}


_FLOW_PROMPTS: dict[str, dict[str, str]] = {
    "1": _s(
        "flow-device",
        "What does this step set?",
        "What does step 1 of the guided flow, The device, set in my spec?",
    ),
    "2": _s(
        "flow-where",
        "Why ask where it is used?",
        "Why does the guided flow ask where the device is used and who responds?",
    ),
    "3": _s(
        "flow-targets",
        "Which targets fit?",
        "Which performance targets does ChipIn use for each kind of task?",
    ),
    "4": _s(
        "flow-constraints",
        "What do constraints change?",
        "What do the sensor, battery and reuse questions set in my spec?",
    ),
    "5": _s(
        "flow-data",
        "Which data to use?",
        "What are the data options, and how are results on simulated data marked?",
    ),
    "spec": _s(
        "flow-spec",
        "Is my spec complete?",
        "Look at my spec draft: what is set, and what is still a default?",
    ),
}


def suggestions(tools: HelperTools, view: ViewContext, limit: int = 4) -> list[dict[str, str]]:
    """A few example prompts for this view and run state, each answerable from the data."""
    marks = _s(
        "marks", "Measured or estimated?", "What do measured, estimated and simulated mean on this page?"
    )
    if view.page == "new":
        picks = [_FLOW_PROMPTS.get(view.flow_step or "1", _FLOW_PROMPTS["1"])]
        picks.append(_s("stages", "What happens on Run?", "What are the seven stages a run goes through?"))
        picks.append(_s("presets", "Which run size?", "What do the presets Lite, Pro, Max and Ultra change?"))
        return picks[:limit]
    if view.page == "configure":
        return [
            _s("presets", "Which preset?", "What do the presets Lite, Pro, Max and Ultra change?"),
            _s("agents", "Which agent and model?", "Which agents and models can drive a run?"),
        ]
    if view.page == "run" and view.run_id:
        try:
            facts = tools.get_run(view.run_id)
            designs = tools.get_designs(view.run_id)
        except ToolError:
            return suggestions(tools, ViewContext(), limit)
        rid, picks = view.run_id, []
        target = view.design_id or designs.get("chosen") or designs.get("smallest_by_gates")
        if view.tab == "patients" and target:
            picks.append(
                _s(
                    "fails",
                    "Where does it fail?",
                    f"Where does design {target} fail in run {rid}: which patient is worst?",
                )
            )
        if view.design_id:
            picks.append(
                _s(
                    "design",
                    "Explain this design",
                    f"What does design {view.design_id} measure in run {rid}, and does it clear the targets?",
                )
            )
            picks.append(
                _s("design-chip", "Open its chip", f"Open the Chip tab for design {view.design_id}.")
            )
        if facts.get("status") == "running":
            picks.append(
                _s(
                    "now",
                    "What is it doing now?",
                    f"Which stage is run {rid} in, and what has it found so far?",
                )
            )
            picks.append(
                _s(
                    "so-far",
                    "Any designs yet?",
                    f"Which designs has run {rid} produced so far, and how big are they?",
                )
            )
        else:
            if facts.get("chosen_chip"):
                picks.append(_s("chosen", "Why this chip?", f"Which chip did run {rid} choose, and why?"))
            if designs.get("smallest_by_gates"):
                picks.append(
                    _s(
                        "smallest",
                        "Smallest design?",
                        f"Which design in run {rid} is smallest, and what does it catch?",
                    )
                )
            picks.append(
                _s(
                    "skipped",
                    "What was skipped?",
                    f"Which stages of run {rid} were skipped or failed, and why?",
                )
            )
        picks.append(marks)
        seen: set[str] = set()
        unique = [p for p in picks if not (p["id"] in seen or seen.add(p["id"]))]
        return unique[:limit]
    picks = [_s("what", "What does ChipIn do?", "What does ChipIn do, in two sentences?")]
    finished = [r for r in tools.list_runs(limit=20)["runs"] if r.get("status") not in ("running", None)]
    if finished:
        picks.append(
            _s(
                "latest",
                "Open the latest run",
                f"Open run {finished[0]['id']} and tell me which chip it chose.",
            )
        )
    picks.append(_s("stages", "How does a run work?", "What are the seven stages a run goes through?"))
    picks.append(marks)
    return picks[:limit]


__all__ = [
    "ACTION_NAMES",
    "ACTION_SCHEMAS",
    "ELEMENTS",
    "FLOW_STEPS",
    "PROPOSAL_NAMES",
    "PROPOSAL_SCHEMAS",
    "TABS",
    "UiActions",
    "ViewContext",
    "parse_view",
    "suggestions",
]
