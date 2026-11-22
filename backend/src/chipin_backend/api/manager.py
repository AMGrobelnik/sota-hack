"""Starts, tracks and stops dashboard runs; each one is a backend run folder.

A dashboard run is an ordinary backend run (``run.json``, ``workspace/``)
started through the backend's own runner, plus:

    api.json            # the dashboard's view: prompt, status, times, summary, cost
    events.jsonl        # contract events (seq from 1), replayable
    agent_events.jsonl  # the backend's raw AgentEvents
    progress.jsonl      # what the agent reported through ./progress
    evidence.json/.md   # number check, weight bytes, stage timings (see evidence.py)
    workspace/brief.md  # the user's brief, answers and attached-file list
    workspace/progress  # the progress helper

Run defaults: the Claude agent backend (``claude_cli``) and the local
runner. "Local" in the contract is this Mac, which the backend calls the
``flex`` run mode (a Mac the team owns, nothing rented); it runs the agent in
this process on the logged-in Claude CLI. RunPod (``on_demand``) is not
offered by this server.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Literal

from loguru import logger

from chipin_backend.agents.types import AgentResult, AgentSpec, EventSink, utc_now
from chipin_backend.api.config import ApiConfig, Preset
from chipin_backend.api.events import API_EVENTS_FILE, EventLog, public_text
from chipin_backend.api.progress import PROGRESS_FILE, ProgressTailer, write_helper
from chipin_backend.api.scripted import NAME as SCRIPTED
from chipin_backend.api.scripted import STEP_ENV, register
from chipin_backend.api.steer import SteerError, Steering, send_message, watch
from chipin_backend.api.steer import shutdown as close_steering
from chipin_backend.api.translate import Translator, clip
from chipin_backend.chiplab import chiplab_available, chiplab_instructions
from chipin_backend.compute.base import Runner
from chipin_backend.config import BackendConfig, RunMode
from chipin_backend.evidence import emit_evidence
from chipin_backend.llm.keys import MissingKeyError
from chipin_backend.llm.presets import expand_preset
from chipin_backend.llm.providers import ProviderError, resolve_provider
from chipin_backend.orchestrate import run_agent
from chipin_backend.runs import JsonlEventSink, RunDir, is_safe_run_id, new_run_id
from chipin_backend.training import train_available, training_instructions

API_RECORD_FILE = "api.json"
RAW_EVENTS_FILE = "agent_events.jsonl"
INSTRUCTIONS_PATH = Path(__file__).with_name("instructions.md")

ApiAgent = Literal["claude", "stub", "openrouter"]
ApiRunner = Literal["local"]
ApiStatus = Literal["running", "succeeded", "failed", "stopped"]
#: Contract agent name -> backend registry name.
AGENT_BACKENDS: dict[str, str] = {"claude": "claude_cli", "stub": SCRIPTED, "openrouter": "openrouter"}
#: Contract runner name -> backend run mode.
RUNNER_MODES: dict[str, RunMode] = {"local": "flex"}
#: ``machine`` values from the dashboard that mean this Mac.
LOCAL_MACHINES = frozenset({"", "local", "flex", "mac", "this-mac"})
#: ``machine`` values that mean a rented pod, which this server never starts.
REMOTE_MACHINES = frozenset({"on_demand", "on-demand", "ondemand", "runpod", "cloud", "gpu"})


class RequestError(ValueError):
    """A bad request; ``status`` is the HTTP status to answer with."""

    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class ApiRunDir(RunDir):
    """A run folder whose agent events go through a :class:`Translator`.

    The raw events are stored in ``agent_events.jsonl`` (the backend's
    ``events_path``); ``events.jsonl`` holds the contract events.
    """

    sink: EventSink | None = field(default=None, compare=False)

    @property
    def events_path(self) -> Path:
        """``agent_events.jsonl``: the backend's raw events."""
        return self.path / RAW_EVENTS_FILE

    def event_sink(self) -> EventSink:  # type: ignore[override]
        """The translating sink (raw events are stored by it too)."""
        return self.sink if self.sink is not None else super().event_sink()


