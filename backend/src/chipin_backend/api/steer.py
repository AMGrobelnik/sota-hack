"""Talking to a run's agent: a message during the run, a follow-up after it.

``POST /api/runs/{id}/messages`` with ``{"text"}``:

* The message is recorded at once as a ``message`` event with ``role`` "user"
  and a ``message_id`` ("m1", "m2", ...).
* While the run works it goes to the running agent (the orchestrator; never a
  helper it started) without stopping it: :meth:`AgentBackend.inject`. When
  the backend reports that the model has it, a ``status`` event "Your message
  reached the agent" with the same ``message_id`` follows. Several messages go
  in the order sent. A message that cannot reach the agent now (it is
  between its last turn and the end of the run) waits and goes as a follow-up.
* After the run ended (succeeded or stopped) the message is a follow-up: the
  same backend session continues in the same folder (``AgentSpec.
  resume_session``), the run goes back to ``running`` and ends with a new
  ``run.finished``; the ``cost`` event and the run's cost are the totals so
  far. The delivery status comes when the agent starts answering.
* A follow-up whose agent cannot be started (after the backend's own retries)
  ends with an ``error`` event and a ``run.finished`` that puts the run back
  as it was (``succeeded`` or ``stopped``): the run is not failed, and the
  next message tries again, carrying the unanswered ones with it.
* A failed run takes no messages (409); text is limited to
  :data:`MAX_MESSAGE_CHARS` characters (413).
"""

from __future__ import annotations

import asyncio
import contextlib
from collections import deque
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any

from loguru import logger

from chipin_backend.agents.types import AgentEvent, AgentResult, AgentSpec, utc_now
from chipin_backend.api.events import EventLog
from chipin_backend.api.progress import PROGRESS_FILE, ProgressTailer
from chipin_backend.api.scripted import STEP_ENV
from chipin_backend.api.translate import Translator, clip
from chipin_backend.compute.factory import runner_for
from chipin_backend.evidence import emit_evidence
from chipin_backend.runs import JsonlEventSink

if TYPE_CHECKING:
    from chipin_backend.api.manager import ApiRun, RunManager

#: Longest message text, in characters.
MAX_MESSAGE_CHARS = 4000
#: The status line that marks a message as delivered.
DELIVERED_TEXT = "Your message reached the agent"
#: A follow-up's first status line.
CONTINUING_TEXT = "ChipIn is continuing the conversation"
#: The error that ends a follow-up whose agent could not be started.
NOT_STARTED_TEXT = (
    "ChipIn could not continue the conversation: the agent did not start ({reason}). "
    "The run is as it was; send a message to try again."
)
#: A real agent's view of a message during the run. Its first line names the
#: message, so the claude_cli backend can find it in the CLI's transcript; without
#: the last sentence a message arriving between turns would end the run.
USER_MESSAGE_PROMPT = (
    "A message from the user (message {n}) arrived while you work:\n\n{text}\n\n"
    "Reply to the user first, in one or two sentences of plain text before your next tool call: "
    "answer it and say what you will change. Then act on it and carry on with the remaining "
    "stages, reporting each with ./progress, until report.md is written."
)
#: A real agent's view of a message after the run ended.
FOLLOW_UP_PROMPT = (
    "A follow-up message from the user (message {n}), after the run finished:\n\n{text}\n\n"
    "Answer it. If it asks for more work, do it in this folder, report what you do with "
    "./progress, and update report.md if the results change."
)


class SteerError(ValueError):
    """A message that cannot be taken; ``status`` is the HTTP status."""

    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


@dataclass
class Steering:
    """One run's messages: which went to the agent and are not yet delivered, which wait."""

    spec: AgentSpec | None = None
    count: int = 0
    #: (message id, text) passed to the agent, oldest first, until it reports delivery.
    in_agent: deque[tuple[str, str]] = field(default_factory=deque)
    #: (message id, text) for the run's end, sent then as a follow-up.
    held: list[tuple[str, str]] = field(default_factory=list)
    #: Follow-up message ids delivered when the agent starts answering.
    answering: list[str] = field(default_factory=list)
    #: Cost totals before the agent run in progress (``usd``, ``tokens_in``, ``tokens_out``).
    cost_base: dict[str, Any] | None = None
    follow_ups: int = 0
    #: (message id, text) of a follow-up whose agent never started; sent with the next one.
    unanswered: list[tuple[str, str]] = field(default_factory=list)
    log: EventLog | None = None

    def sink(self, translator: Translator, log: EventLog) -> SteerSink:
        """The run's event sink: delivery reports and cost totals here, the rest to ``translator``."""
        self.log = log
        return SteerSink(self, translator)

    def attach(self, item: ApiRun, spec: AgentSpec) -> None:
        """Remember the run's spec (a follow-up reuses it)."""
        self.spec = spec
        item.steer = self

    def next_id(self) -> tuple[str, int]:
        self.count += 1
        return f"m{self.count}", self.count


