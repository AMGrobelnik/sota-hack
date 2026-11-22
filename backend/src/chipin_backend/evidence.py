"""Run evidence: three measurements computed only from a finished run's own files.

A. Number tracing: every number the final report states, traced to a
   machine-produced source in the same run folder (a ``metric`` event, or a
   numeric field of a file the chip lab wrote). An untraced number is not
   called wrong: it only has no machine source.
B. Weight bytes per decision: the bytes of trained weights a software
   implementation of the selected chip's model reads for one decision, and
   the memory cells (and flip-flops) in the chip's compiled netlist.
C. Stage timings: wall time per stage from the ``stage`` events, each
   stage's share, the largest share and the speed-up bound it implies, items
   per second where the events count items, and per-tool-call wall times.

Pure functions over a run folder: no network, no model calls. The entry
point :func:`build_evidence` returns a JSON-ready dict and writes
``evidence.json`` and ``evidence.md`` into the run folder. Paths in the
output are relative to the run folder.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

EVIDENCE_JSON = "evidence.json"
EVIDENCE_MD = "evidence.md"
EVENTS_FILE = "events.jsonl"
#: An integer at or below this (absolute) is traced only when its words share a term with the source key.
SMALL_INT_MAX = 10
#: Source files larger than this are not read.
MAX_SOURCE_BYTES = 5_000_000
#: Lab files that are not measurements: the netlist (structure) and the model the agent handed in.
NOT_MEASUREMENTS = frozenset({"net.json", "ir.json"})

# ---------------------------------------------------------------- reading


def read_events(run: Path) -> list[dict[str, Any]]:
    """The run's contract events (lines of ``events.jsonl`` with a ``type``)."""
    path = run / EVENTS_FILE
    if not path.is_file():
        return []
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict) and "type" in item:
            events.append(item)
    return events


def _load_json(path: Path) -> Any:
    try:
        if path.stat().st_size > MAX_SOURCE_BYTES:
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _rel(run: Path, path: Path) -> str:
    try:
        return path.relative_to(run).as_posix()
    except ValueError:
        return path.name


def _ts(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _workspace(run: Path) -> Path:
    return run / "workspace" if (run / "workspace").is_dir() else run


def find_report(run: Path, events: list[dict[str, Any]]) -> Path | None:
    """The run's final report: ``workspace/report.md``, else a ``report`` artifact outside ``chips/``."""
    candidates = [_workspace(run) / "report.md"]
    for event in events:
        path = str(event.get("path") or "")
        if event.get("type") == "artifact" and event.get("kind") == "report" and "chips/" not in path:
            candidates.append(run / path)
    return next((p for p in candidates if p.is_file() and p.suffix == ".md"), None)


def find_prompt(run: Path, events: list[dict[str, Any]]) -> str:
    """The user's prompt: ``run.started``, else ``api.json``, else ``workspace/brief.md``."""
    for event in events:
        if event.get("type") == "run.started" and isinstance(event.get("prompt"), str):
            return event["prompt"]
    record = _load_json(run / "api.json")
    if isinstance(record, dict) and isinstance(record.get("prompt"), str):
        return record["prompt"]
    brief = _workspace(run) / "brief.md"
    return brief.read_text(encoding="utf-8") if brief.is_file() else ""


# ---------------------------------------------------------------- A. number tracing

_STOP = frozenset(
    re.findall(
        r"\w+",
        "a an and are as at be by for from has in is it its of on or per than that the this to was were "
        "with which while each all one two three about into over under after before",
    )
)
_PREFIX = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "m": 1e-3, "": 1.0, "k": 1e3, "M": 1e6, "G": 1e9}
_BASES = ("Hz", "W", "J", "s", "m2", "m²", "m", "V")
_COUNT_UNITS = (
    "gates|GE|LUTs?|LUT4|LUT6|tiles?|bits?|bytes?|B|KB|kB|MB|vectors?|cells?|params?|designs?|"
    "transistors?|patients?|levels?|EUR"
)
_UNIT = re.compile(rf"^(?:%|x|\u00d7|[kMGK]|(?:[pnuµmkMG]?(?:Hz|W|J|s|m2|m²|m|V))|{_COUNT_UNITS})$")
_NUMBER = re.compile(r"(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?(?:[eE]([-+]?\d+))?")
_BOUNDARY = set(" \t()[]{};|*\"'`=:<>≈~!?,–—→")  # noqa: RUF001 (dashes and arrows separate numbers)
_MONTH = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|"
    r"Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\b\.?"
)
#: Words this close to a number are its context, for the small-integer guard and key ranking.
CONTEXT_WORDS = 5
_SPANS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("date", re.compile(r"\b\d{4}-\d{2}-\d{2}(?:[T ][\d:.]+(?:Z|[+-]\d{2}:?\d{2})?)?")),
    ("date", re.compile(rf"\b\d{{1,2}}\s+{_MONTH}(?:\s+\d{{4}})?")),
    ("date", re.compile(rf"\b{_MONTH}\s+\d{{1,2}}(?:,?\s+\d{{4}})?")),
    ("time", re.compile(r"\b\d{1,2}:\d{2}(?::\d{2}(?:\.\d+)?)?\b")),
    ("version", re.compile(r"(?<![\w.])v?\d+(?:\.\d+){2,}(?:[+-]\w+)?|\b\d+\.\d+\+\d+\b")),
    ("code", re.compile(r"`[^`]*[A-Za-z][^`]*`")),
    ("list numbering", re.compile(r"^\s*(?:#+\s*)?\d+(?:\.\d+)*[.)](?=\s)")),
    ("section numbering", re.compile(r"^\s*#+\s*\d+(?:\.\d+)*(?=\s)")),
)


