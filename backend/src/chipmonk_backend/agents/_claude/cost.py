"""Parsing the CLI's ``/cost`` dialog, and token totals from the transcript.

Adapted from AI Inventor.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[()][AB012]|\x1b[=>]")
_NUM = r"(\d+(?:\.\d+)?)"
_COUNT_RE = re.compile(r"(\d+(?:\.\d+)?)([kKmM]?)\b")
#: One "Usage by model" row. Spaces are optional: the TUI often draws them as
#: cursor moves, which leave nothing behind once escapes are stripped.
_PER_MODEL_RE = re.compile(
    r"(claude-[a-z0-9.-]+)\s*:\s*"
    r"([0-9.kmKM]+)\s*input,\s*"
    r"([0-9.kmKM]+)\s*output,\s*"
    r"([0-9.kmKM]+)\s*cache\s*read,\s*"
    r"([0-9.kmKM]+)\s*cache\s*write"
    r"[^()\n]*"
    r"(?:\(\$" + _NUM + r"\))?",
    re.IGNORECASE,
)
#: The session total; newer CLIs label it "Estimated cost".
_TOTAL_RE = re.compile(r"(?:Total|Estimated)\s*cost:\s*\$" + _NUM)


def strip_ansi(text: str) -> str:
    """``text`` without ANSI escapes, carriage returns or bells."""
    return _ANSI_RE.sub("", text).replace("\r", "").replace("\x07", "")


def _token_count(text: str) -> int:
    """``54.0k`` / ``5.7m`` / ``717`` as an integer."""
    m = _COUNT_RE.fullmatch(text.strip())
    if not m:
        return int(re.sub(r"[^\d]", "", text) or "0")
    scale = {"k": 1_000, "m": 1_000_000}.get(m.group(2).lower(), 1)
    return int(float(m.group(1)) * scale)


@dataclass(frozen=True)
class CostReport:
    """What ``/cost`` showed: the session's dollar total and token counts."""

    usd: float = 0.0
    read: bool = False  # a total (or per-model rows) was found
    input_tokens: int = 0
    output_tokens: int = 0


def parse_cost_output(raw: str) -> CostReport:
    """Parse captured ``/cost`` output (ANSI allowed).

    The total is ``Total cost: $N`` (``Estimated cost`` on newer CLIs),
    falling back to the sum of the per-model rows when a lossy capture dropped
    the label. Input tokens include cache reads and writes.
    """
    text = strip_ansi(raw)
    usd, read = 0.0, False
    if m := _TOTAL_RE.search(text):
        usd, read = float(m.group(1)), True
    rows = {m.group(1): m for m in _PER_MODEL_RE.finditer(text)}
    if not read and rows:
        usd, read = sum(float(m.group(6) or 0.0) for m in rows.values()), True
    input_tokens = sum(
        _token_count(m.group(2)) + _token_count(m.group(4)) + _token_count(m.group(5)) for m in rows.values()
    )
    output_tokens = sum(_token_count(m.group(3)) for m in rows.values())
    return CostReport(usd=usd, read=read, input_tokens=input_tokens, output_tokens=output_tokens)


def cost_from_state(record: dict[str, Any]) -> CostReport | None:
    """The session totals from a transcript ``cost-state`` record (written as the CLI exits)."""
    if record.get("type") != "cost-state" or not isinstance(record.get("totalCostUSD"), int | float):
        return None
    models = record.get("modelUsage") or {}
    usage = [m for m in models.values() if isinstance(m, dict)]
    input_keys = ("inputTokens", "cacheReadInputTokens", "cacheCreationInputTokens")
    return CostReport(
        usd=float(record["totalCostUSD"]),
        read=True,
        input_tokens=sum(int(m.get(k) or 0) for m in usage for k in input_keys),
        output_tokens=sum(int(m.get("outputTokens") or 0) for m in usage),
    )


class TranscriptUsage:
    """Token totals summed from the transcript's assistant records.

    The CLI writes one record per content block, each repeating its message's
    ``usage``, so every message id is counted once.
    """

    def __init__(self) -> None:
        self.input_tokens = 0
        self.output_tokens = 0
        self._seen: set[str] = set()

    def add(self, record: dict[str, Any]) -> None:
        """Count ``record``'s usage if it is an assistant message not seen yet."""
        if record.get("type") != "assistant" or record.get("isApiErrorMessage"):
            return
        message = record.get("message") or {}
        usage = message.get("usage")
        msg_id = message.get("id") or record.get("uuid")
        if not isinstance(usage, dict) or not msg_id or msg_id in self._seen:
            return
        self._seen.add(msg_id)
        self.input_tokens += sum(
            int(usage.get(k) or 0)
            for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
        )
        self.output_tokens += int(usage.get("output_tokens") or 0)


__all__ = ["CostReport", "TranscriptUsage", "cost_from_state", "parse_cost_output", "strip_ansi"]
