"""``scripted`` backend: a believable ChipIn run with no model and no paid call.

For tests and for building the dashboards. It walks the seven stages, calls
the run's real ``./progress`` helper for every stage, metric and status (so
the helper -> ``progress.jsonl`` -> event path is exercised), emits text and
tool events like a real agent, answers injected user messages, and writes a
``report.md``. Every number it reports is a labelled placeholder.
Pause between steps: ``spec.env["CHIPIN_STUB_STEP_S"]`` seconds.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, ClassVar

from chipin_backend.agents.base import BACKENDS, AgentBackend
from chipin_backend.agents.mailbox import InjectMailbox
from chipin_backend.agents.types import AgentEvent, AgentResult, AgentSpec, EventSink
from chipin_backend.config import AgentsConfig

NAME = "scripted"
STEP_ENV = "CHIPIN_STUB_STEP_S"

#: (stage, status line, agent text, metrics) per stage.
_PLAN: list[tuple[str, str, str, list[tuple[str, float]]]] = [
    ("spec", "ChipIn is reading your brief", "I read the brief and wrote spec.md.", []),
    ("reference", "ChipIn is training a reference model", "A reference model is in place.", []),
    ("propose", "ChipIn is sketching candidate designs", "Three candidate designs.", [("candidates", 3)]),
    ("finetune", "ChipIn is fine-tuning the candidates", "Two fine-tuning rounds done.", [("round", 2)]),
    ("compile", "ChipIn is wiring the weights into gates", "The best design compiles.", [("gates", 2330)]),
    (
        "verify",
        "ChipIn is checking the chip against patient recordings",
        "Verification finished.",
        [("patients_pass", 41), ("patients_total", 48)],
    ),
    ("report", "ChipIn is writing the report", "The report is ready: report.md.", []),
]


class ScriptedBackend(AgentBackend):
    """Plays a fixed ChipIn run; supports :meth:`inject`."""

    name: ClassVar[str] = NAME

    def __init__(self, config: AgentsConfig) -> None:
        super().__init__(config)
        self._mailbox = InjectMailbox()
        self._calls = 0

    async def inject(self, message: str) -> None:
        """Queue ``message``; it is answered at the next step."""
        if not self._mailbox.try_put(message):
            raise RuntimeError("no scripted run is in progress")

    async def run(self, spec: AgentSpec, sink: EventSink) -> AgentResult:
        """Walk the stages; cancellable at every pause."""
        if spec.workdir is None:
            raise ValueError("spec.workdir must be set by the runner")
        workdir = spec.workdir
        step_s = float(spec.env.get(STEP_ENV, "0.4"))
        started = time.monotonic()
        self._mailbox.open()

        def say(text: str) -> None:
            sink.emit(AgentEvent("text", spec.name, {"text": text}))

        try:
            sink.emit(AgentEvent("agent_start", spec.name, {"backend": NAME, "model": None}))
            say("This is the scripted stub agent: no model is called and every number is a placeholder.")
            await self._tool(sink, spec.name, "Read", {"file_path": str(workdir / "brief.md")}, "brief")
            for stage, status, text, metrics in _PLAN:
                await self._answer_messages(say)
                await self._progress(sink, spec.name, workdir, "stage", stage, "started")
                await self._progress(sink, spec.name, workdir, "status", status)
                await asyncio.sleep(step_s)
                if stage == "spec":
                    await self._write(sink, spec.name, workdir / "spec.md", "# Spec (stub)\n")
                if stage == "report":
                    await self._write(sink, spec.name, workdir / "report.md", _report(spec))
                    await self._progress(sink, spec.name, workdir, "artifact", "report.md", "report")
                for key, value in metrics:
                    await self._progress(sink, spec.name, workdir, "metric", key, str(value))
                say(f"{text} (stub)")
                await self._progress(sink, spec.name, workdir, "stage", stage, "done")
            await self._answer_messages(say)
            summary = "Stub run complete: seven stages walked, placeholder numbers only."
            say(summary)
            sink.emit(AgentEvent("cost", spec.name, {"usd": 0.0, "input_tokens": 0, "output_tokens": 0}))
            duration = time.monotonic() - started
            sink.emit(AgentEvent("agent_end", spec.name, {"failed": False, "duration_s": duration}))
            return AgentResult(
                agent=spec.name,
                final_text=summary,
                duration_s=duration,
                files=["spec.md", "report.md"],
            )
        finally:
            self._mailbox.close()

    async def _answer_messages(self, say: Callable[[str], None]) -> None:
        for message in self._mailbox.drain():
            say(f"Noted your message: {message.strip()} (stub: the plan does not change)")

    async def _tool(self, sink: EventSink, agent: str, tool: str, args: dict[str, Any], output: str) -> None:
        self._calls += 1
        call_id = f"stub-{self._calls}"
        sink.emit(AgentEvent("tool_call", agent, {"tool": tool, "input": args, "call_id": call_id}))
        await asyncio.sleep(0)
        sink.emit(AgentEvent("tool_result", agent, {"call_id": call_id, "output": output, "is_error": False}))

    async def _write(self, sink: EventSink, agent: str, path: Path, text: str) -> None:
        path.write_text(text, encoding="utf-8")
        await self._tool(sink, agent, "Write", {"file_path": str(path)}, f"wrote {path.name}")

    async def _progress(self, sink: EventSink, agent: str, workdir: Path, *args: str) -> None:
        """Run the real helper, shown as the shell call a real agent would make."""
        self._calls += 1
        call_id = f"stub-{self._calls}"
        command = "./progress " + " ".join(f'"{a}"' if " " in a else a for a in args)
        sink.emit(
            AgentEvent(
                "tool_call", agent, {"tool": "Bash", "input": {"command": command}, "call_id": call_id}
            )
        )
        proc = await asyncio.create_subprocess_exec(
            str(workdir / "progress"),
            *args,
            cwd=workdir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            out, _ = await proc.communicate()
        except asyncio.CancelledError:
            with contextlib.suppress(ProcessLookupError):
                proc.kill()
            await proc.wait()
            raise
        sink.emit(
            AgentEvent(
                "tool_result",
                agent,
                {
                    "call_id": call_id,
                    "output": out.decode(errors="replace"),
                    "is_error": proc.returncode != 0,
                },
            )
        )


def _report(spec: AgentSpec) -> str:
    brief = spec.prompts[-1] if spec.prompts else ""
    return (
        "# ChipIn report (stub run)\n\n"
        "This run used the scripted stub agent. No model was called, nothing was\n"
        "trained or measured, and every number on the dashboard is a placeholder.\n\n"
        f"Brief length: {len(brief)} characters.\n"
    )


def register() -> None:
    """Add ``scripted`` to the backend registry (idempotent)."""
    BACKENDS.setdefault(NAME, f"{__name__}:ScriptedBackend")


__all__ = ["NAME", "STEP_ENV", "ScriptedBackend", "register"]
