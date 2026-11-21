"""A test agent backend that runs a real Python script, for proving the runners.

``spec.prompts[0]`` is the script's source. Every line it prints becomes a
``text`` event as it is printed, a non-zero exit status a failed result, and
every file left in the workdir is listed in ``AgentResult.files``.
"""

from __future__ import annotations

import asyncio
import sys
import time
from typing import ClassVar

import pytest

from chipin_backend.agents.base import BACKENDS, AgentBackend
from chipin_backend.agents.types import AgentEvent, AgentResult, AgentSpec, EventSink


class ScriptBackend(AgentBackend):
    """Runs ``python -u -c <prompts[0]>`` in the workdir and streams its output."""

    name: ClassVar[str] = "script"
    _proc: asyncio.subprocess.Process | None = None

    async def run(self, spec: AgentSpec, sink: EventSink) -> AgentResult:
        """Run the script to its exit; its exit status decides ``failed``."""
        assert spec.workdir is not None
        started = time.monotonic()
        sink.emit(AgentEvent("agent_start", spec.name, {"backend": self.name}))
        self._proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-u",
            "-c",
            spec.prompts[0],
            cwd=spec.workdir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        assert self._proc.stdout is not None
        lines = []
        async for raw in self._proc.stdout:
            line = raw.decode().rstrip("\n")
            lines.append(line)
            sink.emit(AgentEvent("text", spec.name, {"text": line}))
        code = await self._proc.wait()
        files = sorted(str(p.relative_to(spec.workdir)) for p in spec.workdir.rglob("*") if p.is_file())
        sink.emit(AgentEvent("agent_end", spec.name, {"exit_status": code}))
        return AgentResult(
            agent=spec.name,
            final_text="\n".join(lines),
            failed=code != 0,
            error=f"exit status {code}" if code else None,
            duration_s=time.monotonic() - started,
            files=files,
        )

    async def close(self) -> None:
        """Kill the script if it is still running."""
        if self._proc is not None and self._proc.returncode is None:
            self._proc.kill()
            await self._proc.wait()


def use_script_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    """Register ``script`` in the backend registry for one test."""
    monkeypatch.setitem(BACKENDS, "script", "script_backend:ScriptBackend")
