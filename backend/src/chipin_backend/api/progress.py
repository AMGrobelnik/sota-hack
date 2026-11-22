"""The agent reports its own progress: a ``progress`` helper in its workspace.

The helper appends one JSON line per call to the run's ``progress.jsonl``::

    ./progress stage propose started [round]
    ./progress stage finetune skipped "no recordings attached"
    ./progress metric gates 2330 [unit] [--chip <design_id>]
    ./progress chosen <design_id>
    ./progress status "ChipIn is wiring the weights into gates"
    ./progress artifact report.md [file|report|chip]

:class:`ProgressTailer` reads new lines from that file and writes ``stage``,
``metric``, ``chosen``, ``status`` and ``artifact`` events. A metric's
optional ``chip`` names the design it measures (for the chip lab's own untagged
metrics, the design its latest status line names; see :data:`LAB_DESIGN_METRICS`);
``chosen`` names the run's chosen chip, and a later one replaces an earlier one. A
malformed line is skipped
with a warning; the helper itself rejects bad arguments with exit status 2,
so the agent learns at once.
"""

from __future__ import annotations

import asyncio
import json
import math
import re
import stat
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from loguru import logger

from chipin_backend.api.events import STAGES, EventLog
from chipin_backend.api.translate import clip

PROGRESS_FILE = "progress.jsonl"
HELPER_NAME = "progress"
ARTIFACT_KINDS = ("file", "report", "chip")
STAGE_STATES = ("started", "done", "skipped")

#: The chip lab reports through this helper by itself, without ``--chip``: before a tool
#: about one design it writes a status line naming it ("ChipIn is synthesising chip
#: <design_id>", its ``VERB`` table), then that tool's metrics. These are the lab's metric
#: keys about one design and the unit it always sends with each (its ``METRIC_KEYS`` less
#: the batch counts ``candidates`` and ``best_gates``). An untagged metric with such a key
#: and unit takes the design of the lab's latest status line; a lab status line about no
#: one design (a batch, an import) clears it, so a metric about no design stays untagged.
#: The agent's own status lines change nothing.
LAB_DESIGN_METRICS: dict[str, str] = {
    "gates": "gates",
    "depth": "gates",
    "transistors": "transistors",
    "luts_ice40": "LUT4",
    "luts_xc7": "LUT6",
    "area_um2": "um2",
    "ge": "GE",
    "tt_tiles": "tiles",
    "cost_eur": "EUR",
    "vectors_checked": "vectors",
    "mismatches": "vectors",
    "verification_level": "level",
    "timing_slack_ns": "ns",
    "fmax_mhz": "MHz",
    "energy_pj": "pJ",
    "leakage_uw": "uW",
    "power_uw_at_rate": "uW",
}
#: The lab's status lines (its ``VERB`` table, after "ChipIn is" or "ChipIn <went wrong> while").
_LAB_LEAD = r"^ChipIn (?:is|(?:found a problem|ran out of time|hit an error|stopped) while) "
_LAB_DESIGN = re.compile(
    _LAB_LEAD + r"(?:synthesising|counting LUTs for|mapping|checking|proving|proving the clocked|"
    r"simulating the streaming|laying out|timing|building an FPGA bitstream for|packaging|"
    r"writing the report for|measuring gate activity of) chip(?: (\w[\w.-]*))?\b"
)
_LAB_NO_DESIGN = re.compile(
    _LAB_LEAD + r"(?:bringing a model in|compiling a design|composing a multi-head chip|"
    r"checking submitted Verilog|ranking candidate chips|synthesising candidate chips)\s*$"
)