def _terms(text: str) -> set[str]:
    """Lower-case content words of ``text``, a trailing plural ``s`` dropped."""
    words = re.findall(r"[A-Za-z][A-Za-z]+", text.replace("_", " "))
    out = set()
    for word in words:
        low = word.lower()
        if low in _STOP:
            continue
        out.add(low[:-1] if len(low) > 3 and low.endswith("s") and not low.endswith("ss") else low)
    return out


def _unit_scale(unit: str | None) -> tuple[str, float] | None:
    """``(base, factor)`` for a physical unit with an SI prefix, e.g. ``nW`` -> ``("W", 1e-9)``."""
    if not unit:
        return None
    unit = unit.replace("um", "µm") if unit.startswith("um") else unit
    for base in _BASES:
        if unit.endswith(base) and unit[: -len(base)] in _PREFIX:
            prefix = _PREFIX[unit[: -len(base)]]
            squared = base in ("m2", "m²")
            return ("m2" if squared else base, prefix**2 if squared else prefix)
    return None


_KEY_UNIT = re.compile(r"_(um2|mm2|ns|ps|us|ms|pj|nj|uw|nw|mw|mhz|khz|hz|eur)$")


def _key_unit(key: str) -> str | None:
    match = _KEY_UNIT.search(key.lower())
    if match is None:
        return None
    raw = match.group(1)
    fixed = {
        "pj": "pJ",
        "nj": "nJ",
        "uw": "uW",
        "nw": "nW",
        "mw": "mW",
        "mhz": "MHz",
        "khz": "kHz",
        "hz": "Hz",
    }
    return fixed.get(raw, raw)


@dataclass
class Claim:
    """One number written in the report."""

    line: int
    snippet: str
    text: str
    value: float
    resolution: float
    unit: str | None
    percent: bool
    terms: set[str] = field(default_factory=set)
    excluded: str | None = None


@dataclass
class Source:
    """One machine-produced number in the run folder."""

    label: str
    key: str
    value: float
    unit: str | None
    terms: set[str]
    from_event: bool


def _word_around(line: str, start: int, end: int) -> tuple[int, int]:
    """The whitespace/punctuation-delimited word containing ``line[start:end]``."""

    def part_of_word(i: int) -> bool:
        ch = line[i]
        if ch == ",":
            return 0 < i < len(line) - 1 and line[i - 1].isdigit() and line[i + 1].isdigit()
        return ch not in _BOUNDARY

    left, right = start, end
    while left > 0 and part_of_word(left - 1):
        left -= 1
    while right < len(line) and part_of_word(right):
        right += 1
    while right > end and line[right - 1] in ".:":
        right -= 1
    return left, right


def _table_headers(lines: list[str]) -> dict[int, list[str]]:
    """For each markdown table row, the header cells of its table."""
    headers: dict[int, list[str]] = {}
    current: list[str] | None = None
    for i, line in enumerate(lines):
        if line.lstrip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if current is None:
                current = cells
            headers[i] = current
        else:
            current = None
    return headers


def extract_claims(report: str, prompt: str = "") -> list[Claim]:
    """Every number in ``report`` with its words; non-claims carry ``excluded`` (the reason)."""
    lines = report.splitlines()
    headers = _table_headers(lines)
    quoted = _prompt_quotes(prompt)
    claims: list[Claim] = []
    in_fence = False
    for index, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        spans = [(m.start(), m.end(), kind) for kind, pattern in _SPANS for m in pattern.finditer(line)]
        seen: set[tuple[int, int]] = set()
        for match in _NUMBER.finditer(line):
            claim = _claim(line, index, match, spans, headers.get(index))
            if claim is None:
                continue
            word = _word_around(line, *match.span())
            if claim.excluded == "identifier or file name" and word in seen:
                continue  # one identifier, one entry
            seen.add(word)
            if in_fence:
                claim.excluded = "code block"
            elif claim.excluded is None and _quote_key(line, match.start(), match.end()) in quoted:
                claim.excluded = "quoted from the prompt"
            claims.append(claim)
    return claims


