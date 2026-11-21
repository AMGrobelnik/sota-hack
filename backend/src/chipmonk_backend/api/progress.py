"""The agent reports its own progress: a ``progress`` helper in its workspace.

The helper appends one JSON line per call to the run's ``progress.jsonl``::

    ./progress stage propose started [round]
    ./progress stage finetune skipped "no recordings attached"
    ./progress metric gates 2330 [unit]
    ./progress status "ChipIn is wiring the weights into gates"
    ./progress artifact report.md [file|report|chip]

:class:`ProgressTailer` reads new lines from that file and writes ``stage``,
``metric``, ``status`` and ``artifact`` events. A malformed line is skipped
with a warning; the helper itself rejects bad arguments with exit status 2,
so the agent learns at once.
"""

from __future__ import annotations

import asyncio
import json
import stat
import sys
from pathlib import Path
from typing import Any

from loguru import logger

from chipmonk_backend.api.events import STAGES, EventLog
from chipmonk_backend.api.translate import clip

PROGRESS_FILE = "progress.jsonl"
HELPER_NAME = "progress"
ARTIFACT_KINDS = ("file", "report", "chip")
STAGE_STATES = ("started", "done", "skipped")

_HELPER = '''\
"""ChipIn progress helper: tells the dashboard what this run is doing.

usage:
  ./progress stage <{stages}> <started|done> [round]
  ./progress stage <{stages}> skipped "<short reason>"
  ./progress metric <key> <number> [unit]
  ./progress status "<one present-tense line>"
  ./progress artifact <path in this folder> [{kinds}]
"""
import json, sys
from datetime import datetime, timezone

OUT = {out!r}
STAGES = {stages_t!r}
KINDS = {kinds_t!r}


def fail(msg):
    sys.stderr.write("progress: " + msg + "\\n" + __doc__)
    sys.exit(2)


a = sys.argv[1:]
if not a:
    fail("no command")
cmd, rest = a[0], a[1:]
line = {{"ts": datetime.now(timezone.utc).isoformat(), "type": cmd}}
if cmd == "stage":
    if len(rest) >= 2 and rest[1] == "skipped":
        reason = " ".join(rest[2:]).strip()
        if rest[0] not in STAGES or not reason:
            fail("a skipped stage needs a stage name and a reason")
        line.update(name=rest[0], state="skipped", reason=reason)
    elif len(rest) not in (2, 3) or rest[0] not in STAGES or rest[1] not in ("started", "done"):
        fail("stage needs a stage name and started|done|skipped")
    else:
        line.update(name=rest[0], state=rest[1])
    if len(rest) == 3 and rest[1] != "skipped":
        if not rest[2].isdigit():
            fail("round must be a whole number")
        line["round"] = int(rest[2])
elif cmd == "metric":
    if len(rest) not in (2, 3):
        fail("metric needs a key and a number")
    try:
        value = float(rest[1])
    except ValueError:
        fail("metric value must be a number")
    line.update(key=rest[0], value=int(value) if value.is_integer() else value)
    if len(rest) == 3:
        line["unit"] = rest[2]
elif cmd == "status":
    if not rest or not " ".join(rest).strip():
        fail("status needs a line of text")
    line["text"] = " ".join(rest)
elif cmd == "artifact":
    if len(rest) not in (1, 2) or (len(rest) == 2 and rest[1] not in KINDS):
        fail("artifact needs a path and optionally a kind")
    line.update(path=rest[0], kind=rest[1] if len(rest) == 2 else "file")
else:
    fail("unknown command " + repr(cmd))
with open(OUT, "a", encoding="utf-8") as handle:
    handle.write(json.dumps(line) + "\\n")
print("ok")
'''


def _interpreter() -> str:
    """The shebang interpreter: this Python, unless its path cannot sit in a shebang."""
    exe = sys.executable
    return exe if exe and " " not in exe else "/usr/bin/env python3"