@dataclass
class ApiRun:
    """One dashboard run, live or finished."""

    run: RunDir
    record: dict[str, Any]
    log: EventLog
    runner: Runner | None = None
    task: asyncio.Task[None] | None = None
    inner: asyncio.Task[AgentResult] | None = None
    stopping: bool = False
    stop_reason: str = "stopped by the user"
    steer: Steering | None = None  # messages to the agent (api/steer.py)

    @property
    def id(self) -> str:
        """The run id (folder name)."""
        return self.run.run_id

    def summary_view(self) -> dict[str, Any]:
        """The run object of ``GET /api/runs``."""
        keys = ("id", "prompt", "status", "started_at", "finished_at")
        return {k: self.record[k] for k in keys if self.record.get(k) is not None}

    def detail_view(self) -> dict[str, Any]:
        """The run object of ``GET /api/runs/{id}``."""
        view = self.summary_view()
        for key in ("summary", "bullets", "cost"):
            if self.record.get(key) is not None:
                view[key] = self.record[key]
        return view

    def save(self) -> None:
        """Write ``api.json`` atomically; its summary names paths relative to the run folder."""
        if isinstance(self.record.get("summary"), str):
            self.record["summary"] = public_text(self.record["summary"], self.run.path)
        path = self.run.path / API_RECORD_FILE
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.record, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)


