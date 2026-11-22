"""Fan-out: the run's agent orchestrates one batch of parallel subagents per stage.

Off unless a run asks for it. When on, the orchestrator runs each stage in
``BATCH_STAGES`` as one batch: it starts ``width`` subagents at once, each
trying a different strategy, waits for all of them and merges the best into
the stage's result. Its working folder gets a second helper, ``./subagent``,
next to ``./progress``::

    ./subagent start <stage> "<brief>" [--name <label>] [--agent <harness>] [--model <id>]
    ./subagent wait <id> [<id> ...] | --stage <stage> | --all [--timeout <seconds>]
    ./subagent merge <stage> --kept <id>[,<id> ...] --why "<one line>"
    ./subagent list

It follows the ``./progress`` pattern: the helper appends a request line to
the run's ``subagents.jsonl`` and reads ``subagents.json``, which
:class:`Fanout` (the backend) rewrites atomically. The backend, not the
helper, starts every subagent, through the same runner and agent backends
as the run's own agent, in ``workspace/agents/<id>/`` with its own
``./progress`` helper and instructions. Its bookkeeping (``progress.jsonl``,
``agent_events.jsonl``) is under ``subagents/<id>/`` in the run folder.

Every event a subagent causes lands in the run's own ``events.jsonl`` with
``"agent": "<id>"``; ``subagent.started`` and ``subagent.finished`` mark its
life, and ``stage.merged`` records a batch's merge. A subagent cannot start subagents: its environment carries
``CHIPIN_SUBAGENT_ID`` and both the helper and the backend refuse.
"""

from __future__ import annotations

import asyncio
import json
import stat
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

from chipin_backend.agents.types import AgentResult, AgentSpec, utc_now
from chipin_backend.api.config import ApiAgent, FanoutConfig
from chipin_backend.api.events import STAGES, EventLog
from chipin_backend.api.progress import PROGRESS_FILE, ProgressTailer, _interpreter, write_helper
from chipin_backend.api.translate import Translator, clip
from chipin_backend.compute.factory import runner_for
from chipin_backend.config import BackendConfig, Effort, RunMode
from chipin_backend.llm.keys import MissingKeyError
from chipin_backend.llm.presets import expand_preset
from chipin_backend.llm.providers import ProviderError, resolve_provider
from chipin_backend.runs import JsonlEventSink, RunDir

HELPER_NAME = "subagent"
REQUESTS_FILE = "subagents.jsonl"
STATE_FILE = "subagents.json"
#: Run-folder bookkeeping per subagent: ``subagents/<id>/``.
SUBAGENTS_DIR = "subagents"
#: Working folders, inside the orchestrator's: ``workspace/agents/<id>/``.
AGENTS_DIR = "agents"
#: Set in a subagent's environment; the helper refuses to run there.
ID_ENV = "CHIPIN_SUBAGENT_ID"
#: The subagent's last message, written into its folder when it ends.
RESULT_FILE = "subagent-result.md"
ORCHESTRATOR_PATH = Path(__file__).with_name("orchestrator.md")
SUBAGENT_PATH = Path(__file__).with_name("subagent.md")
TERMINAL = ("done", "failed", "timed out", "stopped")
#: The stages run as one batch of subagents each; spec and report are the orchestrator's.
BATCH_STAGES = ("reference", "propose", "finetune", "compile", "verify")
#: How many stage batches a run has; ``max_total`` defaults to this many batches.
BATCHES = len(BATCH_STAGES)
BRIEF_MAX = 8000
STRATEGY_MAX = 120
WHY_MAX = 300
NAME_MAX = 40
#: How long ``./subagent start`` waits for the backend's answer.
REPLY_S = 30
#: A subagent's result in ``subagents.json`` (the full text is in its folder).
RESULT_MAX = 6000