_HELPER = '''\
"""ChipIn progress helper: tells the dashboard what this run is doing.

usage:
  ./progress stage <{stages}> <started|done> [round]
  ./progress stage <{stages}> skipped "<short reason>"
  ./progress metric <key> <number> [unit] [--chip <design_id>]
  ./progress chosen <design_id>
  ./progress status "<one present-tense line>"
  ./progress artifact <path in this folder> [{kinds}]
"""
import json, math, sys
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
    chip = None
    if "--chip" in rest[2:]:
        at = rest.index("--chip", 2)
        if at + 1 >= len(rest) or not rest[at + 1].strip() or rest[at + 1].startswith("--"):
            fail("--chip needs a design id")
        chip = rest[at + 1]
        rest = rest[:at] + rest[at + 2:]
    if len(rest) not in (2, 3) or any(arg.startswith("--") for arg in rest):
        fail("metric needs a key and a number")
    try:
        value = float(rest[1])
    except ValueError:
        fail("metric value must be a number")
    if not math.isfinite(value):
        fail("metric value must be a finite number")
    line.update(key=rest[0], value=int(value) if value.is_integer() else value)
    if len(rest) == 3:
        line["unit"] = rest[2]
    if chip is not None:
        line["chip"] = chip
elif cmd == "chosen":
    if len(rest) != 1 or not rest[0].strip() or rest[0].startswith("--"):
        fail("chosen needs one design id")
    line["chip"] = rest[0]
elif cmd == "status":
    if not rest or not " ".join(rest).strip():
        fail("status needs a line of text")
    line["text"] = " ".join(rest)
elif cmd == "artifact":
    if len(rest) not in (1, 2):
        fail("artifact needs a path and optionally a kind")
    if len(rest) == 2 and rest[1] not in KINDS:
        fail("unknown artifact kind " + repr(rest[1]) + "; use one of {kinds}")
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


#: Added to a subagent's helper: the orchestrator owns the stages and the chosen chip.
_SUBAGENT_REFUSAL = """\
if cmd in ("stage", "chosen"):
    sys.stderr.write("progress: a subagent does not mark stages or the chosen chip; "
                     "the orchestrator does. Report your numbers with metric ... --chip <design_id>.\\n")
    sys.exit(2)
"""
_DISPATCH = 'line = {"ts": datetime.now(timezone.utc).isoformat(), "type": cmd}\n'
#: Added to a fan-out orchestrator's helper: a subagent that calls it (a lab tool run from the
#: orchestrator's folder finds it in its working folder) is passed to the subagent's own helper,
#: so its lines carry its id and it cannot mark the orchestrator's stages.
_REDIRECT = """\
import os
_sub = os.environ.get("CHIPIN_SUBAGENT_ID", "")
if _sub:
    _own = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agents", _sub, "progress")
    if _sub[:1] == "a" and _sub[1:].isdigit() and os.path.isfile(_own):
        os.execv(_own, [_own] + sys.argv[1:])
    sys.stderr.write("progress: a subagent reports through its own ./progress\\n")
    sys.exit(2)
"""
_ARGS = "a = sys.argv[1:]\n"


def write_helper(
    workspace: Path, progress_file: Path, *, subagent: bool = False, orchestrator: bool = False
) -> Path:
    """Write the executable ``progress`` helper into ``workspace``; returns its path.

    ``subagent``: the helper refuses ``stage`` and ``chosen`` (exit 2).
    ``orchestrator`` (fan-out on): a call from a subagent's environment goes to
    that subagent's own helper.
    """
    source = _HELPER.format(
        out=str(progress_file),
        stages="|".join(STAGES),
        stages_t=STAGES,
        kinds="|".join(ARTIFACT_KINDS),
        kinds_t=ARTIFACT_KINDS,
    )
    if subagent:
        source = source.replace(_DISPATCH, _SUBAGENT_REFUSAL + _DISPATCH, 1)
    if orchestrator:
        source = source.replace(_ARGS, _REDIRECT + _ARGS, 1)
    helper = workspace / HELPER_NAME
    helper.write_text(f"#!{_interpreter()}\n{source}", encoding="utf-8")
    helper.chmod(helper.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return helper


class ProgressTailer:
    """Turns new lines of ``progress.jsonl`` into contract events."""

    def __init__(
        self,
        path: Path,
        log: EventLog,
        run_path: Path,
        workspace: Path,
        *,
        marks: bool = True,
        on_stage: Callable[[str, str], None] | None = None,
    ) -> None:
        self.path = path
        self.log = log
        self.run_path = run_path
        self.workspace = workspace
        #: False for a subagent: ``stage`` and ``chosen`` lines are skipped.
        self.marks = marks
        #: Called with ``(stage, state)`` before each ``stage`` event (fan-out closes merged stages).
        self.on_stage = on_stage
        self._offset = 0
        self.artifacts: set[str] = set()
        #: The design the lab's latest status line names (``None``: none); see :data:`LAB_DESIGN_METRICS`.
        self.lab_design: str | None = None

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
        if kind in ("stage", "chosen") and not self.marks:
            raise ValueError(f"a subagent does not mark {kind}")
        if kind == "stage":
            if item["name"] not in STAGES or item["state"] not in STAGE_STATES:
                raise ValueError("unknown stage or state")
            reason = str(item.get("reason") or "").strip()
            if item["state"] == "skipped" and not reason:
                raise ValueError("a skipped stage needs a reason")
            round_ = item.get("round")
            if self.on_stage is not None:
                self.on_stage(item["name"], item["state"])
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
            if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
                raise ValueError("metric value is not a finite number")
            key = str(item["key"])
            chip = item.get("chip")
            if chip is not None:
                chip = _chip(chip)
            elif key in LAB_DESIGN_METRICS and item.get("unit") == LAB_DESIGN_METRICS[key]:
                chip = self.lab_design
            self.log.append("metric", key=key, value=value, unit=item.get("unit"), chip=chip)
        elif kind == "chosen":
            self.log.append("chosen", chip=_chip(item["chip"]))
        elif kind == "status":
            text = str(item["text"])
            if found := _LAB_DESIGN.match(text):
                self.lab_design = clip(found.group(1), 200) if found.group(1) else None
            elif _LAB_NO_DESIGN.match(text):
                self.lab_design = None
            self.log.append("status", text=clip(text, 200))
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


def _chip(value: object) -> str:
    """A design id from a progress line: a non-empty string."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("chip must be a non-empty design id")
    return clip(value.strip(), 200)


__all__ = ["ARTIFACT_KINDS", "HELPER_NAME", "PROGRESS_FILE", "ProgressTailer", "write_helper"]