class SteerSink:
    """An :class:`EventSink` in front of the run's :class:`Translator`."""

    def __init__(self, steering: Steering, translator: Translator) -> None:
        self.steering = steering
        self.translator = translator

    def emit(self, event: AgentEvent) -> None:
        """Turn delivery reports into ``status`` events; add earlier costs to ``cost``."""
        st = self.steering
        if event.kind == "status" and event.data.get("user_message_delivered"):
            self.translator.raw.emit(event)
            message_id = st.in_agent.popleft()[0] if st.in_agent else None
            self._delivered(message_id)
            return
        if st.answering and event.kind in ("text", "thinking", "tool_call"):
            ids, st.answering = st.answering, []
            for message_id in ids:
                self._delivered(message_id)
        if event.kind == "cost" and st.cost_base:
            base = st.cost_base
            data = dict(event.data)
            data.update(turn_usd=data.get("usd"), turn_input_tokens=data.get("input_tokens"))
            data["turn_output_tokens"] = data.get("output_tokens")
            data["usd"] = float(data.get("usd") or 0.0) + float(base.get("usd") or 0.0)
            data["input_tokens"] = int(data.get("input_tokens") or 0) + int(base.get("tokens_in") or 0)
            data["output_tokens"] = int(data.get("output_tokens") or 0) + int(base.get("tokens_out") or 0)
            event = replace(event, data=data)
        self.translator.emit(event)

    def _delivered(self, message_id: str | None) -> None:
        if self.steering.log is not None:
            self.steering.log.append("status", text=DELIVERED_TEXT, message_id=message_id)


def steering_of(item: ApiRun) -> Steering:
    """The run's :class:`Steering`; for a run indexed from disk, a new one counting its messages."""
    st = getattr(item, "steer", None)
    if st is None:
        st = Steering(log=item.log)
        st.count = sum(1 for e in item.log.since(1) if e.get("type") == "message" and e.get("role") == "user")
        item.steer = st
    return st


def _text(text: Any) -> str:
    if not isinstance(text, str) or not text.strip():
        raise SteerError("text must be a non-empty string")
    if len(text) > MAX_MESSAGE_CHARS:
        raise SteerError(f"text is longer than {MAX_MESSAGE_CHARS} characters", status=413)
    return text


async def send_message(manager: RunManager, run_id: str, text: Any) -> dict[str, Any]:
    """Record a user message and deliver it: live, after the run's last step, or as a follow-up."""
    item = manager.get(run_id)
    body = _text(text)
    st = steering_of(item)
    running = item.task is not None and not item.task.done()
    status = item.record.get("status")
    if not running and status == "failed":
        raise SteerError("the run failed; start a new run to go on", status=409)
    if not running and status not in ("succeeded", "stopped"):
        raise SteerError("the run is not in progress", status=409)
    if not running and len(manager.running()) >= manager.config.compute.max_concurrent_agents:
        raise SteerError("too many runs in progress; stop one first", status=429)
    message_id, n = st.next_id()
    if not running:
        item.log.reopen()  # the follow-up's events follow the run's run.finished
    item.log.append("message", role="user", author="you", text=body, message_id=message_id)
    if not running:
        start_follow_up(manager, item, [(message_id, body)])
        return {"accepted": True, "id": message_id, "delivery": "follow_up"}
    if await _inject(manager, item, st, message_id, body, n=n):
        return {"accepted": True, "id": message_id, "delivery": "live"}
    st.held.append((message_id, body))
    item.log.append("status", text="Your message waits: the agent takes it when this step of the run ends")
    return {"accepted": True, "id": message_id, "delivery": "after_run"}


async def _inject(
    manager: RunManager, item: ApiRun, st: Steering, message_id: str, body: str, *, n: int
) -> bool:
    """Pass the message to the running agent; ``False`` when it cannot take one now."""
    inject = getattr(item.runner, "inject", None) if item.runner is not None else None
    if inject is None:
        return False
    st.in_agent.append((message_id, body))
    try:
        await inject(_wrap(manager, item, body, n))
    except (NotImplementedError, RuntimeError) as exc:
        logger.info("run {}: message {} waits for the run's end: {}", item.id, message_id, exc)
        with contextlib.suppress(ValueError):
            st.in_agent.remove((message_id, body))
        return False
    return True


