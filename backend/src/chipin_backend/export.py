"""Export a recorded run as ONE static JSON file, so a public page can play it back without a server.

``chipin-backend export <run> --out <file> [--index <index.json>]`` reads a run
folder (``api.json`` or ``run.json``, ``events.jsonl``, the agent's files) and
writes::

    {"format": "chipin-recorded-run", "version": 1, "exported_at": ...,
     "run": {facts as GET /api/history gives them}, "summary": ..., "bullets": ...,
     "events": [...every event with its seq and ts, summary events included...],
     "files": [{"path", "size", "text", "truncated"}],   # small text artifacts the page shows
     "redactions": {"home_paths": n, "keys": n, "emails": n, "host": n, "user": n}}

Everything written is scrubbed first: home folder paths become ``~``, anything
that looks like a key or token and every e-mail address is replaced by
``[removed]``, and this machine's host and user names are replaced too, in
summary lines as in every other event. Summaries written after the run by
``chipin-backend summarise`` (``summaries.jsonl``) follow its events. The
file is size-bounded: long tool details go first, then artifacts, and an
export that still does not fit is refused.
"""

from __future__ import annotations

import getpass
import json
import re
import socket
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from loguru import logger

from chipin_backend.api.history import run_facts, with_summaries
from chipin_backend.api.summaries import SUMMARIES_FILE, read_jsonl

FORMAT = "chipin-recorded-run"
VERSION = 1
REMOVED = "[removed]"
#: Default bound on the whole file, and on each artifact's text.
MAX_BYTES = 1_500_000
ARTIFACT_MAX_BYTES = 64_000
#: Longest string kept in an event once the file has to shrink.
SHRUNK_TEXT = 600
TEXT_SUFFIXES = frozenset({".md", ".txt", ".json", ".csv", ".yaml", ".yml", ".v", ".log", ".tsv"})

#: Key and token shapes of the services a run can touch, and generic ``name=value`` secrets.
KEY_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p)
    for p in (
        r"sk-(?:or-v1-|ant-|proj-)?[A-Za-z0-9_\-]{16,}",
        r"\bgh[pousr]_[A-Za-z0-9]{20,}",
        r"\bgithub_pat_[A-Za-z0-9_]{20,}",
        r"\bAKIA[0-9A-Z]{16}\b",
        r"\bhf_[A-Za-z0-9]{20,}",
        r"\bxox[abprs]-[A-Za-z0-9-]{10,}",
        r"\brpa_[A-Za-z0-9]{20,}",
        r"\bAIza[0-9A-Za-z_\-]{30,}",
        r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}",
        r"(?i)\bbearer\s+[A-Za-z0-9._\-]{16,}",
    )
)
SECRET_ASSIGN = re.compile(
    r"(?i)\b((?:[a-z0-9]+_)*(?:token|api_?key|apikey|secret|password|passwd))(\"?'?\s*[:=]\s*[\"']?)([A-Za-z0-9._\-/+]{8,})"
)
EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}")
HOME_GENERIC = re.compile(r"(?:/Users|/home)/[^/\s\"'`:;,)]+")


@dataclass
class Scrubber:
    """Replaces home paths, keys, e-mail addresses, host and user names in strings; counts each."""

    home: str = field(default_factory=lambda: str(Path.home()))
    host_names: tuple[str, ...] = field(default_factory=lambda: _host_names())
    user: str = field(default_factory=lambda: _user_name())
    counts: dict[str, int] = field(
        default_factory=lambda: {"home_paths": 0, "keys": 0, "emails": 0, "host": 0, "user": 0}
    )

    def _sub(
        self, pattern: re.Pattern[str], repl: str | Callable[[re.Match[str]], str], text: str, key: str
    ) -> str:
        out, n = pattern.subn(repl, text)
        self.counts[key] += n
        return out

    def text(self, value: str) -> str:
        """``value`` with every private detail replaced."""
        out = value
        if self.home and self.home != "/":
            n = out.count(self.home)
            if n:
                out = out.replace(self.home, "~")
                self.counts["home_paths"] += n
        out = self._sub(HOME_GENERIC, "~", out, "home_paths")
        for pattern in KEY_PATTERNS:
            out = self._sub(pattern, REMOVED, out, "keys")
        out = self._sub(SECRET_ASSIGN, lambda m: f"{m.group(1)}{m.group(2)}{REMOVED}", out, "keys")
        out = self._sub(EMAIL, REMOVED, out, "emails")
        for host in self.host_names:
            out = self._sub(re.compile(rf"\b{re.escape(host)}\b", re.IGNORECASE), "[host]", out, "host")
        if self.user:
            out = self._sub(re.compile(rf"\b{re.escape(self.user)}\b"), "[user]", out, "user")
        return out

    def value(self, data: Any) -> Any:
        """``data`` (any JSON value) with every string scrubbed, keys of objects included."""
        if isinstance(data, str):
            return self.text(data)
        if isinstance(data, list):
            return [self.value(v) for v in data]
        if isinstance(data, dict):
            return {self.text(str(k)): self.value(v) for k, v in data.items()}
        return data