def _claim(
    line: str, index: int, match: re.Match[str], spans: list[tuple[int, int, str]], header: list[str] | None
) -> Claim | None:
    start, end = match.span()
    if start > 0 and (line[start - 1].isdigit() or line[start - 1] == "."):
        return None  # the tail of a longer token already handled
    left, right = _word_around(line, start, end)
    word = line[left:right]
    lead = word[: start - left]
    raw_tail = word[end - left :]
    tail = raw_tail.lstrip("-")
    compound = raw_tail.startswith("-") and tail.isalpha()  # "2-lane", "8-bit"
    excluded = next((kind for s, e, kind in spans if s <= start < e), None)
    if excluded is None and any(ch.isalpha() for ch in lead.lstrip("€$£+-−")):  # noqa: RUF001
        excluded = "identifier or file name"
    if (
        excluded is None
        and tail
        and not compound
        and not _UNIT.match(tail)
        and any(c.isalpha() for c in tail)
    ):
        excluded = "identifier or file name"
    whole, frac, exp = match.group(1), match.group(2) or "", match.group(3)
    value = float(whole.replace(",", "") + frac)
    resolution = 10.0 ** -(len(frac) - 1 if frac else 0)
    if exp:
        value *= 10.0 ** int(exp)
        resolution *= 10.0 ** int(exp)
    unit = tail if tail and _UNIT.match(tail) else None
    written = line[start:end] + (raw_tail if unit or compound else "")
    if unit is None:
        after = line[right:].split()
        nxt = after[0].strip(".,;:)*|") if after else ""
        unit = nxt if nxt and _UNIT.match(nxt) and nxt not in ("x", "K", "M", "G", "k", "B") else None
        written += f" {unit}" if unit else ""
    if unit in ("k", "K", "M", "G"):
        scale = {"k": 1e3, "K": 1e3, "M": 1e6, "G": 1e9}[unit]
        value, resolution, unit = value * scale, resolution * scale, None
    if lead.endswith(("-", "−")) and not lead.rstrip("-−"):  # noqa: RUF001
        value = -value
    snippet = _snippet(line, start, end)
    before, after_words = line[:left].split()[-CONTEXT_WORDS:], line[right:].split()[:CONTEXT_WORDS]
    terms = _terms(" ".join([*before, tail if compound else "", *after_words]))
    if header is not None:
        column = line[:start].count("|") - 1
        if 0 <= column < len(header):
            terms |= _terms(header[column])
    return Claim(
        line=index + 1,
        snippet=snippet,
        text=word.strip("*_") if excluded else written,
        value=value,
        resolution=resolution / 2,
        unit=unit if unit != "%" else None,
        percent=unit == "%",
        terms=terms,
        excluded=excluded,
    )


def _snippet(line: str, start: int, end: int, width: int = 50) -> str:
    left = max(0, start - width)
    right = min(len(line), end + width)
    text = " ".join(line[left:right].split())
    return ("..." if left else "") + text + ("..." if right < len(line) else "")


def _quote_key(text: str, start: int, end: int) -> tuple[str, str]:
    nxt = text[end:].split()
    return (text[start:end].replace(",", ""), nxt[0].strip(".,;:)").lower() if nxt else "")


def _prompt_quotes(prompt: str) -> set[tuple[str, str]]:
    """(number as written, next word) pairs of the prompt: the same pair in the report is a quote."""
    return {_quote_key(prompt, m.start(), m.end()) for m in _NUMBER.finditer(prompt)}


def _walk_numbers(data: Any, path: str = "") -> Iterator[tuple[str, float]]:
    """Numeric leaves with a key path; bare number lists (weights, vectors, bit ids) are data, skipped."""
    if isinstance(data, dict):
        for key, value in data.items():
            child = f"{path}.{key}" if path else str(key)
            if isinstance(value, bool):
                continue
            if isinstance(value, int | float) and math.isfinite(value):
                yield child, float(value)
            elif isinstance(value, dict | list):
                yield from _walk_numbers(value, child)
    elif isinstance(data, list):
        for i, value in enumerate(data):
            if isinstance(value, dict):
                yield from _walk_numbers(value, f"{path}[{i}]")


def lab_files(run: Path) -> list[Path]:
    """Files written by lab tools: JSON and text under ``chips/``, and JSON shaped like a lab answer.

    A lab tool prints one JSON object with ``status`` and a ``design_id`` or ``cost``; an agent
    that saved such an answer to a file kept the lab's numbers verbatim.
    """
    space = _workspace(run)
    out: list[Path] = []
    for path in sorted(space.rglob("*")):
        parts = path.relative_to(space).parts
        if any(part.startswith(".") for part in parts) or not path.is_file() or path.name in NOT_MEASUREMENTS:
            continue
        under_chips = parts[0] == "chips"
        if path.suffix in (".md", ".txt") and under_chips:
            out.append(path)
        elif path.suffix == ".json":
            data = _load_json(path) if under_chips else None
            if under_chips and data is not None:
                out.append(path)
            elif not under_chips and path.stat().st_size <= MAX_SOURCE_BYTES:
                data = _load_json(path)
                if isinstance(data, dict) and "status" in data and ("design_id" in data or "cost" in data):
                    out.append(path)
    return out


def collect_sources(run: Path, events: list[dict[str, Any]]) -> list[Source]:
    """Every machine-produced number: metric events, then numeric fields and text numbers of lab files."""
    sources = []
    for event in events:
        value = event.get("value")
        if event.get("type") != "metric" or isinstance(value, bool) or not isinstance(value, int | float):
            continue
        key, unit = str(event.get("key")), event.get("unit") or _key_unit(str(event.get("key")))
        sources.append(
            Source(
                label=f"metric {key} = {value} (events.jsonl seq {event.get('seq')})",
                key=key,
                value=float(value),
                unit=unit,
                terms=_terms(key) | _terms(str(event.get("unit") or "")),
                from_event=True,
            )
        )
    for path in lab_files(run):
        rel = _rel(run, path)
        if path.suffix == ".json":
            for key, value in _walk_numbers(_load_json(path)):
                last = key.rsplit(".", 1)[-1]
                sources.append(
                    Source(f"{rel}: {key} = {value:g}", key, value, _key_unit(last), _terms(key), False)
                )
            continue
        for claim in extract_claims(path.read_text(encoding="utf-8", errors="replace")):
            if claim.excluded is None:
                label = f"{rel} line {claim.line}: {claim.snippet}"
                sources.append(Source(label, claim.snippet, claim.value, claim.unit, claim.terms, False))
    return sources