_HELPER = '''\
"""ChipIn subagent helper: start subagents that work in parallel, then wait for them.

usage:
  ./subagent start <stage> "<brief>" [--name <short label>] [--agent <__AGENTS__>] [--model <id or preset>]
  ./subagent wait <id> [<id> ...] [--timeout <seconds>]
  ./subagent wait --stage <stage> [--timeout <seconds>]
  ./subagent wait --all [--timeout <seconds>]
  ./subagent merge <stage> --kept <id>[,<id> ...] --why "<one line>"
  ./subagent list

start prints the new subagent's id and returns at once; the brief's first line
is its strategy. wait returns when the subagents have finished, or after
--timeout seconds (default __WAIT__); call it again for any still running.
merge records which results of the stage's batch you kept and why (--kept none
if none); it is refused while a subagent of that stage is still running.
Batch stages: __STAGES__.
"""
import json, os, sys, time, uuid
from datetime import datetime, timezone

REQUESTS = __REQUESTS__
STATE = __STATE__
STAGES = __STAGES_T__
AGENTS = __AGENTS_T__
WAIT_S = __WAIT__
REPLY_S = __REPLY__
BATCH = __BATCH_T__
TERMINAL = ("done", "failed", "timed out", "stopped")


def fail(msg, code=2):
    sys.stderr.write("subagent: " + msg + "\\n" + (__doc__ if code == 2 else ""))
    sys.exit(code)


def state():
    try:
        with open(STATE, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


def options(args, names):
    pos, out, i = [], {}, 0
    while i < len(args):
        arg = args[i]
        if arg.startswith("--") and len(arg) > 2:
            key = arg[2:]
            if key not in names:
                fail("unknown option " + arg)
            if names[key]:
                if i + 1 >= len(args):
                    fail(arg + " needs a value")
                out[key] = args[i + 1]
                i += 2
                continue
            out[key] = True
        else:
            pos.append(arg)
        i += 1
    return pos, out


def ask(line):
    req = uuid.uuid4().hex[:12]
    line.update({"ts": datetime.now(timezone.utc).isoformat(), "req": req})
    with open(REQUESTS, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(line) + "\\n")
    deadline = time.time() + REPLY_S
    while time.time() < deadline:
        reply = state().get("replies", {}).get(req)
        if reply:
            if not reply.get("ok"):
                fail(reply.get("error") or "refused", 1)
            return reply
        time.sleep(0.05)
    fail("no answer from the backend in %d s; the run may be ending" % REPLY_S, 1)


def show(sub):
    cost = sub.get("cost_usd")
    head = "== %s \\"%s\\" (%s, %s%s): %s" % (
        sub["id"], sub.get("name", ""), sub.get("stage", ""), sub.get("agent", ""),
        " " + sub["model"] if sub.get("model") else "", sub.get("state", "?"))
    if sub.get("seconds") is not None:
        head += " after %d s" % sub["seconds"]
    if cost is not None:
        head += ", $%.4f" % cost
    print(head)
    print("folder: " + sub.get("folder", ""))
    if sub.get("error"):
        print("error: " + sub["error"])
    if sub.get("state") in TERMINAL:
        print("result:\\n" + (sub.get("result") or "(no result text)"))
    print()


if os.environ.get("CHIPIN_SUBAGENT_ID"):
    fail("a subagent cannot start or wait for subagents; only the orchestrator can", 1)
a = sys.argv[1:]
if not a or a[0] in ("-h", "--help", "help"):
    fail("no command" if not a else "help")
cmd, rest = a[0], a[1:]
if cmd == "start":
    pos, opt = options(rest, {"name": True, "agent": True, "model": True})
    if len(pos) != 2:
        fail("start needs a stage and one quoted brief")
    if pos[0] not in STAGES:
        fail("unknown stage " + repr(pos[0]))
    if not pos[1].strip():
        fail("the brief is empty")
    if opt.get("agent") is not None and opt["agent"] not in AGENTS:
        fail("--agent must be one of " + ", ".join(AGENTS))
    line = {"cmd": "start", "stage": pos[0], "brief": pos[1]}
    line.update({k: opt[k] for k in ("name", "agent", "model") if k in opt})
    reply = ask(line)
    print(reply["id"])
    sys.stderr.write(reply.get("message", "") + "\\n")
elif cmd == "merge":
    pos, opt = options(rest, {"kept": True, "why": True})
    if len(pos) != 1 or pos[0] not in BATCH:
        fail("merge needs one batch stage: " + ", ".join(BATCH))
    if not opt.get("kept") or not str(opt.get("why", "")).strip():
        fail("merge needs --kept <id>[,<id> ...] (or none) and --why \\"<one line>\\"")
    kept = [] if opt["kept"].strip() == "none" else [k.strip() for k in opt["kept"].split(",") if k.strip()]
    reply = ask({"cmd": "merge", "stage": pos[0], "kept": kept, "why": opt["why"]})
    print(reply.get("message", "merged"))
elif cmd == "wait":
    pos, opt = options(rest, {"all": False, "stage": True, "timeout": True})
    try:
        timeout = float(opt.get("timeout", WAIT_S))
    except ValueError:
        fail("--timeout must be a number of seconds")
    if timeout <= 0:
        fail("--timeout must be above 0")
    agents = state().get("agents", {})
    if sum(1 for x in (pos, opt.get("all"), opt.get("stage")) if x) > 1:
        fail("give subagent ids, --stage or --all, only one of them")
    if opt.get("stage"):
        ids = [i for i, s in agents.items() if s.get("stage") == opt["stage"]]
    else:
        ids = list(agents) if opt.get("all") else pos
    if not ids:
        fail("no subagents to wait for" if opt.get("all") or opt.get("stage")
             else "wait needs subagent ids, --stage or --all", 1)
    unknown = [i for i in ids if i not in agents]
    if unknown:
        fail("unknown subagent " + ", ".join(unknown) + "; ./subagent list shows them", 1)
    began = beat = time.time()
    while True:
        agents = state().get("agents", agents)
        running = [i for i in ids if agents.get(i, {}).get("state") not in TERMINAL]
        if not running or time.time() - began >= timeout:
            break
        if time.time() - beat >= 20:
            print("still waiting for " + ", ".join(running) + " (%d s)" % (time.time() - began), flush=True)
            beat = time.time()
        time.sleep(0.5)
    for i in ids:
        show(agents[i])
    if running:
        print("Still running: %s. Call ./subagent wait %s again." % (", ".join(running), " ".join(running)))
    else:
        print("All %d finished." % len(ids))
elif cmd == "list":
    if rest:
        fail("list takes no arguments")
    current = state()
    agents = current.get("agents", {})
    for sub in agents.values():
        print("%-4s %-9s %-9s %-24s %s" % (sub["id"], sub.get("state", "?"), sub.get("stage", ""),
                                         sub.get("name", ""), sub.get("folder", "")))
    if not agents:
        print("no subagents yet")
    for merge in current.get("merges", []):
        print("merged %s: kept %s of %s (%s)" % (merge["stage"], ", ".join(merge["kept"]) or "none",
                                                 ", ".join(merge["ids"]), merge["why"]))
    limits = current.get("limits")
    if limits:
        print("limits: " + ", ".join("%s %s" % (k, v) for k, v in limits.items()))
else:
    fail("unknown command " + repr(cmd))
'''