def _host_names() -> tuple[str, ...]:
    try:
        full = socket.gethostname()
    except OSError:
        return ()
    names = {full, full.split(".")[0]}
    return tuple(sorted((n for n in names if len(n) >= 4), key=len, reverse=True))


def _user_name() -> str:
    try:
        name = getpass.getuser()
    except (OSError, KeyError):
        return ""
    return name if len(name) >= 4 else ""


class ExportError(ValueError):
    """The run cannot be exported (missing folder or events, or too large)."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("{}: unreadable ({})", path.name, exc)
        return {}
    return data if isinstance(data, dict) else {}


def _read_events(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("{}: skipping an unreadable event line", path)
                continue
            if isinstance(ev, dict) and "ts" in ev and "type" in ev:
                events.append(ev)
    return events


def _record(folder: Path, events: list[dict[str, Any]]) -> dict[str, Any]:
    """The dashboard record (``api.json``), else the fields ``run.json`` has."""
    api = folder / "api.json"
    if api.is_file():
        return _read_json(api)
    rec = _read_json(folder / "run.json")
    started = next((e for e in events if e.get("type") == "run.started"), {})
    return {
        "id": folder.name,
        "prompt": started.get("prompt") or "",
        "status": rec.get("status"),
        "started_at": rec.get("started_at") or rec.get("created_at"),
        "finished_at": rec.get("finished_at"),
        "agent": started.get("agent"),
    }


def _artifact_files(folder: Path, events: list[dict[str, Any]], per_file: int) -> list[dict[str, Any]]:
    """Text artifacts named by ``artifact`` events, report first, each cut at ``per_file`` bytes."""
    seen: dict[str, str] = {}
    for ev in events:
        if ev.get("type") == "artifact" and isinstance(ev.get("path"), str):
            seen.setdefault(ev["path"], str(ev.get("kind") or ""))
    workspace = (folder / "workspace").resolve()
    files: list[dict[str, Any]] = []
    for rel, kind in seen.items():
        target = (folder / rel).resolve()
        if (
            not target.is_relative_to(workspace)
            or not target.is_file()
            or target.suffix.lower() not in TEXT_SUFFIXES
        ):
            continue
        raw = target.read_bytes()
        cut = len(raw) > per_file
        files.append(
            {
                "path": rel,
                "kind": kind,
                "size": len(raw),
                "text": raw[:per_file].decode("utf-8", errors="replace"),
                "truncated": cut,
            }
        )
    files.sort(key=lambda f: (f["kind"] != "report", not f["path"].endswith(".md"), f["size"]))
    return files


def _size(doc: dict[str, Any]) -> int:
    return len(json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def _shrink_events(events: list[dict[str, Any]]) -> None:
    """Drop tool details and cut long strings, in place: the first thing to go when over size."""

    def cut(v: Any) -> Any:
        if isinstance(v, str) and len(v) > SHRUNK_TEXT:
            return v[: SHRUNK_TEXT - 1] + "…"
        if isinstance(v, list):
            return [cut(x) for x in v]
        if isinstance(v, dict):
            return {k: cut(x) for k, x in v.items()}
        return v

    for i, ev in enumerate(events):
        if ev.get("type") == "tool":
            ev.pop("detail", None)
        if ev.get("type") in ("design", "evidence"):
            continue  # the page's numbers: never cut
        events[i] = {k: (v if k in ("ts", "type", "seq", "run_id") else cut(v)) for k, v in ev.items()}


def build_export(
    folder: Path,
    *,
    max_bytes: int = MAX_BYTES,
    artifact_max_bytes: int = ARTIFACT_MAX_BYTES,
    scrubber: Scrubber | None = None,
) -> dict[str, Any]:
    """The export document of the run in ``folder``; ``ExportError`` if it cannot be made."""
    events_path = folder / "events.jsonl"
    if not events_path.is_file():
        raise ExportError(f"no events.jsonl in {folder.name}")
    events = _read_events(events_path)
    if not events:
        raise ExportError(f"{folder.name} has no events")
    events = with_summaries(events, read_jsonl(folder / SUMMARIES_FILE))
    record = _record(folder, events)
    scrub = scrubber or Scrubber()
    doc: dict[str, Any] = {
        "format": FORMAT,
        "version": VERSION,
        "exported_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "run": scrub.value(run_facts(record, events)),
        "summary": scrub.value(record.get("summary")),
        "bullets": scrub.value(record.get("bullets")),
        "events": scrub.value(events),
        "files": scrub.value(_artifact_files(folder, events, artifact_max_bytes)),
    }
    if _size(doc) > max_bytes:
        _shrink_events(doc["events"])
    while _size(doc) > max_bytes and doc["files"]:
        doc["files"].pop()  # largest, least wanted last
    if _size(doc) > max_bytes:
        raise ExportError(f"{folder.name} does not fit in {max_bytes} bytes even without its files")
    doc["redactions"] = dict(scrub.counts)
    return doc


def index_entry(doc: dict[str, Any], file_name: str) -> dict[str, Any]:
    """The run's line in an index of exported runs."""
    run = doc["run"]
    keys = (
        "id",
        "title",
        "started_at",
        "finished_at",
        "duration_s",
        "state",
        "preset",
        "agent",
        "model",
        "chosen",
        "counts",
    )
    return {**{k: run[k] for k in keys if k in run}, "file": file_name, "source": "recorded"}