def _matches(claim: Claim, source: Source) -> bool:
    """Whether ``source`` rounds to ``claim`` at the digits shown (sign not compared)."""
    wanted = abs(claim.value)
    candidates = [abs(source.value)]
    if claim.percent:
        candidates.append(abs(source.value) * 100)
    have, want = _unit_scale(source.unit), _unit_scale(claim.unit)
    if have and want and have[0] == want[0]:
        candidates.append(abs(source.value) * have[1] / want[1])
    tolerance = claim.resolution * (1 + 1e-9) + 1e-12
    return any(abs(c - wanted) <= tolerance for c in candidates)


def _is_small_int(claim: Claim) -> bool:
    return claim.resolution >= 0.5 and claim.value.is_integer() and abs(claim.value) <= SMALL_INT_MAX


def trace_numbers(run: Path, events: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Measurement A over the run's final report."""
    events = read_events(run) if events is None else events
    report = find_report(run, events)
    result: dict[str, Any] = {
        "report": _rel(run, report) if report else None,
        "traced": 0,
        "traced_without_key_match": 0,
        "untraced": 0,
        "untraced_small_integer": 0,
        "excluded": 0,
        "numbers": [],
    }
    if report is None:
        result["note"] = "no final report (workspace/report.md) in the run folder"
        return result
    sources = collect_sources(run, events)
    result["sources"] = {
        "metric_events": sum(s.from_event for s in sources),
        "lab_file_numbers": sum(not s.from_event for s in sources),
    }
    for claim in extract_claims(report.read_text(encoding="utf-8"), find_prompt(run, events)):
        entry: dict[str, Any] = {"line": claim.line, "snippet": claim.snippet, "text": claim.text}
        entry["value"] = claim.value
        if claim.excluded:
            entry["status"] = f"excluded ({claim.excluded})"
            result["excluded"] += 1
        else:
            hits = [s for s in sources if _matches(claim, s)]
            ranked = sorted(
                hits,
                key=lambda s: (
                    -len(claim.terms & s.terms),
                    not s.from_event,
                    abs(abs(s.value) - abs(claim.value)),
                ),
            )
            best = ranked[0] if ranked else None
            if best and _is_small_int(claim) and not claim.terms & best.terms:
                best = None
                entry["status"] = "untraced (small integer, no matching key)"
                result["untraced_small_integer"] += 1
            elif best is None:
                entry["status"] = "untraced"
                result["untraced"] += 1
            if best is not None:
                entry["status"] = "traced"
                entry["source"] = best.label
                entry["other_matches"] = len(hits) - 1
                entry["key_match"] = bool(claim.terms & best.terms)
                result["traced"] += 1
                result["traced_without_key_match"] += not entry["key_match"]
        result["numbers"].append(entry)
    return result


# ---------------------------------------------------------------- B. weight bytes

_WEIGHT_KEY = re.compile(r"^(?:W|b|w|weights?|bias(?:es)?|kernel)\d*$")
_WIDTH_KEYS = ("weight_bits", "w_bits", "wbits")
_FLOP = re.compile(r"dff|dlatch|^\$_?sr|__df|__dl|__edf|__sdf", re.I)
_MEMORY = re.compile(r"^\$mem|sram|\bram|rom\b|_ram|_rom|macro", re.I)


def _chips_root(run: Path) -> Path | None:
    return next((p for p in (_workspace(run) / "chips", run / "chips") if p.is_dir()), None)


def laid_out_chips(run: Path, events: list[dict[str, Any]]) -> list[Path]:
    """Chip folders the lab laid out (``artifact`` events of kind ``chip``), in event order."""
    root = _chips_root(run)
    names: list[str] = []
    for event in events:
        parts = Path(str(event.get("path") or "")).parts
        if event.get("type") == "artifact" and event.get("kind") == "chip" and "chips" in parts[:-2]:
            name = parts[parts.index("chips") + 1]
            if name not in names:
                names.append(name)
    return [root / n for n in names if root is not None and (root / n).is_dir()]


def select_chip(run: Path, events: list[dict[str, Any]]) -> tuple[Path | None, str]:
    """The chip the run selected and why.

    The chip the report names most often (laid-out chips first); if the report names none,
    the first laid-out chip whose model carries weights; else the first chip with weights.
    """
    root = _chips_root(run)
    if root is None:
        return None, "no chips/ folder"
    chips = [p for p in sorted(root.iterdir()) if p.is_dir()]
    if not chips:
        return None, "chips/ is empty"
    laid_out = laid_out_chips(run, events)
    report = find_report(run, events)
    text = report.read_text(encoding="utf-8") if report else ""
    pool = laid_out or chips
    counts = {c: len(re.findall(rf"(?<![\w-]){re.escape(c.name)}(?![\w-])", text)) for c in pool}
    best = max(pool, key=lambda c: counts[c])
    if counts[best] and list(counts.values()).count(counts[best]) == 1:
        basis = "the laid-out chips" if laid_out else "all chips"
        return best, f"the chip the report names most often ({counts[best]} times) among {basis}"
    weighted = [c for c in pool if (m := _model_file(c)) is not None and any(_tensors(_load_json(m)))]
    if weighted:
        what = "laid-out chip" if laid_out else "chip folder (by name)"
        return weighted[0], f"the report names no single chip; the first {what} whose model carries weights"
    return pool[0], "the report names no single chip and no model carries weights; the first chip"


def _min_signed_bits(values: list[int]) -> int:
    low, high = min(values), max(values)
    if low >= 0:
        return max(1, high.bit_length() + 1)
    return max((-low - 1).bit_length(), high.bit_length()) + 1


def _flat(values: Any) -> Iterator[Any]:
    if isinstance(values, list):
        for item in values:
            yield from _flat(item)
    else:
        yield values


def _tensors(data: Any, path: str = "") -> Iterator[tuple[str, list[float]]]:
    if isinstance(data, dict):
        for key, value in data.items():
            child = f"{path}.{key}" if path else str(key)
            if _WEIGHT_KEY.match(str(key)) and isinstance(value, list):
                flat = list(_flat(value))
                if flat and all(isinstance(v, int | float) and not isinstance(v, bool) for v in flat):
                    yield child, [float(v) for v in flat]
                    continue
            yield from _tensors(value, child)
    elif isinstance(data, list):
        for i, item in enumerate(data):
            label = item.get("id") if isinstance(item, dict) and isinstance(item.get("id"), str) else str(i)
            yield from _tensors(item, f"{path}[{label}]")


def _declared_width(data: Any) -> int | None:
    meta = data.get("meta") if isinstance(data, dict) else None
    for holder in (data, meta):
        if isinstance(holder, dict):
            for key in _WIDTH_KEYS:
                if isinstance(holder.get(key), int):
                    return int(holder[key])
    return None


def _width(values: list[float], declared: int | None) -> tuple[int, int, str]:
    """``(stored bits, minimal bits, kind)`` of one tensor."""
    if any(not v.is_integer() for v in values):
        bits = declared or 32
        return bits, bits, "declared width" if declared else "decimal values, float32 assumed"
    ints = sorted({int(v) for v in values})
    if set(ints) <= {-1, 1} or set(ints) <= {0, 1}:
        return declared or 1, 1, "binary (1 bit)"
    if set(ints) <= {-1, 0, 1}:
        return declared or 2, 2, "ternary (2 bits)"
    minimal = _min_signed_bits(ints)
    if declared:
        return declared, minimal, "declared width"
    stored = next(b for b in (8, 16, 32, 64) if b >= minimal)
    return stored, minimal, f"integers, int{stored} (smallest machine type holding every value)"


def _model_file(chip: Path) -> Path | None:
    if (chip / "ir.json").is_file():
        return chip / "ir.json"
    return next((p for p in sorted(chip.glob("*.json")) if any(_tensors(_load_json(p)))), None)


def _netlist_cells(chip: Path) -> tuple[Counter[str], dict[str, int], str | None]:
    """Cell type counts and word-level memory bits of the chip's netlist (``net.json``, else ``gates.v``)."""
    counts: Counter[str] = Counter()
    memory_bits: dict[str, int] = {}
    net = chip / "net.json"
    if net.is_file():
        try:
            data = json.loads(net.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = None
        if isinstance(data, dict):
            for module in (data.get("modules") or {}).values():
                for name, cell in (module.get("cells") or {}).items():
                    kind = str(cell.get("type"))
                    counts[kind] += 1
                    params = cell.get("parameters") or {}
                    if kind.startswith("$mem") and "WIDTH" in params and "SIZE" in params:
                        memory_bits[name] = _param(params["WIDTH"]) * _param(params["SIZE"])
            return counts, memory_bits, "net.json"
    verilog = chip / "gates.v"
    if verilog.is_file():
        keywords = {"module", "input", "output", "wire", "assign", "reg", "endmodule", "inout"}
        for line in verilog.read_text(encoding="utf-8", errors="replace").splitlines():
            match = re.match(r"\s*\\?(\$?[A-Za-z_][\w$]*)\s+\\?\S+\s*\(", line)
            if match and match.group(1) not in keywords:
                counts[match.group(1)] += 1
        return counts, memory_bits, "gates.v"
    return counts, memory_bits, None


def _param(raw: Any) -> int:
    if isinstance(raw, int):
        return raw
    text = str(raw)
    return int(text, 2) if set(text) <= {"0", "1"} else int(text)


def _lab_cross_checks(run: Path, chip: Path) -> list[str]:
    """What the lab's own answers for this chip say about flip-flops, memories and cell classes."""
    notes = []
    for path in lab_files(run):
        if path.suffix != ".json" or path.parent == chip:
            continue
        data = _load_json(path)
        if not isinstance(data, dict) or data.get("design_id") != chip.name:
            continue
        metrics = data.get("metrics") if isinstance(data.get("metrics"), dict) else {}
        if "ff" in metrics:
            notes.append(f"{_rel(run, path)}: metrics.ff = {metrics['ff']} (FPGA flip-flops)")
        classes = sorted(k.split("class:", 1)[1] for k in metrics if "__class:" in k)
        if classes:
            flops = [c for c in classes if re.search(r"sequential|flop|macro|memory", c)]
            notes.append(
                f"{_rel(run, path)}: layout cell classes {', '.join(classes)}"
                + (f"; storage classes {', '.join(flops)}" if flops else "; no sequential or macro class")
            )
    return notes


def weight_bytes(run: Path, events: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Measurement B for the chip the run selected, plus one line per other laid-out chip."""
    events = read_events(run) if events is None else events
    chip, why = select_chip(run, events)
    if chip is None:
        return {"chip": None, "note": why}
    out: dict[str, Any] = {"chip": chip.name, "chip_selected_by": why, **chip_weight_figures(run, chip)}
    others = []
    for other in laid_out_chips(run, events):
        if other != chip:
            figures = chip_weight_figures(run, other)
            others.append(
                {
                    "chip": other.name,
                    "software_bytes_per_decision": figures["software"].get("bytes_per_decision"),
                    "parameters": figures["software"].get("parameters"),
                    "declared_params": figures["software"].get("declared_params"),
                    "memory_cells": figures["chip_netlist"].get("memory_cells"),
                    "flip_flops": figures["chip_netlist"].get("flip_flops"),
                    "cells": figures["chip_netlist"].get("cells"),
                }
            )
    out["other_laid_out_chips"] = others
    return out


def chip_weight_figures(run: Path, chip: Path) -> dict[str, Any]:
    """``software`` (model weight bytes) and ``chip_netlist`` (memory cells) for one chip folder."""
    out: dict[str, Any] = {}
    model = _model_file(chip)
    if model is not None:
        data = _load_json(model)
        declared = _declared_width(data)
        tensors = []
        for name, values in _tensors(data):
            stored, minimal, kind = _width(values, declared)
            tensors.append(
                {"field": name, "count": len(values), "bits": stored, "min_bits": minimal, "kind": kind}
            )
        count = sum(t["count"] for t in tensors)
        stored_bits = sum(t["count"] * t["bits"] for t in tensors)
        min_bits = sum(t["count"] * t["min_bits"] for t in tensors)
        meta = data.get("meta") if isinstance(data, dict) else None
        out["software"] = {
            "model_file": _rel(run, model),
            "parameters": count,
            "declared_params": meta.get("params") if isinstance(meta, dict) else None,
            "bytes_per_decision": math.ceil(stored_bits / 8),
            "bytes_at_minimal_widths": math.ceil(min_bits / 8),
            "tensors": tensors,
        }
        by_width: Counter[int] = Counter()
        for tensor in tensors:
            by_width[tensor["bits"]] += tensor["count"]
        widths = " and ".join(f"{n} at {bits} bits" for bits, n in sorted(by_width.items()))
        fields = ", ".join(t["field"] for t in tensors)
        sentence = (
            f"A software implementation reads {out['software']['bytes_per_decision']} bytes of trained "
            f"weights per decision: {count} parameters ({widths or 'none'}) in the arrays {fields or 'none'} "
            f"of {_rel(run, model)}; packed at the smallest width each array needs it would be "
            f"{out['software']['bytes_at_minimal_widths']} bytes."
        )
        declared_params = out["software"]["declared_params"]
        if isinstance(declared_params, int) and declared_params != count:
            sentence += (
                f" The file declares {declared_params} parameters: its arrays store {count} entries "
                "(shared or unrolled weights), so software that shares them reads fewer bytes."
            )
        out["software"]["sentence"] = sentence
    else:
        out["software"] = {"note": f"no model file with weights in {_rel(run, chip)}"}
    counts, mem_bits, source = _netlist_cells(chip)
    memories = {k: v for k, v in counts.items() if _MEMORY.search(k)}
    flops = {k: v for k, v in counts.items() if _FLOP.search(k) and k not in memories}
    hardware: dict[str, Any] = {
        "netlist": _rel(run, chip / source) if source else None,
        "cells": sum(counts.values()),
        "memory_cells": sum(memories.values()),
        "memory_cell_types": memories,
        "memory_bits": sum(mem_bits.values()) if mem_bits else (0 if not memories else None),
        "flip_flops": sum(flops.values()),
        "flip_flop_types": flops,
        "cell_types": dict(sorted(counts.items())),
        "lab_cross_checks": _lab_cross_checks(run, chip),
    }
    if source is None:
        hardware["sentence"] = f"No netlist (net.json or gates.v) in {_rel(run, chip)}; no chip figure."
    elif not memories:
        hardware["weight_bytes_fetched_per_decision"] = 0
        hardware["sentence"] = (
            f"The compiled chip {chip.name} has 0 memory cells and {hardware['flip_flops']} flip-flops "
            f"among {hardware['cells']} cells in {hardware['netlist']}, so it fetches 0 weight bytes per "
            "decision: the weights are constants wired into the logic."
        )
    else:
        bits = hardware["memory_bits"]
        hardware["weight_bytes_fetched_per_decision"] = None
        hardware["sentence"] = (
            f"The compiled chip {chip.name} has {hardware['memory_cells']} memory cells "
            f"({', '.join(sorted(memories))}) holding {bits if bits is not None else 'an unknown number of'} "
            f"bits in {hardware['netlist']}; its weights may be read from memory, so 0 is not claimed."
        )
    out["chip_netlist"] = hardware
    return out


# ---------------------------------------------------------------- C. stage timings


def stage_timings(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Measurement C: wall time per stage, shares, the largest stage's bound, items/s and tool calls."""
    stamped = [(e, _ts(e.get("ts"))) for e in events]
    stamped = [(e, t) for e, t in stamped if t is not None]
    if not stamped:
        return {"note": "no timestamped events"}
    start = next((t for e, t in stamped if e["type"] == "run.started"), stamped[0][1])
    finished = next((t for e, t in stamped if e["type"] == "run.finished"), None)
    end = finished or stamped[-1][1]
    total = max((end - start).total_seconds(), 0.0)
    intervals: dict[str, list[dict[str, Any]]] = {}
    open_: dict[str, datetime] = {}
    for event, t in stamped:
        if event["type"] != "stage":
            continue
        name, state = str(event.get("name") or event.get("stage")), event.get("state")
        if state == "started":
            open_[name] = t
        elif state in ("done", "skipped"):
            begin = open_.pop(name, t)
            intervals.setdefault(name, []).append({"start": begin, "end": t, "state": state})
    for name, begin in open_.items():
        intervals.setdefault(name, []).append({"start": begin, "end": end, "state": "open (no done event)"})
    stages = []
    for name, spans in intervals.items():
        seconds = sum((s["end"] - s["start"]).total_seconds() for s in spans)
        stages.append(
            {
                "stage": name,
                "seconds": round(seconds, 3),
                "share": round(seconds / total, 4) if total else None,
                "state": spans[-1]["state"],
                "items": _stage_items(stamped, spans, seconds),
            }
        )
    stages.sort(key=lambda s: min(sp["start"] for sp in intervals[s["stage"]]))
    covered = _union_seconds([(s["start"], s["end"]) for spans in intervals.values() for s in spans])
    result: dict[str, Any] = {
        "run_finished": finished is not None,
        "total_seconds": round(total, 3),
        "outside_stages_seconds": round(max(total - covered, 0.0), 3),
        "stages": stages,
        "tool_calls": _tool_calls(stamped),
        "scope": "wall time of one run on one machine, from the event timestamps",
    }
    timed = [s for s in stages if s["share"]]
    if timed:
        top = max(timed, key=lambda s: s["share"])
        result["largest"] = {
            "stage": top["stage"],
            "share": top["share"],
            "bound": round(1 / top["share"], 2),
            "sentence": (
                f"{top['stage']} took {top['share']:.0%} of the run's wall time, so even if every other "
                f"stage took no time the whole run could speed up by at most {1 / top['share']:.2f}x."
            ),
        }
    return result


def _union_seconds(spans: list[tuple[datetime, datetime]]) -> float:
    total, last_end = 0.0, None
    for begin, finish in sorted(spans):
        if last_end is not None and begin < last_end:
            begin = last_end
        if finish > begin:
            total += (finish - begin).total_seconds()
        last_end = finish if last_end is None or finish > last_end else last_end
    return total


def _stage_items(
    stamped: list[tuple[dict[str, Any], datetime]], spans: list[dict[str, Any]], seconds: float
) -> list[dict[str, Any]]:
    """Counts of what the events show the stage processed, with items per second."""
    inside = [e for e, t in stamped if any(s["start"] <= t <= s["end"] for s in spans)]
    chips = {
        Path(str(e.get("path"))).parts[2]
        for e in inside
        if e["type"] == "artifact"
        and Path(str(e.get("path") or "")).parts[1:2] == ("chips",)
        and len(Path(str(e.get("path"))).parts) > 3
    }
    metrics = Counter(str(e.get("key")) for e in inside if e["type"] == "metric")
    vectors = sum(
        e.get("value") or 0 for e in inside if e["type"] == "metric" and e.get("key") == "vectors_checked"
    )
    items: list[tuple[str, float]] = []
    if chips:
        items.append(("chip folders written", len(chips)))
    for key, label in (("gates", "designs synthesised"), ("verification_level", "verification results")):
        if metrics.get(key):
            items.append((label, metrics[key]))
    if vectors:
        items.append(("vectors checked", vectors))
    return [
        {"item": label, "count": count, "per_second": round(count / seconds, 3) if seconds > 0 else None}
        for label, count in items
    ]


def _tool_calls(stamped: list[tuple[dict[str, Any], datetime]]) -> dict[str, Any]:
    started: dict[str, tuple[datetime, str]] = {}
    calls: list[dict[str, Any]] = []
    for event, t in stamped:
        if event["type"] != "tool" or not event.get("call_id"):
            continue
        if event.get("state") == "started":
            started[event["call_id"]] = (t, str(event.get("summary") or event.get("name") or ""))
        elif event["call_id"] in started:
            begin, summary = started.pop(event["call_id"])
            calls.append(
                {"summary": summary, "start": begin, "end": t, "seconds": (t - begin).total_seconds()}
            )
    if not calls and not started:
        return {"count": 0}
    calls.sort(key=lambda c: c["start"])
    overlaps, latest_end = 0, None
    for call in calls:
        if latest_end is not None and call["start"] < latest_end:
            overlaps += 1
        latest_end = call["end"] if latest_end is None or call["end"] > latest_end else latest_end
    longest = max(calls, key=lambda c: c["seconds"]) if calls else None
    return {
        "count": len(calls),
        "unfinished": len(started),
        "total_seconds": round(sum(c["seconds"] for c in calls), 3),
        "longest": {"summary": longest["summary"], "seconds": round(longest["seconds"], 3)}
        if longest
        else None,
        "overlapping_calls": overlaps,
        "note": (
            "some tool calls overlapped in time"
            if overlaps
            else "no two finished tool calls overlapped in time"
        ),
    }


# ---------------------------------------------------------------- entry point


def build_evidence(run: Path, *, write: bool = True, finishing: bool = False) -> dict[str, Any]:
    """All three measurements for ``run``; with ``write``, also ``evidence.json`` and ``evidence.md``.

    ``finishing``: the backend computes it as the run ends, just before ``run.finished`` is written.
    """
    run = Path(run)
    events = read_events(run)
    finished = any(e["type"] == "run.finished" for e in events)
    evidence = {
        "run_id": next((str(e["run_id"]) for e in events if e.get("run_id")), run.name),
        "run_finished": finished,
        "run_state": "finished"
        if finished
        else "finishing (measured just before run.finished)"
        if finishing
        else "NOT finished (no run.finished event)",
        "numbers": trace_numbers(run, events),
        "weights": weight_bytes(run, events),
        "stages": stage_timings(events),
    }
    if write:
        (run / EVIDENCE_JSON).write_text(json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8")
        (run / EVIDENCE_MD).write_text(render_markdown(evidence), encoding="utf-8")
    return evidence


def evidence_summary(evidence: dict[str, Any]) -> dict[str, Any]:
    """The three short summaries carried by the ``evidence`` event."""
    numbers, weights, stages = evidence["numbers"], evidence["weights"], evidence["stages"]
    software = weights.get("software") or {}
    chip = weights.get("chip_netlist") or {}
    return {
        "numbers": {k: numbers.get(k) for k in ("traced", "untraced", "untraced_small_integer", "excluded")},
        "weights": {
            "chip": weights.get("chip"),
            "software_bytes_per_decision": software.get("bytes_per_decision"),
            "chip_memory_cells": chip.get("memory_cells"),
            "chip_flip_flops": chip.get("flip_flops"),
        },
        "stages": {
            "total_seconds": stages.get("total_seconds"),
            "largest": (stages.get("largest") or {}).get("stage"),
            "largest_share": (stages.get("largest") or {}).get("share"),
            "bound": (stages.get("largest") or {}).get("bound"),
        },
    }


def emit_evidence(run: Path, append: Callable[..., Any]) -> None:
    """Compute the evidence once and ``append("evidence", ...)``; any failure is logged, never raised."""
    try:
        evidence = build_evidence(run, finishing=True)
        append("evidence", **evidence_summary(evidence))
    except Exception:  # evidence must never fail a run
        logger.exception("run {}: evidence not computed", Path(run).name)


def render_markdown(evidence: dict[str, Any]) -> str:
    """``evidence.md``: the three measurements in plain words."""
    numbers, weights, stages = evidence["numbers"], evidence["weights"], evidence["stages"]
    out = [
        f"# Run evidence: {evidence['run_id']}",
        "",
        f"Run state when measured: {evidence['run_state']}.",
        "",
    ]
    out += ["## A. Number tracing", ""]
    if numbers.get("report") is None:
        out += [numbers.get("note", "no report"), ""]
    else:
        out += [
            f"Report: `{numbers['report']}`. Traced {numbers['traced']}, untraced {numbers['untraced']}, "
            f"untraced small integers {numbers['untraced_small_integer']}, excluded {numbers['excluded']}.",
            f"{numbers['traced_without_key_match']} traced numbers share no word with their source's key "
            "(the value matches; the match may be a coincidence).",
            "An untraced number is not wrong: it has no machine source in this run folder.",
            "",
        ]
        for entry in numbers["numbers"]:
            where = f": {entry['source']}" if entry.get("source") else ""
            extra = f" (+{entry['other_matches']} more)" if entry.get("other_matches") else ""
            loose = " [no shared key word]" if entry.get("key_match") is False else ""
            out.append(f"- line {entry['line']}: `{entry['text']}` {entry['status']}{where}{extra}{loose}")
            out.append(f"  - {entry['snippet']}")
        out.append("")
    out += ["## B. Weight bytes per decision", ""]
    if weights.get("chip") is None:
        out += [weights.get("note", "no chip"), ""]
    else:
        software, chip = weights.get("software") or {}, weights.get("chip_netlist") or {}
        out += [f"Chip `{weights['chip']}`, selected as {weights['chip_selected_by']}.", ""]
        out += [f"- Software: {software.get('sentence') or software.get('note')}"]
        out += [f"- Chip: {chip.get('sentence')}"]
        out += [f"- Lab cross-check: {note}" for note in chip.get("lab_cross_checks") or []]
        for other in weights.get("other_laid_out_chips") or []:
            out.append(
                f"- Other laid-out chip `{other['chip']}`: software {other['software_bytes_per_decision']} "
                f"bytes ({other['parameters']} stored parameters, {other['declared_params']} declared); "
                f"chip {other['memory_cells']} memory cells, {other['flip_flops']} flip-flops, "
                f"{other['cells']} cells"
            )
        out += ["", "No energy or speed claim follows from these two figures.", ""]
    out += ["## C. Stage timings", ""]
    if "stages" not in stages:
        out += [stages.get("note", "no stage events"), ""]
    else:
        out += [
            f"Total {stages['total_seconds']:.1f} s ({stages['scope']}); "
            f"{stages['outside_stages_seconds']:.1f} s fell outside any stage.",
            "",
        ]
        for stage in stages["stages"]:
            share = f"{stage['share']:.1%}" if stage["share"] is not None else "n/a"
            out.append(f"- {stage['stage']}: {stage['seconds']:.1f} s, {share}, {stage['state']}")
            for item in stage["items"]:
                rate = f", {item['per_second']}/s" if item["per_second"] is not None else ""
                out.append(f"  - {item['item']}: {item['count']:g}{rate}")
        if stages.get("largest"):
            out += ["", stages["largest"]["sentence"]]
        tools = stages["tool_calls"]
        if tools.get("count"):
            longest = tools["longest"]
            out += [
                "",
                f"Tool calls: {tools['count']} finished ({tools['unfinished']} unfinished), "
                f"{tools['total_seconds']:.1f} s in total, longest {longest['seconds']:.1f} s "
                f"({longest['summary']}); {tools['note']}.",
            ]
        out.append("")
    return "\n".join(out)


__all__ = [
    "EVIDENCE_JSON",
    "EVIDENCE_MD",
    "build_evidence",
    "emit_evidence",
    "evidence_summary",
    "extract_claims",
    "find_report",
    "read_events",
    "render_markdown",
    "select_chip",
    "stage_timings",
    "trace_numbers",
    "weight_bytes",
]