def _agent(manager: RunManager, item: ApiRun) -> str:
    return str(item.record.get("agent") or manager.agent)


def _wrap(manager: RunManager, item: ApiRun, body: str, n: int, *, follow_up: bool = False) -> str:
    """What the agent reads: the stub gets the bare text, a real agent the framed one."""
    if _agent(manager, item) == "stub":
        return body
    return (FOLLOW_UP_PROMPT if follow_up else USER_MESSAGE_PROMPT).format(n=n, text=body.strip())


def watch(manager: RunManager, item: ApiRun) -> None:
    """When the run's task ends, send undelivered and held messages as a follow-up."""
    if item.task is None:
        return

    def done(_task: asyncio.Task[None]) -> None:
        st = steering_of(item)
        waiting = [*st.in_agent, *st.held]
        st.in_agent.clear()
        st.held.clear()
        if not waiting:
            return
        if item.record.get("status") != "succeeded":
            logger.warning(
                "run {} ended {}; {} message(s) not delivered",
                item.id,
                item.record.get("status"),
                len(waiting),
            )
            return
        start_follow_up(manager, item, waiting)

    item.task.add_done_callback(done)


def start_follow_up(manager: RunManager, item: ApiRun, messages: list[tuple[str, str]]) -> None:
    """Continue a finished run's session with ``messages`` (already recorded), in its folder."""
    st = steering_of(item)
    messages, st.unanswered = [*st.unanswered, *messages], []
    st.follow_ups += 1
    st.answering = [message_id for message_id, _ in messages]
    st.cost_base = dict(item.record.get("cost") or {}) or None
    numbers = [int(message_id.removeprefix("m")) for message_id, _ in messages]
    prompt = "\n\n".join(
        _wrap(manager, item, body, n, follow_up=True) for (_, body), n in zip(messages, numbers, strict=True)
    )
    spec = replace(
        st.spec or _spec_from_record(manager, item),
        prompts=[prompt],
        resume_session=_session_id(item),
    )
    before = {k: item.record.get(k) for k in ("status", "finished_at", "summary", "cost")}
    item.log.reopen()
    item.stopping = False
    item.stop_reason = "stopped by the user"
    item.record.update(status="running", follow_ups=st.follow_ups)
    item.record.pop("finished_at", None)
    item.save()
    item.log.append("status", text=CONTINUING_TEXT)
    item.task = asyncio.create_task(
        _drive_follow_up(manager, item, spec, messages=messages, before=before), name=f"follow-up-{item.id}"
    )
    watch(manager, item)
    logger.info("run {}: follow-up {} started", item.id, st.follow_ups)


def _session_id(item: ApiRun) -> str | None:
    try:
        result = item.run.read_record().result or {}
    except (OSError, ValueError, TypeError) as exc:
        logger.warning("run {}: no session to continue: {}", item.id, exc)
        return None
    return result.get("session_id") or None


def _spec_from_record(manager: RunManager, item: ApiRun) -> AgentSpec:
    """The run's spec rebuilt from ``api.json`` (a run indexed after a server restart)."""
    from chipin_backend.api.manager import AGENT_BACKENDS

    agent = _agent(manager, item)
    preset = item.record.get("preset")
    return AgentSpec(
        name="chipin",
        prompts=[],
        backend=AGENT_BACKENDS.get(agent, AGENT_BACKENDS[manager.agent]),  # type: ignore[arg-type]
        model=item.record.get("model"),
        provider=item.record.get("provider"),
        effort=manager.api.presets.get(preset) if preset else None,
        system_prompt=manager.instructions,
        timeout_s=manager.api.run_timeout_s,
        env={STEP_ENV: str(manager.api.stub_step_s)} if agent == "stub" else {},
    )