def write_subagent_helper(workspace: Path, run_path: Path, *, wait_s: int, agents: tuple[str, ...]) -> Path:
    """Write the executable ``subagent`` helper into ``workspace``; returns its path."""
    values = {
        "__REQUESTS__": repr(str(run_path / REQUESTS_FILE)),
        "__STATE__": repr(str(run_path / STATE_FILE)),
        "__STAGES_T__": repr(STAGES),
        "__BATCH_T__": repr(BATCH_STAGES),
        "__STAGES__": ", ".join(BATCH_STAGES),
        "__AGENTS_T__": repr(agents),
        "__AGENTS__": "|".join(agents),
        "__WAIT__": str(int(wait_s)),
        "__REPLY__": str(REPLY_S),
    }
    source = _HELPER
    for token, value in values.items():
        source = source.replace(token, value)
    helper = workspace / HELPER_NAME
    helper.write_text(f"#!{_interpreter()}\n{source}", encoding="utf-8")
    helper.chmod(helper.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return helper


@dataclass(frozen=True)
class _SubagentDir(RunDir):
    """``subagents/<id>/`` in the run folder; the runner sends the agent's events to ``sink``."""

    sink: Translator | None = field(default=None, compare=False)

    def event_sink(self) -> Translator:  # type: ignore[override]
        """The subagent's translator (it stores the raw events too)."""
        assert self.sink is not None
        return self.sink


@dataclass(frozen=True)
class FanoutPlan:
    """One run's fan-out settings, resolved from the config and the request."""

    width: int
    max_parallel: int
    max_total: int
    max_usd: float
    wait_timeout_s: int
    timeout_s: int
    agent: ApiAgent
    model: str | None = None
    provider: str | None = None
    effort: Effort | None = None
    #: What the orchestrator runs on (harness, model), for the views.
    orchestrator: dict[str, Any] = field(default_factory=dict)
    #: A subagent's model per harness when a start names none.
    automatic: dict[str, str | None] = field(default_factory=dict)

    def view(self) -> dict[str, Any]:
        """The plan as JSON for ``api.json`` and ``GET /api/runs/{id}``."""
        view = {
            "width": self.width,
            "stages": list(BATCH_STAGES),
            "max_parallel": self.max_parallel,
            "max_total": self.max_total,
            "max_usd": self.max_usd,
            "orchestrator": self.orchestrator,
            "subagent": {"agent": self.agent, "model": self.model, "effort": self.effort},
            "timeout_s": self.timeout_s,
        }
        if self.provider:
            view["subagent"]["provider"] = self.provider
        return view


@dataclass(frozen=True)
class Orchestrator:
    """What the run's own agent runs on."""

    agent: ApiAgent
    model: str | None = None
    provider: str | None = None
    effort: Effort | None = None


def default_model(agent: str, config: BackendConfig) -> str | None:
    """The model a harness runs when nobody names one."""
    if agent == "claude":
        return config.agents.claude_cli.model
    if agent == "openrouter":
        return config.agents.openrouter.model
    return None


def plan_fanout(
    raw: Any,
    cfg: FanoutConfig,
    *,
    orchestrator: Orchestrator,
    preset: str | None,
    config: BackendConfig,
    agents: Mapping[str, str],
) -> FanoutPlan | None:
    """The run's :class:`FanoutPlan`, or ``None`` when fan-out is off.

    ``raw`` is the request's ``fanout`` value: absent (the config decides),
    a bool, or ``{"enabled", "width", "max_usd", "subagent": {"agent",
    "model", "provider", "effort"}}``; any field but ``enabled`` turns it on.
    The batch size is the preset's unless the request or the config names
    one; every limit the config leaves ``null`` follows from it. A request's
    ``max_usd`` may only lower the config's. ``ValueError`` for anything
    invalid, a missing key included (by name only).
    """
    if raw is None:
        raw = {}
    elif isinstance(raw, bool):
        raw = {"enabled": raw}
    if not isinstance(raw, dict):
        raise ValueError("fanout must be an object or true/false")
    unknown = set(raw) - {"enabled", "width", "max_usd", "subagent"}
    if unknown:
        raise ValueError(f"unknown fanout fields: {sorted(unknown)}")
    enabled = raw.get("enabled", True if set(raw) - {"enabled"} else cfg.enabled)
    if not isinstance(enabled, bool):
        raise ValueError("fanout.enabled must be true or false")
    if not enabled:
        return None
    biggest = max([*cfg.widths.values(), cfg.default_width, cfg.width or 0])
    width = raw.get("width", cfg.width)
    if width is None:
        width = cfg.widths.get(preset, cfg.default_width) if preset else cfg.default_width  # type: ignore[call-overload]
    if isinstance(width, bool) or not isinstance(width, int) or not 1 <= width <= biggest:
        raise ValueError(f"fanout.width must be a whole number from 1 to {biggest}")
    spare = cfg.spare_starts if cfg.spare_starts is not None else max(2, -(-width // 5))
    max_total = cfg.max_total or BATCHES * width + spare
    max_usd = cfg.max_usd if cfg.max_usd is not None else round(cfg.usd_per_subagent * max_total, 2)
    if "max_usd" in raw:
        asked = raw["max_usd"]
        if isinstance(asked, bool) or not isinstance(asked, int | float) or not 0 <= asked <= max_usd:
            raise ValueError(f"fanout.max_usd must be a number from 0 to {max_usd}")
        max_usd = float(asked)
    timeout_s = cfg.subagent.timeout_s or (
        cfg.subagent.timeouts.get(preset, cfg.subagent.default_timeout_s)  # type: ignore[call-overload]
        if preset
        else cfg.subagent.default_timeout_s
    )
    sub = raw.get("subagent") or {}
    if not isinstance(sub, dict) or set(sub) - {"agent", "model", "provider", "effort"}:
        raise ValueError("fanout.subagent takes agent, model, provider and effort")
    agent = sub.get("agent") or cfg.subagent.agent or orchestrator.agent
    same = agent == orchestrator.agent
    model, provider = choose_model(
        agent,
        sub.get("model") or automatic_model(agent, cfg, orchestrator),
        sub.get("provider") or cfg.subagent.provider or (orchestrator.provider if same else None),
        config=config,
        agents=agents,
    )
    effort = sub.get("effort") or cfg.subagent.effort or orchestrator.effort
    if effort is not None and effort not in ("low", "medium", "high", "xhigh", "max"):
        raise ValueError("fanout.subagent.effort must be low, medium, high, xhigh or max")
    return FanoutPlan(
        width=width,
        # A whole batch runs at once; a start beyond max_parallel waits in a queue.
        max_parallel=cfg.max_parallel or width,
        max_total=max_total,
        max_usd=max_usd,
        wait_timeout_s=cfg.wait_timeout_s,
        timeout_s=timeout_s,
        agent=agent,
        model=model,
        provider=provider,
        effort=effort,
        orchestrator={
            "agent": orchestrator.agent,
            "model": orchestrator.model or default_model(orchestrator.agent, config),
            "effort": orchestrator.effort,
        },
        automatic={name: automatic_model(name, cfg, orchestrator) for name in agents},
    )


def automatic_model(agent: str, cfg: FanoutConfig, orchestrator: Orchestrator) -> str | None:
    """A subagent's model when the request names none.

    ``claude``: ``fanout.subagent.model`` (the smaller Claude model; the
    orchestrator runs the larger). ``openrouter``: ``fanout.subagent.openrouter_model``,
    else the orchestrator's model when it runs on openrouter too, else the
    harness default. ``stub``: none.
    """
    if agent == "claude":
        return cfg.subagent.model
    if agent == "openrouter":
        return cfg.subagent.openrouter_model or (orchestrator.model if orchestrator.agent == agent else None)
    return None


def choose_model(
    agent: str, model: str | None, provider: str | None, *, config: BackendConfig, agents: Mapping[str, str]
) -> tuple[str | None, str | None]:
    """``(model, provider)`` for a subagent on ``agent``; ``ValueError`` if it cannot run.

    The openrouter harness needs its provider's key in the environment (checked
    by name); its model may be a preset such as ``inkling-mini``.
    """
    if agent not in agents:
        raise ValueError(f"the subagent harness must be one of {sorted(agents)}")
    for value, what in ((model, "model"), (provider, "provider")):
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise ValueError(f"the subagent {what} must be a non-empty string")
    if agent != "openrouter":
        if provider is not None:
            raise ValueError("a provider needs the openrouter harness")
        return model, None
    try:
        chosen = resolve_provider(config.providers, provider)
        chosen.api_key()
        # The model it will really run: a preset expanded, else the provider's default.
        resolved = chosen.model_for(
            expand_preset(model, chosen.name, config.llm.presets), fallback=config.agents.openrouter.model
        )
    except (ProviderError, MissingKeyError) as exc:
        raise ValueError(str(exc)) from None
    return resolved, chosen.name


def orchestrator_instructions(plan: FanoutPlan) -> str:
    """The paragraph added to the standing instructions when fan-out is on."""
    text = ORCHESTRATOR_PATH.read_text(encoding="utf-8")
    for token, value in {
        "{width}": str(plan.width),
        "{wait_s}": str(plan.wait_timeout_s),
        "{max_total}": str(plan.max_total),
        "{timeout_min}": str(max(1, round(plan.timeout_s / 60))),
        "{subagent}": f"the {plan.agent} harness"
        + (f" with the model {plan.model}" if plan.model else "")
        + (f" at {plan.effort} effort" if plan.effort else ""),
    }.items():
        text = text.replace(token, value)
    return text


def subagent_instructions(chiplab: str | None) -> str:
    """A subagent's standing instructions, with the chip-lab paragraph when the lab is on."""
    text = SUBAGENT_PATH.read_text(encoding="utf-8")
    return f"{text.rstrip()}\n\n{chiplab}" if chiplab else text


class TaggedLog:
    """Writes into a run's :class:`EventLog` with ``"agent": <id>`` on every event."""

    def __init__(self, log: EventLog, agent_id: str) -> None:
        self.log = log
        self.agent_id = agent_id
        self.run_id = log.run_id

    def append(self, type_: str, **fields: Any) -> dict[str, Any] | None:
        """:meth:`EventLog.append` with the subagent's id added."""
        return self.log.append(type_, **fields, agent=self.agent_id)


@dataclass
class Subagent:
    """One subagent of a run, live or finished."""

    id: str
    name: str
    stage: str
    brief: str
    agent: str
    model: str | None
    provider: str | None
    state: str = "queued"
    created_at: str = field(default_factory=utc_now)
    started_at: str | None = None
    finished_at: str | None = None
    seconds: float | None = None
    cost: dict[str, Any] | None = None
    result: str = ""
    error: str | None = None
    task: asyncio.Task[None] | None = None
    #: ``time.monotonic()`` at the start and the end, for a batch's span.
    t_start: float | None = None
    t_end: float | None = None

    @property
    def strategy(self) -> str:
        """The brief's first line: the one strategy this subagent tries."""
        first = next((line.strip() for line in self.brief.splitlines() if line.strip()), "")
        return clip(first.lstrip("#").strip(), STRATEGY_MAX)

    @property
    def cost_usd(self) -> float | None:
        """What it cost, as its harness reported it."""
        return float(self.cost["usd"]) if self.cost and self.cost.get("usd") is not None else None

    def view(self) -> dict[str, Any]:
        """The subagent as JSON (``subagents.json``, ``run.json``, the API)."""
        view: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "stage": self.stage,
            "agent": self.agent,
            "model": self.model,
            "state": self.state,
            "folder": f"{AGENTS_DIR}/{self.id}",
            "path": f"workspace/{AGENTS_DIR}/{self.id}",
            "strategy": self.strategy,
            "brief": clip(self.brief, 300),
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "seconds": round(self.seconds) if self.seconds is not None else None,
            "cost_usd": self.cost_usd,
            "tokens_in": (self.cost or {}).get("tokens_in"),
            "tokens_out": (self.cost or {}).get("tokens_out"),
            "result": self.result[:RESULT_MAX] if self.result else None,
            "error": self.error,
        }
        if self.provider:
            view["provider"] = self.provider
        return {k: v for k, v in view.items() if v is not None}


class Fanout:
    """The subagents of one run: reads requests, enforces limits, runs subagents, records merges.

    ``max_parallel`` subagents (by default the batch size) run at once; a
    start beyond it is accepted and queued until one finishes. ``max_total`` and the API-model spending cap
    ``max_usd`` refuse further starts. :meth:`close` stops every subagent still
    running or queued (a run that ends or is stopped takes its subagents with it).
    """

    def __init__(
        self,
        plan: FanoutPlan,
        *,
        run: RunDir,
        log: EventLog,
        config: BackendConfig,
        mode: RunMode,
        backends: Mapping[str, str],
        instructions: str,
        stub_env: Mapping[str, str] | None = None,
        on_change: Callable[[], None] | None = None,
    ) -> None:
        self.plan = plan
        self.run = run
        self.log = log
        self.config = config
        self.mode = mode
        self.backends = backends
        self.instructions = instructions
        self.stub_env = dict(stub_env or {})
        self.on_change = on_change
        self.subagents: dict[str, Subagent] = {}
        self.replies: dict[str, dict[str, Any]] = {}
        #: Every merge record, in order, as its ``stage.merged`` event says.
        self.merges: list[dict[str, Any]] = []
        self.closed = False
        self._offset = 0
        self.requests_path = run.path / REQUESTS_FILE
        self.state_path = run.path / STATE_FILE

    # ---- setup ----

    def install(self) -> None:
        """Write ``./subagent`` into the orchestrator's folder, its ``./progress`` anew, and the state file.

        The orchestrator's ``./progress`` passes a subagent's call to the
        subagent's own helper: a lab tool a subagent runs from the
        orchestrator's folder finds that helper in its working folder.
        """
        write_helper(self.run.workspace, self.run.path / PROGRESS_FILE, orchestrator=True)
        write_subagent_helper(
            self.run.workspace, self.run.path, wait_s=self.plan.wait_timeout_s, agents=tuple(self.backends)
        )
        self._save()

    # ---- requests ----

    async def follow(self, poll_s: float) -> None:
        """Answer new requests every ``poll_s`` until cancelled."""
        while True:
            self.drain()
            await asyncio.sleep(poll_s)

    def drain(self) -> None:
        """Answer every complete new request line; a partial last line waits."""
        try:
            with self.requests_path.open("rb") as handle:
                handle.seek(self._offset)
                chunk = handle.read()
        except FileNotFoundError:
            return
        except OSError as exc:
            logger.warning("run {}: cannot read {}: {}", self.log.run_id, self.requests_path, exc)
            return
        end = chunk.rfind(b"\n")
        if end < 0:
            return
        self._offset += end + 1
        changed = False
        for raw in chunk[: end + 1].splitlines():
            if not raw.strip():
                continue
            try:
                request = json.loads(raw)
                if not isinstance(request, dict) or not isinstance(request.get("req"), str):
                    raise ValueError("not a request object")
            except ValueError as exc:
                logger.warning(
                    "run {}: bad subagent request skipped ({}): {!r}", self.log.run_id, exc, raw[:200]
                )
                continue
            self.replies[request["req"]] = self._answer(request)
            changed = True
        if changed:
            self._save()

    def _answer(self, request: dict[str, Any]) -> dict[str, Any]:
        try:
            if request.get("cmd") == "merge":
                return {"ok": True, "message": self._merge(request)}
            sub = self._accept(request)
        except ValueError as exc:
            logger.info("run {}: subagent {} refused: {}", self.log.run_id, request.get("cmd"), exc)
            return {"ok": False, "error": str(exc)}
        running = self._running()
        if len(running) < self.plan.max_parallel:
            self._launch(sub)
            message = f"{sub.id} started ({sub.stage}, {sub.agent}{' ' + sub.model if sub.model else ''})"
        else:
            message = (
                f"{sub.id} queued: {len(running)} subagents are running (at most "
                f"{self.plan.max_parallel} at once); it starts when one finishes"
            )
        return {"ok": True, "id": sub.id, "state": sub.state, "message": message}

    def _accept(self, request: dict[str, Any]) -> Subagent:
        """A new queued :class:`Subagent` for a start request; ``ValueError`` says why not."""
        if request.get("cmd") != "start":
            raise ValueError(f"unknown request {request.get('cmd')!r}")
        if self.closed:
            raise ValueError("the run is ending; no new subagents")
        stage, brief = request.get("stage"), request.get("brief")
        if stage not in STAGES:
            raise ValueError(f"unknown stage {stage!r}")
        if not isinstance(brief, str) or not brief.strip():
            raise ValueError("the brief is empty")
        if len(brief) > BRIEF_MAX:
            raise ValueError(f"the brief is longer than {BRIEF_MAX} characters; point to a file instead")
        if len(self.subagents) >= self.plan.max_total:
            raise ValueError(
                f"this run has started its limit of {self.plan.max_total} subagents; "
                "carry on with the results you have"
            )
        agent = request.get("agent") or self.plan.agent
        if request.get("agent") or request.get("model"):
            same = agent == self.plan.agent
            model, provider = choose_model(
                agent,
                request.get("model") or (self.plan.model if same else self.plan.automatic.get(agent)),
                self.plan.provider if same else None,
                config=self.config,
                agents=self.backends,
            )
        else:
            model, provider = self.plan.model, self.plan.provider
        if agent == "openrouter":
            spent = self.api_spend()
            if spent >= self.plan.max_usd:
                self.log.append(
                    "status", text=f"ChipIn reached the subagent spending limit (${self.plan.max_usd:.2f})"
                )
                raise ValueError(
                    f"the subagents' spending limit for this run (${self.plan.max_usd:.2f}) is reached "
                    f"(${spent:.4f} spent); no more subagents on API models; carry on yourself"
                )
        number = len(self.subagents) + 1
        name = clip(str(request.get("name") or f"{stage}-{number}"), NAME_MAX)
        sub = Subagent(
            id=f"a{number}",
            name=name,
            stage=stage,
            brief=brief.strip(),
            agent=agent,
            model=model,
            provider=provider,
        )
        self.subagents[sub.id] = sub
        return sub

    def _merge(self, request: dict[str, Any]) -> str:
        """Record a batch's merge as one ``stage.merged`` event; ``ValueError`` says why not."""
        stage, kept, why = request.get("stage"), request.get("kept"), request.get("why")
        if stage not in BATCH_STAGES:
            raise ValueError(f"merge takes a batch stage ({', '.join(BATCH_STAGES)}), not {stage!r}")
        if not isinstance(kept, list) or not all(isinstance(k, str) for k in kept):
            raise ValueError("kept must be a list of subagent ids")
        if not isinstance(why, str) or not why.strip():
            raise ValueError("say in one line why: --why")
        # A batch is the stage's subagents not merged yet: a retry batch after a merge is merged on its own.
        merged = {i for m in self.merges if m["stage"] == stage for i in m["ids"]}
        batch = [s for s in self.subagents.values() if s.stage == stage and s.id not in merged]
        if not batch:
            if merged:
                raise ValueError(f"the {stage} batch is already merged; start a retry batch to merge again")
            raise ValueError(f"no subagents were started for {stage}; start the batch first")
        busy = [s.id for s in batch if s.state not in TERMINAL]
        if busy:
            raise ValueError(
                f"{', '.join(busy)} of the {stage} batch still running; "
                f"wait for them first (./subagent wait --stage {stage})"
            )
        ids = [s.id for s in batch]
        stray = [k for k in kept if k not in ids]
        if stray:
            raise ValueError(f"{', '.join(stray)} not in the {stage} batch ({', '.join(ids)})")
        first = min((s.t_start for s in batch if s.t_start is not None), default=None)
        last = max((s.t_end for s in batch if s.t_end is not None), default=None)
        record = {
            "stage": stage,
            "started": len(batch),
            "ids": ids,
            "done": sum(1 for s in batch if s.state == "done"),
            "kept": kept,
            "why": clip(why.strip(), WHY_MAX),
            "seconds": round(last - first, 1) if first is not None and last is not None else 0.0,
        }
        self.merges.append(record)
        self.log.append("stage.merged", **record)
        logger.info("run {}: {} batch merged, kept {}", self.log.run_id, stage, kept or "none")
        return f"{stage} merged: kept {', '.join(kept) or 'none'} of {len(batch)}"

    # ---- running ----

    def _running(self) -> list[Subagent]:
        return [s for s in self.subagents.values() if s.state == "running"]

    def _launch(self, sub: Subagent) -> None:
        sub.state = "running"
        sub.started_at = utc_now()
        sub.t_start = time.monotonic()
        sub.task = asyncio.create_task(self._run(sub), name=f"subagent-{self.run.run_id}-{sub.id}")

    def _pump(self) -> None:
        """Start queued subagents while there is room."""
        if self.closed:
            return
        for sub in self.subagents.values():
            if sub.state == "queued" and len(self._running()) < self.plan.max_parallel:
                self._launch(sub)

    def display_model(self, sub: Subagent) -> str | None:
        """The model a subagent really runs on, for events and views."""
        if sub.model:
            return sub.model
        if sub.agent == "claude":
            return self.config.agents.claude_cli.model
        if sub.agent == "openrouter":
            return self.config.agents.openrouter.model
        return None

    async def _run(self, sub: Subagent) -> None:
        """Run one subagent to its end; never raises except for cancellation."""
        started = time.monotonic()
        folder = self.run.workspace / AGENTS_DIR / sub.id
        meta = self.run.path / SUBAGENTS_DIR / sub.id
        folder.mkdir(parents=True, exist_ok=True)
        meta.mkdir(parents=True, exist_ok=True)
        write_helper(folder, meta / "progress.jsonl", subagent=True)
        (folder / "brief.md").write_text(f"# Brief from the orchestrator\n\n{sub.brief}\n", encoding="utf-8")
        tagged = TaggedLog(self.log, sub.id)
        translator = Translator(
            tagged,  # type: ignore[arg-type]
            JsonlEventSink(meta / "agent_events.jsonl"),
            folder,
            start_status=None,
            errors=False,
        )
        tailer = ProgressTailer(meta / "progress.jsonl", tagged, self.run.path, folder, marks=False)  # type: ignore[arg-type]
        follow = asyncio.create_task(tailer.follow(0.5))
        self.log.append(
            "subagent.started",
            id=sub.id,
            name=sub.name,
            stage=sub.stage,
            strategy=sub.strategy,
            harness=sub.agent,
            model=self.display_model(sub),
            brief=clip(sub.brief, 200),
        )
        self._save()
        spec = AgentSpec(
            name=f"subagent-{sub.id}",
            prompts=[self._first_prompt(sub)],
            backend=self.backends[sub.agent],  # type: ignore[arg-type]
            model=sub.model,
            provider=sub.provider,
            effort=self.plan.effort,
            system_prompt=self.instructions,
            workdir=folder,
            timeout_s=self.plan.timeout_s,
            env={ID_ENV: sub.id, **(self.stub_env if sub.agent == "stub" else {})},
        )
        runner = runner_for(self.config, self.mode)
        result: AgentResult | None = None
        try:
            result = await runner.run(spec, _SubagentDir(meta, sink=translator))
            if not result.failed:
                sub.state = "done"
            elif (result.error or "").startswith("timed out after"):
                sub.state = "timed out"
            else:
                sub.state = "failed"
            sub.error = clip(result.error, 300) if result.failed and result.error else None
        except asyncio.CancelledError:
            sub.state = "stopped"
            sub.error = "stopped because the run ended or was stopped"
            raise
        except Exception as exc:
            logger.exception("run {}: subagent {} failed in the runner", self.log.run_id, sub.id)
            sub.state = "failed"
            sub.error = clip(f"{type(exc).__name__}: {exc}", 300)
        finally:
            await runner.close()
            follow.cancel()
            tailer.drain()
            sub.t_end = time.monotonic()
            sub.seconds = sub.t_end - started
            sub.finished_at = utc_now()
            sub.cost = translator.cost
            sub.result = translator.last_text or (result.final_text if result else "") or ""
            if sub.error is None and translator.error_text and sub.state != "done":
                sub.error = clip(translator.error_text, 300)
            self._finished(sub, folder)

    def _finished(self, sub: Subagent, folder: Path) -> None:
        try:
            (folder / RESULT_FILE).write_text(sub.result or "(no result text)\n", encoding="utf-8")
        except OSError as exc:
            logger.warning("run {}: {} not written for {}: {}", self.log.run_id, RESULT_FILE, sub.id, exc)
        self.log.append(
            "subagent.finished",
            id=sub.id,
            stage=sub.stage,
            state=sub.state,
            seconds=round(sub.seconds or 0.0, 1),
            cost=sub.cost_usd,
            result=clip(sub.result, 300) if sub.result else None,
            error=sub.error,
        )
        logger.info("run {}: subagent {} {} in {:.0f}s", self.log.run_id, sub.id, sub.state, sub.seconds or 0)
        self._pump()
        self._save()

    def _first_prompt(self, sub: Subagent) -> str:
        # Absolute folders: some harnesses' file tools take absolute paths only.
        mine = (self.run.workspace / AGENTS_DIR / sub.id).resolve()
        theirs = self.run.workspace.resolve()
        minutes = max(1, round(self.plan.timeout_s / 60))
        return (
            f'You are subagent {sub.id} ("{sub.name}") of a ChipIn run, one of the batch trying '
            f"different strategies for its {sub.stage} stage at once; your strategy is the brief's "
            "first line. "
            f"Your working folder is {mine} ; the orchestrator's folder is {theirs} (../.. from yours), "
            "and paths in the brief are relative to it unless they say otherwise. The brief is also in "
            "brief.md:\n\n"
            f"{sub.brief}\n\n"
            f"Do exactly that strategy within {minutes} minutes, report each number with "
            "./progress metric ... --chip <design_id>, and end with the short result the brief asks for."
        )

    # ---- totals and shutdown ----

    def api_spend(self) -> float:
        """What the subagents on API models (the openrouter harness) have cost so far."""
        return sum(s.cost_usd or 0.0 for s in self.subagents.values() if s.agent == "openrouter")

    def cost(self) -> dict[str, Any]:
        """The subagents' summed cost: ``usd``, ``tokens_in``, ``tokens_out``."""
        total: dict[str, Any] = {"usd": 0.0, "tokens_in": 0, "tokens_out": 0}
        for sub in self.subagents.values():
            for key in total:
                total[key] += (sub.cost or {}).get(key) or 0
        return total

    def views(self) -> list[dict[str, Any]]:
        """Every subagent as JSON, in the order they were started."""
        return [s.view() for s in self.subagents.values()]

    async def close(self) -> None:
        """Refuse new starts, stop every subagent still queued or running, and wait for them."""
        self.drain()
        self.closed = True
        for sub in self.subagents.values():
            if sub.state == "queued":
                sub.state = "stopped"
                sub.error = "never started: the run ended first"
                self.log.append(
                    "subagent.finished",
                    id=sub.id,
                    stage=sub.stage,
                    state="stopped",
                    seconds=0.0,
                    error=sub.error,
                )
        live = [s.task for s in self.subagents.values() if s.task is not None and not s.task.done()]
        for task in live:
            task.cancel()
        if live:
            await asyncio.gather(*live, return_exceptions=True)
        self._save()

    def _save(self) -> None:
        """Rewrite ``subagents.json`` atomically and tell the owner."""
        state = {
            "agents": {s.id: s.view() for s in self.subagents.values()},
            "merges": self.merges,
            "replies": self.replies,
            "limits": {
                "width": self.plan.width,
                "max_parallel": self.plan.max_parallel,
                "max_total": self.plan.max_total,
                "max_usd": self.plan.max_usd,
                "timeout_s": self.plan.timeout_s,
            },
        }
        tmp = self.state_path.with_suffix(".json.tmp")
        try:
            tmp.write_text(json.dumps(state, indent=1, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.state_path)
        except OSError as exc:
            logger.error("run {}: {} not written: {}", self.log.run_id, self.state_path.name, exc)
        if self.on_change is not None:
            try:
                self.on_change()
            except (OSError, ValueError, TypeError) as exc:
                logger.warning("run {}: subagent record not updated: {}", self.log.run_id, exc)


__all__ = [
    "AGENTS_DIR",
    "BATCH_STAGES",
    "HELPER_NAME",
    "ID_ENV",
    "REQUESTS_FILE",
    "RESULT_FILE",
    "STATE_FILE",
    "SUBAGENTS_DIR",
    "Fanout",
    "FanoutPlan",
    "Orchestrator",
    "Subagent",
    "TaggedLog",
    "choose_model",
    "orchestrator_instructions",
    "plan_fanout",
    "subagent_instructions",
    "write_subagent_helper",
]
