"""``scripted`` backend: a believable ChipIn run with no model and no paid call.

For tests and for building the dashboards. It walks the seven stages, calls
the run's real ``./progress`` helper for every stage, metric and status (so
the helper -> ``progress.jsonl`` -> event path is exercised), emits text and
tool events like a real agent, answers injected user messages (reporting each
delivery, and noting each one in ``report.md`` as a change made on request),
answers a follow-up (``spec.resume_session``) in the same folder, and writes a
``report.md``. Every number it reports is a labelled placeholder.
Pause between steps: ``spec.env["CHIPIN_STUB_STEP_S"]`` seconds.

Scripts, for tests of fan-out: when the last prompt holds lines that start
with ``$ ``, the stub runs only those, in order, as shell commands in its
folder (shown as ``Bash`` tool calls); a command that exits non-zero ends
the run as failed, and the last ``# cost <usd>`` in the prompt (a shell
comment at the end of a script line will do) sets the cost it reports.
Without a script, a stub subagent (``CHIPIN_SUBAGENT_ID`` set) holds for a
moment (five steps, at least 1.5 s, so a whole batch is seen running at
once), reports one placeholder metric and a result; a stub orchestrator
(``./subagent`` in its folder) runs each batch stage as one batch: it starts
the batch size its instructions name, all at once, waits for the batch,
merges it keeping the first subagent that finished ``done``, then marks the
stage done. Every shell command runs in its own process group, killed as a
whole when the agent is cancelled.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import re
import signal
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any, ClassVar

from chipin_backend.agents.base import BACKENDS, AgentBackend
from chipin_backend.agents.mailbox import InjectMailbox
from chipin_backend.agents.types import AgentEvent, AgentResult, AgentSpec, EventSink
from chipin_backend.config import AgentsConfig

NAME = "scripted"
STEP_ENV = "CHIPIN_STUB_STEP_S"
#: Where the stub notes each user message it acted on (its "change"); copied into report.md.
CHANGES_FILE = "requested_changes.md"
#: Set for subagents (``chipin_backend.api.fanout.ID_ENV``).
SUBAGENT_ENV = "CHIPIN_SUBAGENT_ID"
_COST = re.compile(r"# cost (\d+(?:\.\d+)?)")
_WIDTH = re.compile(r"ONE BATCH of (\d+) subagents")
_DONE = re.compile(r"^== (a\d+) .*: done", re.MULTILINE)
#: The stages a stub orchestrator runs as batches (``chipin_backend.api.fanout.BATCH_STAGES``).
_BATCH_STAGES = ("reference", "propose", "finetune", "compile", "verify")

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
        self._sink: EventSink | None = None
        self._agent = "chipin"

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
        self._sink, self._agent = sink, spec.name
        self._mailbox.open()

        def say(text: str) -> None:
            sink.emit(AgentEvent("text", spec.name, {"text": text}))

        if spec.resume_session:
            try:
                return await self._follow_up(spec, sink, say, step_s, started)
            finally:
                self._mailbox.close()
        try:
            sink.emit(AgentEvent("agent_start", spec.name, {"backend": NAME, "model": None}))
            script = _script(spec)
            if script or spec.env.get(SUBAGENT_ENV):
                return await self._script(spec, sink, script, started)
            say("This is the scripted stub agent: no model is called and every number is a placeholder.")
            await self._tool(sink, spec.name, "Read", {"file_path": str(workdir / "brief.md")}, "brief")
            for stage, status, text, metrics in _PLAN:
                await self._answer_messages(say, workdir)
                await self._progress(sink, spec.name, workdir, "stage", stage, "started")
                await self._progress(sink, spec.name, workdir, "status", status)
                await asyncio.sleep(step_s)
                if stage == "spec":
                    await self._write(sink, spec.name, workdir / "spec.md", "# Spec (stub)\n")
                if stage == "report":
                    await self._write(sink, spec.name, workdir / "report.md", _report(spec))
                    await self._progress(sink, spec.name, workdir, "artifact", "report.md", "report")
                if stage in _BATCH_STAGES and (workdir / "subagent").is_file():
                    await self._batch(spec, sink, stage)
                for key, value in metrics:
                    await self._progress(sink, spec.name, workdir, "metric", key, str(value))
                say(f"{text} (stub)")
                await self._progress(sink, spec.name, workdir, "stage", stage, "done")
            await self._answer_messages(say, workdir)
            summary = "Stub run complete: seven stages walked, placeholder numbers only."
            say(summary)
            sink.emit(AgentEvent("cost", spec.name, {"usd": 0.0, "input_tokens": 0, "output_tokens": 0}))
            duration = time.monotonic() - started
            sink.emit(AgentEvent("agent_end", spec.name, {"failed": False, "duration_s": duration}))
            return AgentResult(
                agent=spec.name,
                final_text=summary,
                session_id=f"stub-{uuid.uuid4()}",
                duration_s=duration,
                files=["spec.md", "report.md"],
            )
        finally:
            self._mailbox.close()

    async def _follow_up(
        self,
        spec: AgentSpec,
        sink: EventSink,
        say: Callable[[str], None],
        step_s: float,
        started: float,
    ) -> AgentResult:
        """Answer a follow-up prompt in the same folder, then any message sent meanwhile."""
        assert spec.workdir is not None
        sink.emit(AgentEvent("agent_start", spec.name, {"backend": NAME, "model": None}))
        question = spec.prompts[-1].strip() if spec.prompts else ""
        await asyncio.sleep(step_s)
        await self._answer_messages(say, spec.workdir)
        answer = f"Follow-up answer (stub): {question[-200:]}"
        say(answer)
        await self._answer_messages(say, spec.workdir)
        sink.emit(AgentEvent("cost", spec.name, {"usd": 0.0, "input_tokens": 0, "output_tokens": 0}))
        duration = time.monotonic() - started
        sink.emit(AgentEvent("agent_end", spec.name, {"failed": False, "duration_s": duration}))
        return AgentResult(
            agent=spec.name, final_text=answer, session_id=spec.resume_session, duration_s=duration
        )

    async def _script(
        self, spec: AgentSpec, sink: EventSink, script: list[str], started: float
    ) -> AgentResult:
        """Run the prompt's ``$ `` lines (a stub subagent without one gets a default script)."""
        assert spec.workdir is not None
        if not script:
            design = f"stub-{spec.env[SUBAGENT_ENV]}"
            hold = max(1.5, 5 * float(spec.env.get(STEP_ENV, "0.4")))
            script = [
                f'./progress status "Stub subagent {spec.env[SUBAGENT_ENV]} is trying its strategy"',
                f"sleep {hold:g}",
                f"./progress metric gates 1000 gates --chip {design}",
                f"echo 'Stub result: design {design}, 1000 gates (placeholder).'",
            ]
        error, output = None, ""
        for line in script:
            code, output = await self._shell(sink, spec, line)
            if code != 0:
                error = f"command failed with exit status {code}: {line}"
                break
        text = output.strip() or "Stub script done."
        sink.emit(AgentEvent("text", spec.name, {"text": text}))
        costs = _COST.findall(spec.prompts[-1] if spec.prompts else "")
        usd = float(costs[-1]) if costs else 0.0  # the last one: an orchestrator's briefs hold theirs
        sink.emit(AgentEvent("cost", spec.name, {"usd": usd, "input_tokens": 0, "output_tokens": 0}))
        if error:
            sink.emit(AgentEvent("error", spec.name, {"message": error}))
        duration = time.monotonic() - started
        sink.emit(AgentEvent("agent_end", spec.name, {"failed": error is not None, "duration_s": duration}))
        return AgentResult(
            agent=spec.name,
            final_text=text,
            failed=error is not None,
            error=error,
            cost_usd=usd,
            duration_s=duration,
        )

    async def _batch(self, spec: AgentSpec, sink: EventSink, stage: str) -> None:
        """One batch stage of a stub orchestrator: start all, wait for all, merge."""
        match = _WIDTH.search(spec.system_prompt or "")
        width = int(match.group(1)) if match else 3
        starts = " ".join(
            f'./subagent start {stage} "Stub strategy {n} for {stage}" --name {stage}-{n} >/dev/null 2>&1 &'
            for n in range(1, width + 1)
        )
        await self._shell(sink, spec, f"{starts} wait")
        output = ""
        for _ in range(100):
            code, output = await self._shell(sink, spec, f"./subagent wait --stage {stage}")
            if code != 0 or "Still running" not in output:
                break
        done = _DONE.findall(output)
        kept = done[0] if done else "none"
        await self._shell(
            sink, spec, f'./subagent merge {stage} --kept {kept} --why "stub: kept the first one done"'
        )

    async def _shell(self, sink: EventSink, spec: AgentSpec, command: str) -> tuple[int, str]:
        """Run one shell command in the workdir, shown as a ``Bash`` tool call."""
        self._calls += 1
        call_id = f"stub-{self._calls}"
        sink.emit(
            AgentEvent(
                "tool_call", spec.name, {"tool": "Bash", "input": {"command": command}, "call_id": call_id}
            )
        )
        proc = await asyncio.create_subprocess_exec(
            "/bin/sh",
            "-c",
            command,
            cwd=spec.workdir,
            env={**os.environ, **spec.env},
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            out, _ = await proc.communicate()
        except asyncio.CancelledError:
            # The whole group: a shell's children (a sleep, a pipeline) go with it.
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(proc.pid, signal.SIGKILL)
            await proc.wait()
            raise
        text = out.decode(errors="replace")
        code = proc.returncode or 0
        sink.emit(
            AgentEvent("tool_result", spec.name, {"call_id": call_id, "output": text, "is_error": code != 0})
        )
        return code, text

    async def _answer_messages(self, say: Callable[[str], None], workdir: Path | None = None) -> None:
        """Report each waiting message delivered, answer it and note it in ``report.md``."""
        for message in self._mailbox.drain():
            if self._sink is not None:
                data = {"message": "Your message reached the agent", "user_message_delivered": True}
                self._sink.emit(AgentEvent("status", self._agent, data))
            say(f"Noted your message: {message.strip()} (stub: noted in report.md)")
            if workdir is not None:
                with (workdir / CHANGES_FILE).open("a", encoding="utf-8") as handle:
                    handle.write(f"- {' '.join(message.split())}\n")

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


def _script(spec: AgentSpec) -> list[str]:
    """The ``$ `` lines of the last prompt, without the ``$ ``."""
    prompt = spec.prompts[-1] if spec.prompts else ""
    return [line[2:].strip() for line in prompt.splitlines() if line.startswith("$ ") and line[2:].strip()]


def _report(spec: AgentSpec) -> str:
    brief = spec.prompts[-1] if spec.prompts else ""
    changes = spec.workdir / CHANGES_FILE if spec.workdir is not None else None
    asked = changes.read_text(encoding="utf-8") if changes is not None and changes.is_file() else ""
    return (
        "# ChipIn report (stub run)\n\n"
        "This run used the scripted stub agent. No model was called, nothing was\n"
        "trained or measured, and every number on the dashboard is a placeholder.\n\n"
        f"Brief length: {len(brief)} characters.\n" + (f"\n## Changed on request\n\n{asked}" if asked else "")
    )


def register() -> None:
    """Add ``scripted`` to the backend registry (idempotent)."""
    BACKENDS.setdefault(NAME, f"{__name__}:ScriptedBackend")


__all__ = ["NAME", "STEP_ENV", "ScriptedBackend", "register"]