def write_helper(workspace: Path, progress_file: Path) -> Path:
    """Write the executable ``progress`` helper into ``workspace``; returns its path."""
    source = _HELPER.format(
        out=str(progress_file),
        stages="|".join(STAGES),
        stages_t=STAGES,
        kinds="|".join(ARTIFACT_KINDS),
        kinds_t=ARTIFACT_KINDS,
    )
    helper = workspace / HELPER_NAME
    helper.write_text(f"#!{_interpreter()}\n{source}", encoding="utf-8")
    helper.chmod(helper.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return helper


class ProgressTailer:
    """Turns new lines of ``progress.jsonl`` into contract events."""

    def __init__(self, path: Path, log: EventLog, run_path: Path, workspace: Path) -> None:
        self.path = path
        self.log = log
        self.run_path = run_path
        self.workspace = workspace
        self._offset = 0
        self.artifacts: set[str] = set()

    async def follow(self, poll_s: float) -> None:
        """Read new lines every ``poll_s`` until cancelled."""
        while True:
            self.drain()
            await asyncio.sleep(poll_s)

    def drain(self) -> None:
        """Emit an event for every complete new line; a partial last line waits."""
        try:
            with self.path.open("rb") as handle:
                handle.seek(self._offset)
                chunk = handle.read()
        except FileNotFoundError:
            return
        except OSError as exc:
            logger.warning("run {}: cannot read {}: {}", self.log.run_id, self.path, exc)
            return
        end = chunk.rfind(b"\n")
        if end < 0:
            return
        self._offset += end + 1
        for raw in chunk[: end + 1].splitlines():
            if raw.strip():
                self._line(raw)

    def _line(self, raw: bytes) -> None:
        try:
            item = json.loads(raw)
            if not isinstance(item, dict):
                raise ValueError("not an object")
            self._emit(item)
        except (ValueError, TypeError, KeyError) as exc:
            logger.warning("run {}: bad progress line skipped ({}): {!r}", self.log.run_id, exc, raw[:200])

    def _emit(self, item: dict[str, Any]) -> None:
        kind = item.get("type")
        if kind == "stage":
            if item["name"] not in STAGES or item["state"] not in STAGE_STATES:
                raise ValueError("unknown stage or state")
            reason = str(item.get("reason") or "").strip()
            if item["state"] == "skipped" and not reason:
                raise ValueError("a skipped stage needs a reason")
            round_ = item.get("round")
            self.log.append(
                "stage",
                name=item["name"],
                stage=item["name"],
                state=item["state"],
                reason=clip(reason, 200) if item["state"] == "skipped" else None,
                round=int(round_) if round_ is not None else None,
            )
        elif kind == "metric":
            value = item["value"]
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise ValueError("metric value is not a number")
            self.log.append("metric", key=str(item["key"]), value=value, unit=item.get("unit"))
        elif kind == "status":
            self.log.append("status", text=clip(str(item["text"]), 200))
        elif kind == "artifact":
            self.add_artifact(str(item["path"]), str(item.get("kind", "file")))
        else:
            raise ValueError(f"unknown type {kind!r}")

    def add_artifact(self, path: str, kind: str) -> None:
        """Emit one ``artifact`` event for a workspace path (once per path)."""
        if kind not in ARTIFACT_KINDS:
            raise ValueError(f"unknown artifact kind {kind!r}")
        target = (self.workspace / path).resolve()
        try:
            rel = target.relative_to(self.run_path.resolve())
        except ValueError:
            raise ValueError(f"artifact {path!r} is outside the run folder") from None
        if str(rel) in self.artifacts:
            return
        self.artifacts.add(str(rel))
        self.log.append("artifact", name=target.name, kind=kind, path=str(rel))


__all__ = ["ARTIFACT_KINDS", "HELPER_NAME", "PROGRESS_FILE", "ProgressTailer", "write_helper"]