async def _drive_follow_up(
    manager: RunManager,
    item: ApiRun,
    spec: AgentSpec,
    *,
    messages: list[tuple[str, str]],
    before: dict[str, Any],
) -> None:
    """One follow-up turn of the agent; always ends the event log with ``run.finished``.

    When the agent never started, the run goes back to ``before`` (its status,
    times, summary and cost) and ``messages`` wait for the next follow-up.
    """
    from chipin_backend.api.manager import RUNNER_MODES, ApiRunDir

    st = steering_of(item)
    translator = Translator(
        item.log, JsonlEventSink(item.run.events_path), item.run.workspace, start_text=None
    )
    run = ApiRunDir(item.run.path, sink=st.sink(translator, item.log))
    tailer = ProgressTailer(item.run.path / PROGRESS_FILE, item.log, item.run.path, item.run.workspace)
    tailer.skip_to_end()
    report = item.run.workspace / "report.md"
    report_before = report.stat().st_mtime if report.is_file() else None
    follow = asyncio.create_task(tailer.follow(manager.api.progress_poll_s))
    status, summary, result, not_started = "failed", None, None, False
    runner = runner_for(manager.config, RUNNER_MODES[manager.runner])
    item.runner = runner
    try:
        if item.stopping:
            raise asyncio.CancelledError
        item.inner = asyncio.create_task(runner.run(spec, run))
        result = await item.inner
        status = "failed" if result.failed else "succeeded"
        summary = clip(result.error or translator.last_text or result.final_text, 600) or None
        not_started = result.failed and not result.started
        if not_started:
            reason = clip(result.error or "no reason given", 300)
            item.log.append("error", message=NOT_STARTED_TEXT.format(reason=reason))
        elif result.failed and not translator.error_emitted:
            item.log.append("error", message=result.error or "the agent failed")
    except asyncio.CancelledError:
        if not item.stopping:
            raise
        status, summary = "stopped", item.stop_reason
    except Exception as exc:
        logger.exception("run {}: follow-up failed in the runner", item.id)
        summary = f"{type(exc).__name__}: {exc}"
        item.log.append("error", message=summary)
    finally:
        await runner.close()
        follow.cancel()
        tailer.drain()
        item.runner = None
        if report.is_file() and report.stat().st_mtime != report_before:
            manager._artifact(tailer, "report.md", "report")
        emit_evidence(item.run.path, item.log.append)
        cost = translator.cost or item.record.get("cost")
        outcome = status
        if not_started:
            st.answering, st.unanswered = [], [*messages, *st.unanswered]
            status, summary, cost = before["status"], before["summary"], before["cost"]
        item.log.append(
            "run.finished",
            status=status,
            summary=summary,
            bullets=item.record.get("bullets"),
            follow_up=st.follow_ups,
            follow_up_failed=True if not_started else None,
        )
        finished_at = before["finished_at"] if not_started else utc_now()
        item.record.update(status=status, finished_at=finished_at, summary=summary, cost=cost)
        item.save()
        _record_follow_up(item, result, outcome, st, run_status=status)
        logger.info("run {}: follow-up {} {}", item.id, st.follow_ups, status)


def _record_follow_up(
    item: ApiRun, result: AgentResult | None, status: str, st: Steering, *, run_status: str
) -> None:
    """Add the follow-up to ``run.json``: its outcome (``status``) under ``result.follow_ups``,
    its cost to the total, ``run_status`` as the run's."""
    try:
        record = item.run.read_record()
        merged = dict(record.result or {})
        entry = {"n": st.follow_ups, "status": status, "finished_at": utc_now()}
        if result is not None:
            entry.update(cost_usd=result.cost_usd, session_id=result.session_id, error=result.error)
            if result.session_id:
                merged["session_id"] = result.session_id
        merged["follow_ups"] = [*merged.get("follow_ups", []), entry]
        added = result.cost_usd if result is not None else 0.0
        item.run.update_record(
            result=merged,
            agent_cost_usd=(record.agent_cost_usd or 0.0) + added,
            status=run_status,
            finished_at=utc_now(),
        )
    except (OSError, ValueError, TypeError) as exc:
        logger.warning("run {}: follow-up not written to run.json: {}", item.id, exc)


def shutdown() -> None:
    """Close the conversations kept in memory for follow-ups (server shutdown)."""
    try:
        from chipin_backend.agents.openrouter_agent import close_parked_conversations
    except ImportError:
        return
    close_parked_conversations()


__all__ = [
    "CONTINUING_TEXT",
    "DELIVERED_TEXT",
    "FOLLOW_UP_PROMPT",
    "MAX_MESSAGE_CHARS",
    "NOT_STARTED_TEXT",
    "USER_MESSAGE_PROMPT",
    "SteerError",
    "SteerSink",
    "Steering",
    "send_message",
    "shutdown",
    "start_follow_up",
    "steering_of",
    "watch",
]
