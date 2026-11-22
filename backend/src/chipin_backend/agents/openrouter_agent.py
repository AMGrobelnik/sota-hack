"""``openrouter`` backend: an agent loop on any OpenRouter model.

Uses the OpenHands Agent SDK (LiteLLM underneath) with terminal, file-editor
and task-tracker tools; install with ``uv pip install -e '.[openhands]'``. The
SDK is imported inside :meth:`OpenRouterAgentBackend.run` only, so the base
install keeps working without the extra. Unlike ``claude_cli`` it needs only
``OPENROUTER_API_KEY``, which makes it the easy backend on RunPod pods.

Built on the OpenHands SDK, on paid OpenRouter models only.

The conversation runs in memory (no ``persistence_dir``): the SDK's saved state
holds the LLM settings, API key included, and the workspace is the agent's own
folder, so nothing of it is written to disk.
"""

from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path
from typing import Any, ClassVar

from loguru import logger

from chipin_backend.agents.base import AgentBackend
from chipin_backend.agents.env import build_agent_env
from chipin_backend.agents.mailbox import InjectMailbox
from chipin_backend.agents.output import (
    STRUCT_OUT_FILENAME,
    review_output,
    struct_out_instruction,
    written_files,
)
from chipin_backend.agents.types import AgentEvent, AgentResult, AgentSpec, EventSink
from chipin_backend.chiplab import SKILL_DIRS
from chipin_backend.config import AgentsConfig, OpenRouterAgentConfig
from chipin_backend.llm.providers import DEFAULT_PROVIDER, Provider, resolve_provider

#: Per-request timeout for one model call.
LLM_CALL_TIMEOUT_S = 600
#: Model calls per request: 1 + 4 retries on rate limits, 5xx and connection
#: errors, backing off 1, 2, 4, 8 s (LiteLLM's own retry, run by the SDK).
LLM_CALL_ATTEMPTS = 5
#: A ``run()`` with no agent event for this long is stopped and resumed.
IDLE_TIMEOUT_S = 1800.0
#: Least seconds between two interim ``cost`` events of one run.
LIVE_COST_INTERVAL_S = 5.0
#: Agent steps (model call plus tool calls) per ``run()``.
MAX_ITERATIONS = 200
#: The SDK's tool names, by the names a spec may use in ``allowed_tools``.
TOOL_NAMES = ("terminal", "file_editor", "task_tracker")

#: Sent when a run is resumed after an idle timeout.
RESUME_NUDGE = (
    "Your previous run was interrupted after a long time with no progress. Continue the "
    "task from where you left off, reusing work already on disk. If a command takes "
    "very long, split it into shorter steps."
)
#: The status emitted when a user message reached the conversation (``user_message_delivered``).
DELIVERED_STATUS = "Your message reached the agent"
#: Finished conversations kept in memory for a follow-up, newest last.
PARKED_MAX = 4
#: Sent first when a follow-up cannot continue the conversation (it is gone from memory).
LOST_CONVERSATION_NOTE = (
    "This continues an earlier run in this working folder, but its conversation is no longer "
    "in memory: read brief.md, report.md and the other files here to see what was done."
)


class _Route:
    """Where a conversation's SDK callback sends events; a follow-up points it at its own run."""

    def __init__(self) -> None:
        self.target: Any = None

    def __call__(self, event: Any) -> None:
        if self.target is not None:
            self.target(event)


#: conversation id -> (conversation, route): finished conversations a follow-up may continue.
_PARKED: dict[str, tuple[Any, _Route]] = {}
#: conversation id -> its accumulated cost when parked, so a follow-up reports only its own.
_PARKED_USD: dict[str, tuple[float, int, int]] = {}


def parked_usd(conversation: Any) -> tuple[float, int, int]:
    """What a parked conversation had already run up: dollars, input and output tokens."""
    return _PARKED_USD.pop(str(conversation.id), (0.0, 0, 0))


def close_parked_conversations() -> None:
    """Close every conversation kept for a follow-up (server shutdown)."""
    while _PARKED:
        _, (conversation, _) = _PARKED.popitem()
        try:
            conversation.close()
        except Exception:  # closing is best effort at shutdown
            logger.exception("openrouter: a parked conversation did not close")