def update_index(index_path: Path, entry: dict[str, Any]) -> list[dict[str, Any]]:
    """Add or replace ``entry`` (by id) in the index file, newest first; returns the list."""
    runs: list[dict[str, Any]] = []
    if index_path.is_file():
        data = _read_json(index_path)
        runs = [r for r in data.get("runs", []) if isinstance(r, dict) and r.get("id") != entry["id"]]
    runs.append(entry)
    runs.sort(key=lambda r: (str(r.get("started_at") or ""), str(r.get("id"))), reverse=True)
    index_path.write_text(
        json.dumps(
            {"format": "chipin-recorded-runs", "version": VERSION, "runs": runs}, indent=1, ensure_ascii=False
        )
        + "\n",
        encoding="utf-8",
    )
    return runs


def export_run(
    folder: Path,
    out: Path,
    *,
    index: Path | None = None,
    max_bytes: int = MAX_BYTES,
    artifact_max_bytes: int = ARTIFACT_MAX_BYTES,
) -> dict[str, Any]:
    """Write the export of ``folder`` to ``out`` (and its line into ``index``); returns a short report."""
    doc = build_export(folder, max_bytes=max_bytes, artifact_max_bytes=artifact_max_bytes)
    text = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text + "\n", encoding="utf-8")
    if index is not None:
        try:
            name = str(out.resolve().relative_to(index.resolve().parent))
        except ValueError:
            name = out.name
        update_index(index, index_entry(doc, name))
    return {
        "id": doc["run"].get("id"),
        "out": out.name,
        "bytes": len(text.encode("utf-8")) + 1,
        "events": len(doc["events"]),
        "files": len(doc["files"]),
        "redactions": doc["redactions"],
    }


__all__ = [
    "ARTIFACT_MAX_BYTES",
    "FORMAT",
    "MAX_BYTES",
    "ExportError",
    "Scrubber",
    "build_export",
    "export_run",
    "index_entry",
    "update_index",
]
