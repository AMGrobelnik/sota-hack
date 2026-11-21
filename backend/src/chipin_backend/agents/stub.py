"""``stub`` backend: no model at all, for tests and dry runs of the whole path.

Emits the same event kinds as a real backend, writes the expected files and
returns zero cost, so a runner, a run folder and (later) a worker pod can be
exercised end to end without spending anything.
"""

from __future__ import annotations

import time
from typing import ClassVar

from chipin_backend.agents.base import AgentBackend
from chipin_backend.agents.types import AgentEvent, AgentResult, AgentSpec, EventSink


class StubBackend(AgentBackend):
    """Echoes the last prompt and writes every expected file."""

    name: ClassVar[str] = "stub"

    async def run(self, spec: AgentSpec, sink: EventSink) -> AgentResult:
        """Pretend to run ``spec``; never fails unless the workdir is unwritable."""
        if spec.workdir is None:
            raise ValueError("spec.workdir must be set by the runner")
        started = time.monotonic()
        sink.emit(AgentEvent("agent_start", spec.name, {"backend": self.name, "model": None}))
        reply = f"stub reply to: {spec.prompts[-1] if spec.prompts else ''}"
        sink.emit(AgentEvent("text", spec.name, {"text": reply}))
        written: list[str] = []
        for rel in spec.expected_files:
            target = spec.workdir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("stub\n", encoding="utf-8")
            written.append(rel)
        structured = {} if spec.output_schema is not None else None
        sink.emit(AgentEvent("cost", spec.name, {"usd": 0.0, "input_tokens": 0, "output_tokens": 0}))
        duration = time.monotonic() - started
        sink.emit(AgentEvent("agent_end", spec.name, {"failed": False, "duration_s": duration}))
        return AgentResult(
            agent=spec.name,
            final_text=reply,
            structured_output=structured,
            duration_s=duration,
            files=written,
        )


__all__ = ["StubBackend"]
