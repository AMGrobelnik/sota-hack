"""The agent contract: what to run (:class:`AgentSpec`), what it streams
(:class:`AgentEvent` into an :class:`EventSink`) and what it returns
(:class:`AgentResult`).

Every type round-trips through ``to_dict``/``from_dict`` as plain JSON, because
On Demand mode ships a spec to a RunPod worker pod and streams events and the
result back over HTTP. Only the fields a ChipIn agent needs.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

from chipin_backend.config import Effort

#: Kinds of event an agent backend emits. ``data`` carries the payload:
#: ``text``/``thinking`` -> ``{"text"}``; ``tool_call`` -> ``{"tool", "input",
#: "call_id"}``; ``tool_result`` -> ``{"call_id", "output", "is_error"}``;
#: ``cost`` -> ``{"usd", "input_tokens", "output_tokens"}``; ``status`` ->
#: ``{"message"}``; ``error`` -> ``{"message"}``; ``agent_start``/``agent_end``
#: -> backend-specific summary (model, session id, duration).
EventKind = Literal[
    "agent_start",
    "text",
    "thinking",
    "tool_call",
    "tool_result",
    "cost",
    "status",
    "error",
    "agent_end",
]


def utc_now() -> str:
    """The current UTC time as an ISO-8601 string."""
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class AgentEvent:
    """One thing an agent did, in the order it did it."""

    kind: EventKind
    agent: str
    data: dict[str, Any] = field(default_factory=dict)
    ts: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        """Plain JSON-ready dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentEvent:
        """Inverse of :meth:`to_dict`."""
        return cls(kind=data["kind"], agent=data["agent"], data=data.get("data", {}), ts=data["ts"])


@runtime_checkable
class EventSink(Protocol):
    """Receives an agent's events as they happen. Must not raise on a full disk
    or a closed stream in a way that kills the agent; log and carry on."""

    def emit(self, event: AgentEvent) -> None:
        """Record or forward one event."""
        ...


@dataclass
class AgentSpec:
    """Everything needed to run one agent, independent of backend and machine.

    ``backend`` and ``model``/``effort`` default to the config's choice when
    ``None``. ``workdir`` ``None`` means the runner picks the run's own
    ``workspace/`` folder. ``env`` carries NON-secret values only; keys reach
    the agent through the allowlist in :mod:`chipin_backend.agents.env`.
    """

    name: str
    prompts: list[str]
    backend: Literal["claude_cli", "openrouter", "stub"] | None = None
    model: str | None = None
    provider: str | None = None  # openrouter backend only; None = openrouter
    effort: Effort | None = None
    system_prompt: str | None = None
    allowed_tools: list[str] | None = None  # None = backend default tool set
    disallowed_tools: list[str] | None = None
    mcp_servers: dict[str, Any] = field(default_factory=dict)
    skills: list[str] = field(default_factory=list)  # names or globs under .claude/skills
    output_schema: dict[str, Any] | None = None  # JSON schema of the structured result
    output_retries: int = 2  # re-prompts when the output fails the schema
    expected_files: list[str] = field(default_factory=list)  # relative to workdir
    workdir: Path | None = None
    timeout_s: int | None = None  # whole-agent wall clock
    retries: int = 1  # whole-agent restarts after a crash or stall
    env: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Plain JSON-ready dict (``workdir`` as a string)."""
        data = asdict(self)
        data["workdir"] = str(self.workdir) if self.workdir is not None else None
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentSpec:
        """Inverse of :meth:`to_dict`; unknown keys are an error."""
        known = {f.name for f in fields(cls)}
        unknown = set(data) - known
        if unknown:
            raise ValueError(f"unknown AgentSpec fields: {sorted(unknown)}")
        values = dict(data)
        if values.get("workdir") is not None:
            values["workdir"] = Path(values["workdir"])
        return cls(**values)


@dataclass
class AgentResult:
    """What an agent produced. ``failed`` with ``error`` set when it did not finish."""

    agent: str
    final_text: str = ""
    structured_output: dict[str, Any] | None = None
    failed: bool = False
    error: str | None = None
    session_id: str | None = None  # backend session, for resume
    cost_usd: float = 0.0
    duration_s: float = 0.0
    files: list[str] = field(default_factory=list)  # files written, relative to workdir
    #: Written after the run (``chipin_backend.llm.summarise``): ``{"run": ...,
    #: "output_label": ...}``, each a ``Summary.to_dict()`` with its own cost.
    summary: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Plain JSON-ready dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentResult:
        """Inverse of :meth:`to_dict`; unknown keys are ignored (newer workers)."""
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})


__all__ = ["AgentEvent", "AgentResult", "AgentSpec", "EventKind", "EventSink", "utc_now"]