class RunManager:
    """Every run under ``config.runs_dir`` that the dashboard started."""

    def __init__(
        self,
        config: BackendConfig,
        api: ApiConfig,
        *,
        agent: ApiAgent = "claude",
        runner: ApiRunner = "local",
        summary: bool = True,
    ) -> None:
        register()
        self.config = config
        self.api = api
        self.agent = agent
        self.runner = runner
        self.runs: dict[str, ApiRun] = {}
        self.summary = summary
        self.instructions = standing_instructions()

    @property
    def runs_dir(self) -> Path:
        """Where run folders live."""
        return self.config.resolved_runs_dir()

    def load(self) -> None:
        """Index earlier dashboard runs; one left ``running`` by a dead server is closed as failed."""
        loop = asyncio.get_running_loop()
        if not self.runs_dir.is_dir():
            return
        for record_path in sorted(self.runs_dir.glob(f"*/{API_RECORD_FILE}")):
            folder = record_path.parent
            try:
                record = json.loads(record_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning("skipping run {}: unreadable {}: {}", folder.name, API_RECORD_FILE, exc)
                continue
            item = ApiRun(RunDir(folder), record, EventLog(folder / API_EVENTS_FILE, folder.name, loop))
            if record.get("status") == "running":
                message = "the server stopped while this run was in progress"
                item.log.append("error", message=message)
                item.log.append("run.finished", status="failed", summary=message)
                record.update(status="failed", finished_at=utc_now(), summary=message)
                item.save()
                _close_record(item.run, message)
            self.runs[item.id] = item
        logger.info("indexed {} earlier runs in {}", len(self.runs), self.runs_dir)

    def get(self, run_id: str) -> ApiRun:
        """The run ``run_id``; ``RequestError(404)`` if unknown."""
        item = self.runs.get(run_id) if is_safe_run_id(run_id) else None
        if item is None:
            raise RequestError(f"no run {run_id!r}", status=404)
        return item

    def listing(self) -> list[dict[str, Any]]:
        """Every run, newest first."""
        items = sorted(self.runs.values(), key=lambda r: (r.record.get("started_at", ""), r.id), reverse=True)
        return [r.summary_view() for r in items]

    def running(self) -> list[ApiRun]:
        """Runs still in progress."""
        return [r for r in self.runs.values() if r.task is not None and not r.task.done()]

    # ---- start ----

    def start(self, body: dict[str, Any]) -> ApiRun:
        """Validate a ``POST /api/runs`` body, make the run folder and start the agent."""
        prompt, preset, machine, answers, files = _validate(body, self.api)
        provider, model = self._provider_choice(body)
        if len(self.running()) >= self.config.compute.max_concurrent_agents:
            raise RequestError("too many runs in progress; stop one first", status=429)
        run = ApiRunDir.create(self.runs_dir, new_run_id())
        loop = asyncio.get_running_loop()
        log = EventLog(run.path / API_EVENTS_FILE, run.run_id, loop)
        translator = Translator(log, JsonlEventSink(run.events_path), run.workspace)
        steering = Steering()
        run = replace(run, sink=steering.sink(translator, log))
        write_helper(run.workspace, run.path / PROGRESS_FILE)
        (run.workspace / "brief.md").write_text(_brief(prompt, answers, files), encoding="utf-8")
        record: dict[str, Any] = {
            "id": run.run_id,
            "prompt": prompt,
            "status": "running",
            "started_at": utc_now(),
            "agent": self.agent,
            "runner": self.runner,
            "preset": preset,
            "machine": machine,
        }
        if self.agent == "openrouter":
            record["provider"] = provider
            record["model"] = model
        item = ApiRun(run, record, log)
        item.save()
        spec = AgentSpec(
            name="chipin",
            prompts=[_first_prompt(prompt)],
            backend=AGENT_BACKENDS[self.agent],  # type: ignore[arg-type]
            model=model,
            provider=provider,
            effort=self.api.presets[preset] if preset else None,
            system_prompt=self.instructions,
            timeout_s=self.api.run_timeout_s,
            env={STEP_ENV: str(self.api.stub_step_s)} if self.agent == "stub" else {},
        )
        log.append("run.started", prompt=prompt, agent=self.agent, runner=self.runner)
        self.runs[item.id] = item
        steering.attach(item, spec)
        item.task = asyncio.create_task(self._drive(item, spec, translator), name=f"run-{item.id}")
        watch(self, item)
        logger.info("run {} started: agent={} runner={} preset={}", item.id, self.agent, self.runner, preset)
        return item

    def _provider_choice(self, body: dict[str, Any]) -> tuple[str | None, str | None]:
        """The body's ``provider`` and ``model``, checked before a run folder is made.

        Only the ``openrouter`` agent takes a provider; an unknown or unconfigured one,
        or one whose key is not set, is a 400 that names the problem (never a key).
        """
        provider, model = body.get("provider"), body.get("model")
        if provider is None and model is None:
            return None, None
        if not all(v is None or (isinstance(v, str) and v.strip()) for v in (provider, model)):
            raise RequestError("provider and model must be non-empty strings")
        if self.agent != "openrouter":
            raise RequestError("provider and model need the server started with --agent openrouter")
        try:
            chosen = resolve_provider(self.config.providers, provider)
            chosen.api_key()
            chosen.model_for(model, fallback=self.config.agents.openrouter.model)
        except (ProviderError, MissingKeyError) as exc:
            raise RequestError(str(exc)) from None
        return chosen.name, expand_preset(model, chosen.name, self.config.llm.presets)

    async def _drive(self, item: ApiRun, spec: AgentSpec, translator: Translator) -> None:
        """Run the agent through :func:`run_agent`; always ends the event log with ``run.finished``.

        ``run_agent`` owns ``run.json`` (status, timings, costs, ``stopped`` on
        cancellation) and closes the runner; this adds the dashboard's view.
        """
        tailer = ProgressTailer(item.run.path / PROGRESS_FILE, item.log, item.run.path, item.run.workspace)
        follow = asyncio.create_task(tailer.follow(self.api.progress_poll_s))
        status: ApiStatus = "failed"
        summary: str | None = None
        bullets: str | None = None
        result: AgentResult | None = None

        def keep_runner(runner: Runner) -> None:
            item.runner = runner

        try:
            if item.stopping:
                raise asyncio.CancelledError
            item.inner = asyncio.create_task(
                run_agent(
                    spec,
                    self.config,
                    run_mode=RUNNER_MODES[self.runner],
                    run=item.run,
                    on_runner=keep_runner,
                    summary=self.summary,
                )
            )
            _, result = await item.inner
            status = "failed" if result.failed else "succeeded"
            # The agent's last message, not final_text: claude_cli joins every turn's text there.
            summary = clip(result.error or translator.last_text or result.final_text, 600) or None
            bullets = _bullets(result)
            if result.failed and not translator.error_emitted:
                item.log.append("error", message=result.error or "the agent failed")
        except asyncio.CancelledError:
            if not item.stopping:
                raise
            status, summary = "stopped", item.stop_reason
        except Exception as exc:
            logger.exception("run {} failed in the runner", item.id)
            summary = f"{type(exc).__name__}: {exc}"
            item.log.append("error", message=summary)
        finally:
            follow.cancel()
            tailer.drain()
            item.runner = None
            for rel in result.files if result else []:
                if rel.lower() in {"report.md", "report.html"}:
                    self._artifact(tailer, rel, "report")
            cost = translator.cost
            emit_evidence(item.run.path, item.log.append)
            item.log.append("run.finished", status=status, summary=summary, bullets=bullets)
            item.record.update(
                status=status, finished_at=utc_now(), summary=summary, bullets=bullets, cost=cost
            )
            item.save()
            logger.info("run {} {}", item.id, status)

    @staticmethod
    def _artifact(tailer: ProgressTailer, rel: str, kind: str) -> None:
        try:
            tailer.add_artifact(rel, kind)
        except ValueError as exc:
            logger.warning("artifact {} skipped: {}", rel, exc)

    # ---- control ----

    async def message(self, run_id: str, text: str) -> dict[str, Any]:
        """A user message to the run's agent: live while it runs, a follow-up after (api/steer.py)."""
        try:
            return await send_message(self, run_id, text)
        except SteerError as exc:
            raise RequestError(str(exc), exc.status) from None

    async def stop(self, run_id: str, reason: str = "stopped by the user") -> ApiRun:
        """Ask a running agent to stop; a finished run is left as it is."""
        item = self.get(run_id)
        if item.task is not None and not item.task.done() and not item.stopping:
            item.stopping = True
            item.stop_reason = reason
            item.log.append("status", text="ChipIn is stopping")
            if item.inner is not None:
                item.inner.cancel()
        return item

    async def shutdown(self) -> None:
        """Stop every running agent and wait for its ``run.finished``."""
        live = self.running()
        for item in live:
            await self.stop(item.id, "stopped because the server on this Mac was shut down")
        if live:
            await asyncio.gather(*(i.task for i in live if i.task), return_exceptions=True)
        close_steering()
        for item in self.runs.values():
            item.log.wake()


def standing_instructions(source: Mapping[str, str] | None = None) -> str:
    """The agent's standing instructions, plus the training and chip-lab paragraphs when each is on."""
    text = INSTRUCTIONS_PATH.read_text(encoding="utf-8")
    if train_available(source):
        text = f"{text.rstrip()}\n\n{training_instructions()}"
    if chiplab_available(source):
        text = f"{text.rstrip()}\n\n{chiplab_instructions()}"
    return text


def _bullets(result: AgentResult) -> str | None:
    """The three-bullet OpenRouter run summary, if one was written."""
    run_summary = (result.summary or {}).get("run") or {}
    return run_summary.get("text") or None


def _close_record(run: RunDir, message: str) -> None:
    """Mark a ``run.json`` left ``running`` by a dead server as failed."""
    try:
        if run.record_path.is_file() and run.read_record().status == "running":
            run.update_record(status="failed", error=message, finished_at=utc_now())
    except (OSError, ValueError, TypeError) as exc:
        logger.warning("run {}: could not close {}: {}", run.run_id, run.record_path.name, exc)


def _validate(
    body: dict[str, Any], api: ApiConfig
) -> tuple[str, Preset | None, str, dict[str, Any], list[dict[str, Any]]]:
    if not isinstance(body, dict):
        raise RequestError("the body must be a JSON object")
    prompt = body.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise RequestError("prompt must be a non-empty string")
    preset = body.get("preset")
    if preset is not None and preset not in api.presets:
        raise RequestError(f"preset must be one of {sorted(api.presets)}")
    machine = str(body.get("machine") or "").strip().lower()
    if machine in REMOTE_MACHINES:
        raise RequestError(
            "this local server runs agents on this Mac only; on-demand machines are not offered"
        )
    answers = body.get("answers") or {}
    if not isinstance(answers, dict):
        raise RequestError("answers must be an object")
    files = body.get("files") or []
    if not isinstance(files, list) or not all(isinstance(f, dict) and f.get("name") for f in files):
        raise RequestError("files must be a list of objects with a name")
    return prompt.strip(), preset, machine or "local", answers, files


def _brief(prompt: str, answers: dict[str, Any], files: list[dict[str, Any]]) -> str:
    """``brief.md``: what the user gave, and plainly what did not arrive."""
    parts = ["# Brief\n", prompt.strip(), ""]
    if answers:
        parts += ["## Answers to follow-up questions\n"]
        parts += [f"- {k}: {json.dumps(v, ensure_ascii=False)}" for k, v in answers.items()]
        parts.append("")
    if files:
        parts += [
            "## Files the user attached\n",
            "Only these names, sizes and header lines reached this run; the file",
            "contents were NOT uploaded.\n",
        ]
        for f in files:
            header = f" header: {clip(str(f['header']), 1000)}" if f.get("header") else ""
            parts.append(f"- {f.get('name')} ({f.get('size', '?')} bytes){header}")
        parts.append("")
    return "\n".join(parts)


def _first_prompt(prompt: str) -> str:
    return (
        "A new ChipIn run. The user's brief is in brief.md in your working folder; here it is too:\n\n"
        f"{prompt.strip()}\n\n"
        "Follow your instructions: work through the stages, report each one with ./progress, "
        "and finish with report.md."
    )


__all__ = [
    "AGENT_BACKENDS",
    "API_RECORD_FILE",
    "INSTRUCTIONS_PATH",
    "RUNNER_MODES",
    "ApiAgent",
    "ApiRun",
    "ApiRunDir",
    "ApiRunner",
    "RequestError",
    "RunManager",
    "standing_instructions",
]