def normalize_model(model: str, provider: str = DEFAULT_PROVIDER) -> str:
    """The id as LiteLLM names it.

    OpenRouter: ``vendor/slug`` as ``openrouter/vendor/slug`` (a prefixed id passes
    through). Any other provider is an OpenAI-compatible endpoint: ``openai/<id>``.
    """
    model = model.strip()
    if provider != DEFAULT_PROVIDER:
        if not model:
            raise ValueError("empty model id")
        return model if model.startswith("openai/") else f"openai/{model}"
    if model.startswith("openrouter/"):
        return model
    if "/" not in model:
        raise ValueError(f"{model!r} is not an OpenRouter model id (vendor/slug)")
    return f"openrouter/{model}"


def mcp_servers_for(raw: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """The headless-usable MCP servers in ``raw`` (bare or ``mcpServers``-wrapped).

    A server with OAuth auth would open a browser and hang a headless agent,
    so it is dropped with a warning.
    """
    servers = raw.get("mcpServers", raw) if isinstance(raw, dict) else {}
    usable: dict[str, dict[str, Any]] = {}
    for name, server in servers.items():
        if not isinstance(server, dict):
            continue
        auth = server.get("auth")
        strategy = auth.get("strategy") if isinstance(auth, dict) else auth
        if str(strategy or "").strip().lower() == "oauth":
            logger.warning("openrouter: MCP server {!r} needs a browser login; dropped", name)
            continue
        usable[name] = dict(server)
    return usable


def workspace_skills(workdir: Path) -> list[Any]:
    """The AgentSkills-format skills (``SKILL.md`` folders) in ``workdir/.agents/skills``.

    The backend installs the chip-lab skill there (``chiplab.install_skill``).
    They go into the agent's ``AgentContext``: the SDK lists each skill's name
    and description in the system prompt's ``<available_skills>`` and attaches
    its ``invoke_skill`` tool, which returns the skill's body when the agent
    calls it. Only this folder is read: the SDK's own project loading would
    also pick up instruction files (``AGENTS.md`` and the like) from parent
    folders up to the git root.
    """
    from openhands.sdk import load_skills_from_dir

    folder = workdir / SKILL_DIRS["openrouter"]
    if not folder.is_dir():
        return []
    _, _, agent_skills = load_skills_from_dir(folder, root=workdir.resolve())
    return list(agent_skills.values())


def _texts(content: Any) -> str:
    """The text of a content list (``TextContent`` items), a string, or ``""``."""
    if isinstance(content, str):
        return content
    if isinstance(content, list | tuple):
        return "".join(str(getattr(c, "text", "") or "") for c in content)
    return ""


def translate_event(event: Any, agent: str) -> list[AgentEvent]:
    """Events for one OpenHands event (zero or more).

    Agent messages become ``text`` (and ``thinking`` for reasoning); actions
    become ``tool_call``; observations and tool errors become ``tool_result``;
    a conversation-level failure becomes ``error``. System prompts, user
    messages and housekeeping events yield nothing.
    """
    kind = type(event).__name__
    out: list[AgentEvent] = []
    reasoning = getattr(event, "reasoning_content", None)
    if kind == "MessageEvent":
        if getattr(event, "source", "") != "agent":
            return out
        msg = getattr(event, "llm_message", None)
        reasoning = getattr(msg, "reasoning_content", None)
        if reasoning:
            out.append(AgentEvent("thinking", agent, {"text": reasoning}))
        if text := _texts(getattr(msg, "content", None)):
            out.append(AgentEvent("text", agent, {"text": text}))
    elif kind == "ActionEvent":
        if reasoning:
            out.append(AgentEvent("thinking", agent, {"text": reasoning}))
        if thought := _texts(getattr(event, "thought", None)):
            out.append(AgentEvent("text", agent, {"text": thought}))
        action = getattr(event, "action", None)
        args: dict[str, Any] = action.model_dump(exclude={"kind"}) if action is not None else {}
        out.append(
            AgentEvent(
                "tool_call",
                agent,
                {"tool": event.tool_name, "input": args, "call_id": event.tool_call_id},
            )
        )
    elif kind == "ObservationEvent":
        obs = event.observation
        output = getattr(obs, "text", "") or str(obs)
        data = {"call_id": event.tool_call_id, "output": output, "is_error": bool(obs.is_error)}
        out.append(AgentEvent("tool_result", agent, data))
    elif kind in ("AgentErrorEvent", "UserRejectObservation"):
        output = getattr(event, "error", None) or getattr(event, "rejection_reason", "")
        data = {"call_id": event.tool_call_id, "output": str(output), "is_error": True}
        out.append(AgentEvent("tool_result", agent, data))
    elif kind == "ConversationErrorEvent":
        out.append(AgentEvent("error", agent, {"message": f"{event.code}: {event.detail}"}))
    return out


class _Activity:
    """Monotonic time of the last agent event, written from the SDK's worker thread."""

    def __init__(self) -> None:
        self.last = time.monotonic()

    def mark(self) -> None:
        self.last = time.monotonic()


class OpenRouterAgentBackend(AgentBackend):
    """One OpenHands conversation per :meth:`run`."""

    name: ClassVar[str] = "openrouter"

    def __init__(self, config: AgentsConfig) -> None:
        super().__init__(config)
        self._mailbox = InjectMailbox()
        self._conversation: Any = None
        self._deliver_lock = asyncio.Lock()
        self._deliveries: set[asyncio.Task[int]] = set()
        self._emit: Any = None

    @property
    def openrouter(self) -> OpenRouterAgentConfig:
        """This backend's config section."""
        return self.config.openrouter

    async def run(self, spec: AgentSpec, sink: EventSink) -> AgentResult:
        """Build the LLM, the tools and the conversation in ``spec.workdir``;
        send every prompt; emit events as they happen; validate
        ``spec.output_schema`` and ``spec.expected_files`` with corrective
        turns; read the cost from the conversation's metrics.

        Model calls retry transient faults (see :data:`LLM_CALL_ATTEMPTS`) and
        then fall over, call by call, to ``fallback_model``. Raises only for
        setup errors: no workdir, no ``openhands`` extra, no key.
        """
        if spec.workdir is None:
            raise ValueError("spec.workdir must be set by the runner")
        provider = resolve_provider(self.providers, spec.provider)
        key = provider.api_key()
        try:
            from openhands.sdk import Conversation
        except ImportError as err:
            raise RuntimeError("the openrouter backend needs the openhands extra") from err
        workdir = spec.workdir.resolve()
        workdir.mkdir(parents=True, exist_ok=True)
        model_id = provider.model_for(spec.model, fallback=self.openrouter.model)
        model = normalize_model(model_id, provider.name)
        logger.info("agent {}: provider {} model {}", spec.name, provider.name, model_id)
        started = time.monotonic()
        lock = threading.Lock()
        activity = _Activity()
        final = {"text": ""}
        live = _LiveCost()

        def emit(kind: str, data: dict[str, Any]) -> None:
            with lock:
                try:
                    sink.emit(AgentEvent(kind, spec.name, data))  # type: ignore[arg-type]
                except Exception:
                    logger.exception("openrouter: event sink raised; event dropped")

        def on_event(event: Any) -> None:
            activity.mark()
            for out in translate_event(event, spec.name):
                if out.kind == "text":
                    final["text"] = out.data["text"]
                emit(out.kind, out.data)
            action = getattr(event, "action", None)
            if type(action).__name__ == "FinishAction":
                final["text"] = action.message or final["text"]
            live.after_step(event, emit)

        emit("agent_start", {"backend": self.name, "provider": provider.name, "model": model})
        parked = _PARKED.pop(spec.resume_session, None) if spec.resume_session else None
        before = (0.0, 0, 0)  # what a continued conversation had already run up
        if parked is not None:
            conversation, route = parked
            before = parked_usd(conversation)
        else:
            route = _Route()
            agent = self._build_agent(spec, model, key, provider)
            conversation = Conversation(
                agent=agent,
                workspace=str(workdir),
                persistence_dir=None,  # never write the SDK state (it carries the key)
                callbacks=[route],
                max_iteration_per_run=MAX_ITERATIONS,
                visualizer=None,
            )
        live.conversation, live.before = conversation, before
        route.target = on_event
        self._conversation = conversation
        self._emit = emit
        self._mailbox.open()

        output_file = str(workdir / STRUCT_OUT_FILENAME)
        prompts = list(spec.prompts)
        if spec.resume_session and parked is None and prompts:
            prompts[0] = f"{LOST_CONVERSATION_NOTE}\n\n{prompts[0]}"
        if spec.output_schema is not None:
            (workdir / STRUCT_OUT_FILENAME).unlink(missing_ok=True)
            if prompts:
                prompts[-1] += struct_out_instruction(spec.output_schema, output_file)

        deadline = started + spec.timeout_s if spec.timeout_s else None
        error: str | None = None
        structured = None
        try:
            for prompt in prompts:
                await self._turn(conversation, prompt, spec, activity, deadline, emit)
            for attempt in range(1, spec.output_retries + 2):
                structured, fix = review_output(
                    workdir,
                    spec.output_schema,
                    spec.expected_files,
                    attempt=attempt,
                    output_file=output_file,
                )
                if fix is None:
                    break
                if attempt > spec.output_retries:
                    error = f"output still invalid after {spec.output_retries} corrective turns: {fix}"
                    break
                emit("status", {"message": f"output check failed; corrective turn {attempt}"})
                # The file editor cannot overwrite a file, so clear the old output first.
                (workdir / STRUCT_OUT_FILENAME).unlink(missing_ok=True)
                await self._turn(conversation, fix, spec, activity, deadline, emit)
        except (_AgentFailedError, TimeoutError) as err:
            error = str(err)
        except asyncio.CancelledError:
            # Cancelled from outside (the runner's wall clock, a stop): the
            # money is spent all the same, so report it before going.
            _emit_cost(conversation, emit, before=before)
            raise
        finally:
            self._mailbox.close()

        usd, totals = _emit_cost(conversation, emit, error=error, before=before)
        route.target = None
        if error is None:
            self._park(conversation, route, totals)
        await self.close()
        duration = time.monotonic() - started
        emit("agent_end", {"failed": error is not None, "duration_s": duration})
        return AgentResult(
            agent=spec.name,
            final_text=final["text"],
            structured_output=structured if error is None else None,
            failed=error is not None,
            error=error,
            session_id=str(conversation.id),
            cost_usd=float(usd),
            duration_s=duration,
            files=written_files(workdir),
        )

    async def inject(self, message: str) -> None:
        """Add ``message`` to the running conversation without stopping it.

        ``Conversation.send_message`` may be called while ``run()`` works: it
        waits for the conversation's state lock, appends the user message, and
        the agent's next step reads it (a message after the agent finished
        sets the conversation back to idle, and ``run()`` goes on). Messages
        go in the order they came; a ``status`` event with
        ``user_message_delivered`` marks each. ``RuntimeError`` when no run is
        in progress.
        """
        if not message.strip():
            raise ValueError("an empty message")
        if not self._mailbox.try_put(message):
            raise RuntimeError("no openrouter run is in progress")
        task = asyncio.get_running_loop().create_task(self._deliver_waiting())
        self._deliveries.add(task)
        task.add_done_callback(self._deliveries.discard)

    async def _deliver_waiting(self) -> int:
        """Send every waiting message into the conversation, oldest first; how many went."""
        async with self._deliver_lock:
            conversation, sent = self._conversation, 0
            for message in self._mailbox.drain():
                if conversation is None:
                    logger.warning("openrouter: a message arrived after the conversation closed")
                    break
                await asyncio.to_thread(conversation.send_message, message)
                sent += 1
                if self._emit is not None:
                    self._emit("status", {"message": DELIVERED_STATUS, "user_message_delivered": True})
            return sent

    def _park(self, conversation: Any, route: _Route, totals: tuple[float, int, int]) -> None:
        """Keep a finished conversation for a follow-up; the oldest beyond :data:`PARKED_MAX` closes."""
        _PARKED[str(conversation.id)] = (conversation, route)
        _PARKED_USD[str(conversation.id)] = totals
        self._conversation = None
        while len(_PARKED) > PARKED_MAX:
            oldest = next(iter(_PARKED))
            old, _ = _PARKED.pop(oldest)
            _PARKED_USD.pop(oldest, None)
            try:
                old.close()
            except Exception:
                logger.exception("openrouter: a parked conversation did not close")

    async def close(self) -> None:
        """Close the conversation (its terminal sessions). Idempotent."""
        conversation, self._conversation = self._conversation, None
        if conversation is not None:
            await asyncio.to_thread(conversation.close)

    def _build_llm(
        self, model: str, key: str, provider: Provider, *, usage_id: str, fallback: Any = None
    ) -> Any:
        """One OpenRouter ``LLM`` for the SDK, retrying transient faults itself.

        ``fallback`` is a ``FallbackStrategy`` tried when a call still fails.
        """
        from openhands.sdk import LLM
        from pydantic import SecretStr

        cfg = self.openrouter
        extra_body: dict[str, Any] = {}
        is_openrouter = provider.name == DEFAULT_PROVIDER
        if is_openrouter and cfg.provider_order:
            extra_body["provider"] = {"order": cfg.provider_order, "allow_fallbacks": cfg.allow_fallbacks}
        return LLM(
            model=model,
            api_key=SecretStr(key),
            base_url=provider.base_url,
            usage_id=usage_id,
            timeout=LLM_CALL_TIMEOUT_S,
            num_retries=LLM_CALL_ATTEMPTS - 1,
            retry_min_wait=1,
            retry_max_wait=8,
            retry_multiplier=1.0,
            reasoning_effort=cfg.effort if is_openrouter else None,
            litellm_extra_body=extra_body,
            fallback_strategy=fallback,
        )

    def _build_agent(self, spec: AgentSpec, model: str, key: str, provider: Provider) -> Any:
        """The OpenHands ``Agent``: LLM (with backup model), tools, prompt, MCP servers."""
        from openhands.sdk import Agent, AgentContext
        from openhands.sdk.llm.fallback_strategy import FallbackStrategy
        from openhands.sdk.tool import Tool
        from openhands.tools import FileEditorTool, TaskTrackerTool

        from chipin_backend.agents.paced_terminal import PACED_TERMINAL

        strategy = None
        backup = self.openrouter.fallback_model if provider.name == DEFAULT_PROVIDER else None
        if backup and normalize_model(backup) != model:
            strategy = FallbackStrategy(fallback_llms=[backup])
            # Pre-filled, so the SDK never looks for a profile file holding the key.
            strategy._resolved = [
                self._build_llm(normalize_model(backup), key, provider, usage_id="agent-fallback")
            ]
        llm = self._build_llm(model, key, provider, usage_id="agent", fallback=strategy)

        # The terminal is the SDK's subprocess one fed in small pieces (see paced_terminal).
        registry = {
            "terminal": PACED_TERMINAL,
            "file_editor": FileEditorTool.name,
            "task_tracker": TaskTrackerTool.name,
        }
        names = [n for n in TOOL_NAMES if spec.allowed_tools is None or n in spec.allowed_tools]
        names = [n for n in names if n not in (spec.disallowed_tools or [])]
        terminal_params = {"env": build_agent_env(spec.env)}
        tools = [Tool(name=registry[n], params=terminal_params if n == "terminal" else {}) for n in names]
        kwargs: dict[str, Any] = {"llm": llm, "tools": tools}
        # One context for both: the instructions are appended to OpenHands' own
        # system message (which keeps its tool rules) and the skills are listed in it.
        context: dict[str, Any] = {}
        if spec.system_prompt:
            context["system_message_suffix"] = spec.system_prompt
        if spec.workdir is not None and (skills := workspace_skills(spec.workdir)):
            context["skills"] = skills
        if context:
            kwargs["agent_context"] = AgentContext(**context)
        if servers := mcp_servers_for(spec.mcp_servers):
            kwargs["mcp_config"] = servers
        return Agent(**kwargs)

    async def _turn(
        self,
        conversation: Any,
        prompt: str,
        spec: AgentSpec,
        activity: _Activity,
        deadline: float | None,
        emit: Any,
    ) -> None:
        """Send ``prompt`` and run until the agent finishes, and on while user messages arrive.

        A run with no event for :data:`IDLE_TIMEOUT_S` is paused and resumed
        with a nudge, up to ``spec.retries`` times.
        """
        from openhands.sdk.conversation.state import ConversationExecutionStatus

        pending: list[str | None] = [prompt]
        resumes = 0
        while pending:
            if pending[0] is not None:
                await asyncio.to_thread(conversation.send_message, pending[0])
            pending.pop(0)
            try:
                await _run_until_idle(conversation, activity, deadline)
            except TimeoutError as err:
                if isinstance(err, _DeadlineError) or resumes >= spec.retries:
                    raise
                resumes += 1
                emit("status", {"message": f"{err}; resuming ({resumes}/{spec.retries})"})
                pending.insert(0, RESUME_NUDGE)
                continue
            status = conversation.state.execution_status
            if status in (ConversationExecutionStatus.ERROR, ConversationExecutionStatus.STUCK):
                raise _AgentFailedError(f"conversation ended in state {status.value}")
            # A message sent as the agent finished left the conversation idle: run it
            # (``None``: run on without sending anything new).
            sent = await self._deliver_waiting()
            if sent or conversation.state.execution_status == ConversationExecutionStatus.IDLE:
                pending.append(None)


class _AgentFailedError(Exception):
    """The conversation ended in an error or stuck state."""


class _DeadlineError(TimeoutError):
    """The agent's whole time budget is spent."""


def _emit_cost(
    conversation: Any,
    emit: Any,
    *,
    error: str | None = None,
    before: tuple[float, int, int] = (0.0, 0, 0),
) -> tuple[float, tuple[float, int, int]]:
    """Emit the ``error`` (if any) and this run's ``cost``: the conversation's totals
    less ``before`` (what a continued conversation had already run up).

    Returns this run's USD and the conversation's totals (dollars, input, output tokens).
    """
    totals = _totals(conversation)
    usd, tokens_in, tokens_out = (max(a - b, 0) for a, b in zip(totals, before, strict=True))
    if error:
        emit("error", {"message": error})
    emit("cost", {"usd": float(usd), "input_tokens": int(tokens_in), "output_tokens": int(tokens_out)})
    return float(usd), totals


def _totals(conversation: Any) -> tuple[float, int, int]:
    """The conversation's spend so far: dollars, input tokens, output tokens."""
    metrics = conversation.conversation_stats.get_combined_metrics()
    tokens = metrics.accumulated_token_usage
    return (
        float(metrics.accumulated_cost or 0.0),
        int(tokens.prompt_tokens) if tokens else 0,
        int(tokens.completion_tokens) if tokens else 0,
    )


class _LiveCost:
    """Emits this run's spend so far while it works, at most every :data:`LIVE_COST_INTERVAL_S`.

    A ``cost`` event's ``usd`` is the agent's spend so far (``api.costs``), so
    these interim events and the closing one mean the same thing; without them
    a run shows no cost until its agent ends.
    """

    def __init__(self) -> None:
        self.conversation: Any = None
        self.before: tuple[float, int, int] = (0.0, 0, 0)
        self._usd = 0.0
        self._at = 0.0

    def after_step(self, event: Any, emit: Any) -> None:
        """Called for every SDK event; emits after a model call when the spend went up."""
        if self.conversation is None or type(event).__name__ not in ("ActionEvent", "MessageEvent"):
            return
        now = time.monotonic()
        if now - self._at < LIVE_COST_INTERVAL_S:
            return
        try:
            totals = _totals(self.conversation)
        except Exception:
            logger.exception("openrouter: could not read the live cost")
            return
        usd, tokens_in, tokens_out = (max(a - b, 0) for a, b in zip(totals, self.before, strict=True))
        if usd <= self._usd:
            return
        self._usd, self._at = float(usd), now
        emit("cost", {"usd": float(usd), "input_tokens": int(tokens_in), "output_tokens": int(tokens_out)})


async def _run_until_idle(conversation: Any, activity: _Activity, deadline: float | None) -> None:
    """Run the conversation in a thread; stop it on inactivity, at ``deadline`` or when cancelled.

    Cancelling the await does not stop the SDK's worker thread, so a cancel
    (a stop, the runner's wall clock) pauses the conversation as well; the
    pause takes effect after the step in progress. It is requested from its
    own thread because it waits for the conversation's lock, which a step holds.
    """
    activity.mark()
    task = asyncio.create_task(asyncio.to_thread(conversation.run))
    try:
        await _watch(conversation, task, activity, deadline)
    except asyncio.CancelledError:
        threading.Thread(target=conversation.pause, name="openrouter-pause", daemon=True).start()
        raise


async def _watch(conversation: Any, task: Any, activity: _Activity, deadline: float | None) -> None:
    """Wait for ``task`` (the conversation's run); pause it on inactivity or at ``deadline``."""
    while True:
        now = time.monotonic()
        idle_at = activity.last + IDLE_TIMEOUT_S
        stop_at = min(idle_at, deadline) if deadline is not None else idle_at
        if now >= stop_at:
            await asyncio.to_thread(conversation.pause)
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=60)
            except TimeoutError:
                logger.warning("openrouter: the paused run did not stop within 60s")
            if deadline is not None and now >= deadline:
                raise _DeadlineError("the agent's time budget is spent")
            raise TimeoutError(f"no agent progress for {IDLE_TIMEOUT_S:.0f}s")
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=stop_at - now)
            return
        except TimeoutError:
            continue


__all__ = [
    "DELIVERED_STATUS",
    "OpenRouterAgentBackend",
    "close_parked_conversations",
    "mcp_servers_for",
    "normalize_model",
    "translate_event",
    "workspace_skills",
]
