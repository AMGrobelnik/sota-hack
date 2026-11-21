"""Summaries on OpenRouter models: run summaries and output labels.

One entry point, :func:`summarise`, walks a chain of provider tiers for ONE
model (``summaries.yaml`` beside this file): each tier pins exactly one
provider endpoint, and the next tier is the fallback. A tier fails over on a
non-200 answer, a transport error, an error body, a reply cut off at the token
limit, or an empty reply (retried once on the same tier first). A used-up key
stops the walk, since every tier would spend the same key. The whole walk has
one wall-clock budget. ``cost_usd`` and the token counts cover every billed
attempt, the rejected ones included.

Two summaries are built on it:

* :func:`summarise_run`: three bullets on what a whole agent run did, from a
  digest of its events, for the run record.
* :func:`label_output`: a one-line label for an agent's long final answer.

Paid OpenRouter models only; the key is ``OPENROUTER_API_KEY``, read at call
time and sent only in the ``Authorization`` header.
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import httpx
import yaml
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from chipin_backend.llm.endpoints import CHAT_COMPLETIONS_URL
from chipin_backend.llm.keys import (
    OPENROUTER_KEY_ENV,
    has_openrouter_key,
    is_key_exhausted,
    openrouter_api_key,
)

if TYPE_CHECKING:
    from chipin_backend.agents.types import AgentEvent, AgentResult

SETTINGS_PATH = Path(__file__).with_name("summaries.yaml")

#: Finish reasons that mean the reply was cut off, not finished.
_TRUNCATED_FINISH_REASONS = frozenset({"length", "max_tokens"})
#: Below this many seconds left, a tier is not worth starting.
_MIN_ATTEMPT_S = 2.0
#: Attempts per tier: one call plus one retry, on an empty reply only.
_TIER_ATTEMPTS = 2
#: Characters per token when clipping a prompt to the context window (errs short).
_CHARS_PER_TOKEN = 3
#: Tokens kept free of the prompt for the system message and the answer.
_PROMPT_OVERHEAD_TOKENS = 5_000

Effort = Literal["minimal", "low", "medium", "high"]


class SummarySettings(BaseModel):
    """``summaries.yaml``: the model, its provider tiers and the summary shapes."""

    model_config = ConfigDict(extra="forbid")

    model: str
    reasoning_effort: Effort = "low"
    label_reasoning_effort: Effort = "medium"
    max_context_tokens: int = 131072
    tier_timeout_s: float = 8.0
    walk_budget_s: float = 40.0
    min_max_tokens: int = 4096
    providers: list[str] = Field(min_length=1)
    background_providers: list[str] = Field(default_factory=list)
    summary_bullets: int = 3
    summary_max_chars: int = 300
    label_min_output_chars: int = 300
    label_min_chars: int = 30
    label_max_chars: int = 50
    label_max_input_chars: int = 3000
    digest_line_chars: int = 300

    @property
    def bullet_max_chars(self) -> int:
        """Each bullet's share of :attr:`summary_max_chars`, newlines taken out first."""
        bullets = max(1, self.summary_bullets)
        return max(1, (self.summary_max_chars - (bullets - 1)) // bullets)


def load_summary_settings(path: Path | None = None) -> SummarySettings:
    """The settings in ``path`` (default: ``summaries.yaml`` beside this module)."""
    chosen = path or SETTINGS_PATH
    try:
        data = yaml.safe_load(chosen.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid YAML in {chosen}: {exc}") from exc
    return SummarySettings.model_validate(data or {})


@dataclass
class Summary:
    """One summary walk: the text (``""`` when no tier answered) and what it cost."""

    text: str = ""
    cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""  # what OpenRouter says served the answer
    provider: str = ""
    error: str = ""  # the joined per-tier errors when no tier answered

    def to_dict(self) -> dict[str, Any]:
        """Plain JSON-ready dict."""
        return asdict(self)


def _scrub(text: str) -> str:
    """The reply without surrounding whitespace or a wrapping code fence."""
    lines = text.strip().splitlines()
    if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].strip() == "```":
        lines = lines[1:-1]
    return "\n".join(lines).strip()


async def summarise(
    *,
    prompt: str,
    system: str,
    label: bool = False,
    background: bool = False,
    max_output_tokens: int = 0,
    min_words: int = 0,
    settings: SummarySettings | None = None,
    client: httpx.AsyncClient | None = None,
) -> Summary:
    """Walk the summary chain and return the first usable answer.

    ``label`` uses the label reasoning effort; ``background`` walks
    ``background_providers`` (when set) instead of ``providers``.
    ``max_output_tokens`` is raised to the settings' floor; a reply under
    ``min_words`` words counts as empty. Never raises for a failed call: the
    result's ``error`` says why ``text`` is empty. ``client`` is for tests.
    """
    settings = settings or load_summary_settings()
    if not has_openrouter_key():
        logger.warning("summarise: {} is not set; no summary written", OPENROUTER_KEY_ENV)
        return Summary(error=f"{OPENROUTER_KEY_ENV} is not set")
    headers = {"Authorization": f"Bearer {openrouter_api_key()}"}
    chain = (settings.background_providers if background else []) or settings.providers
    effort = settings.label_reasoning_effort if label else settings.reasoning_effort
    budget_chars = (settings.max_context_tokens - _PROMPT_OVERHEAD_TOKENS) * _CHARS_PER_TOKEN
    payload_base: dict[str, Any] = {
        "model": settings.model,
        "messages": [
            {"role": "system", "content": system},
            # Keep the newest part of an over-long prompt.
            {"role": "user", "content": prompt[-budget_chars:] if budget_chars > 0 else prompt},
        ],
        "reasoning": {"effort": effort},
        "usage": {"include": True},
        "max_tokens": max(max_output_tokens, settings.min_max_tokens),
    }
    result = Summary()
    errors: list[str] = []
    deadline = time.monotonic() + settings.walk_budget_s
    own_client = client is None
    http = client or httpx.AsyncClient(follow_redirects=True)
    try:
        for index, provider in enumerate(chain, start=1):
            payload = {
                **payload_base,
                "provider": {"order": [provider], "only": [provider], "allow_fallbacks": False},
            }
            error, stop = await _walk_tier(
                http, payload, headers, settings, deadline=deadline, min_words=min_words, result=result
            )
            if not error:
                result.provider = result.provider or provider
                return result
            errors.append(f"tier{index} {provider}: {error}")
            if stop:
                break
    finally:
        if own_client:
            await http.aclose()
    result.error = " | ".join(errors)
    logger.warning("summarise: no tier answered: {}", result.error)
    return result


async def _walk_tier(
    http: httpx.AsyncClient,
    payload: dict[str, Any],
    headers: dict[str, str],
    settings: SummarySettings,
    *,
    deadline: float,
    min_words: int,
    result: Summary,
) -> tuple[str, bool]:
    """Try one tier; fill ``result`` on success. ``(error, stop the walk)``; ``("", False)`` = answered."""
    error = ""
    for attempt in range(1, _TIER_ATTEMPTS + 1):
        remaining = deadline - time.monotonic()
        if remaining < _MIN_ATTEMPT_S:
            return f"skipped, {remaining:.1f}s left of the walk budget", True
        try:
            response = await http.post(
                CHAT_COMPLETIONS_URL,
                json=payload,
                headers=headers,
                timeout=min(settings.tier_timeout_s, remaining),
            )
        except httpx.HTTPError as exc:
            # No retry on the same tier: the request may already be billed.
            return f"{type(exc).__name__}", False
        if response.status_code != 200:
            exhausted = is_key_exhausted(response.status_code, response.text)
            return f"HTTP {response.status_code}", exhausted
        try:
            data = response.json()
        except json.JSONDecodeError:
            return "unreadable body", False
        usage = data.get("usage") or {}
        result.cost_usd += float(usage.get("cost") or 0.0)
        result.input_tokens += int(usage.get("prompt_tokens") or 0)
        result.output_tokens += int(usage.get("completion_tokens") or 0)
        if data.get("error"):
            error_info = data["error"]
            code = error_info.get("code", "?") if isinstance(error_info, dict) else "?"
            return f"upstream error {code}", False
        choices = data.get("choices") or [{}]
        text = _scrub(str((choices[0].get("message") or {}).get("content") or ""))
        if text and choices[0].get("finish_reason") in _TRUNCATED_FINISH_REASONS:
            return "truncated (finish_reason)", False
        if text and min_words and len(text.split()) < min_words:
            text = ""
        if text:
            result.text = text
            result.model = str(data.get("model") or payload["model"])
            result.provider = str(data.get("provider") or "")
            return "", False
        error = "empty result (retried)" if attempt == _TIER_ATTEMPTS else "empty result"
    return error, False


# ---------------------------------------------------------------------------
# The whole-run summary
# ---------------------------------------------------------------------------

_RUN_SYSTEM_PROMPT = """\
You keep a short summary of one AI agent run for its owner, who wants to know
what the WHOLE run has done.

You get a DIGEST of the run: pinned items first (errors, and the run's own end,
if any), then a chronological list of what happened, oldest to newest: one line
per agent message, tool call or tool result.

SHAPE (hard cap): EXACTLY {bullets} bullets, each starting with "- ", one line of
at most {item_max} characters, {total_max} characters in total; anything longer
is cut off. Together they cover the WHOLE run from start to now, split by WHEN
things happened:
- bullet 1: the run's earliest third: its goal and its first steps or setup;
- bullet 2: its middle third: experiments, results, or revisions since bullet 1;
- bullet 3: its most recent third: what it just produced or is doing now.
  If a line starts with "RUN ENDED", the run is over: bullet 3 must instead
  lead with how it ended (done or failed) and what it produced, using that
  line. Never phrase an ended run as ongoing, and never soften or omit the
  ended state. With NO "RUN ENDED" line the run is STILL RUNNING: no bullet may
  say or imply that it stopped. An error in the digest is a setback the run
  hit, not its end.

GROUNDING (absolute): every fact you write must appear in the digest. NEVER
invent metrics, and never add scope, motive, or color that is not in the
source. Never say a call, step, or tool failed unless the digest shows it.

NO PREAMBLE (absolute): start directly with the first bullet's "- ". Never
restate this prompt or narrate the task.

CONTENT
- Substance: the task, datasets, models, designs, experiment results, and
  real scores or metrics written with digits.
- Never paste URLs or full paths; name the artifact instead ("report
  written", "model trained").
- Do not mention tool calls, agents, configs, or clock times as such; use
  plain words for the work.

STYLE
- Short direct sentences, present tense for the current state, no filler,
  no hedging.
- Light markdown only: **bold** sparingly. No headings, code, nested lists,
  tables, quotes, or emojis.

Output ONLY the bullets."""


def _one_line(text: Any, width: int) -> str:
    """``text`` flattened to one line of at most ``width`` characters."""
    flat = " ".join(str(text).split())
    return flat if len(flat) <= width else flat[: width - 3] + "..."


def build_run_digest(
    events: Iterable[AgentEvent], result: AgentResult | None, *, line_chars: int = 300
) -> str:
    """The run as the summary prompt reads it: pinned lines, then one line per event."""
    pinned: list[str] = []
    lines: list[str] = []
    for event in events:
        data = event.data
        if event.kind == "text":
            lines.append(f"agent: {_one_line(data.get('text', ''), line_chars)}")
        elif event.kind == "tool_call":
            args = json.dumps(data.get("input"), ensure_ascii=False)
            lines.append(f"tool call {data.get('tool')}: {_one_line(args, line_chars)}")
        elif event.kind == "tool_result":
            tag = "tool error" if data.get("is_error") else "tool result"
            lines.append(f"{tag}: {_one_line(data.get('output', ''), line_chars)}")
        elif event.kind in ("error", "status"):
            line = f"{event.kind}: {_one_line(data.get('message', ''), line_chars)}"
            lines.append(line)
            if event.kind == "error":
                pinned.append(line)
    if result is not None:
        state = f"failed: {_one_line(result.error or '', line_chars)}" if result.failed else "done"
        produced = f"; files: {', '.join(result.files[:20])}" if result.files else ""
        final = f"; final answer: {_one_line(result.final_text, line_chars)}" if result.final_text else ""
        pinned.insert(0, f"RUN ENDED ({state}){produced}{final}")
    head = "\n".join(f"PINNED {line}" for line in pinned)
    return "\n".join(part for part in (head, "\n".join(lines)) if part)


def _enforce_shape(text: str, settings: SummarySettings) -> str:
    """At most ``summary_bullets`` bullet lines (the newest kept), each clipped to its share."""
    bullets = [line.strip() for line in text.splitlines() if line.strip().startswith(("- ", "* "))]
    if not bullets:
        return ""
    kept = bullets[-settings.summary_bullets :]
    width = settings.bullet_max_chars
    return "\n".join("- " + (b[2:] if len(b) <= width else b[2 : width - 3].rstrip() + "...") for b in kept)


async def summarise_run(
    events: Iterable[AgentEvent],
    result: AgentResult | None,
    *,
    settings: SummarySettings | None = None,
    client: httpx.AsyncClient | None = None,
) -> Summary:
    """Three bullets on what the run did, from :func:`build_run_digest` of its events."""
    settings = settings or load_summary_settings()
    digest = build_run_digest(events, result, line_chars=settings.digest_line_chars)
    if not digest.strip():
        return Summary(error="the run has no events to summarise")
    system = _RUN_SYSTEM_PROMPT.format(
        bullets=settings.summary_bullets,
        item_max=settings.bullet_max_chars,
        total_max=settings.summary_max_chars,
    )
    prompt = (
        f"Whole-run digest, chronological (oldest to newest):\n\n{digest}\n\n"
        "Write the summary of the whole run from this digest alone. Output only the bullets."
    )
    summary = await summarise(
        prompt=prompt,
        system=system,
        background=True,
        max_output_tokens=settings.summary_max_chars // 4 + 200,
        settings=settings,
        client=client,
    )
    shaped = _enforce_shape(summary.text, settings)
    if summary.text and not shaped:
        summary.error = "the reply had no bullet lines"
    summary.text = shaped
    return summary


# ---------------------------------------------------------------------------
# The one-line label of a long answer
# ---------------------------------------------------------------------------

_LABEL_SYSTEM_PROMPT = """\
Compress one AI agent's output into a single one-line label.

THE LABEL IS ALL THE READER GETS. A label that only NAMES the subject
("Score", "Report", "Results") tells the reader nothing. Put the actual values
in the label itself: it must make sense on its own to someone who never opens
the output.

HARD LIMIT: 3-8 words, under {max_chars} characters. Longer output is cut.
Aim for {min_chars}-{max_chars} characters and carry two or three concrete
values; never pad with filler words.

LEAD WITH THE CONCRETE RESULT: the number, verdict, name, or file, not the
word for the kind of thing it is. "3 designs, best 0.94 F1 at 12 uW" beats
"Designs".

NEVER END ON A LABEL, A COLON, OR A DANGLING WORD.

Report what the output itself states: an announced intention or next step is
"started", never already done. Never invent values that are not in it.

FORMAT: plain ASCII only, at most one colon, digits for numbers, no ids or
hashes, never full paths or URLs.

STATE THE RESULT, NEVER NARRATE THE TASK. Never open with "The output", "This
message", "The agent", or "The user".

Return only the label."""


async def label_output(
    text: str,
    *,
    settings: SummarySettings | None = None,
    client: httpx.AsyncClient | None = None,
) -> Summary:
    """A one-line label for a long agent answer (the text is clipped first)."""
    settings = settings or load_summary_settings()
    clipped = text[: settings.label_max_input_chars]
    if len(text) > len(clipped):
        clipped += "... [truncated]"
    summary = await summarise(
        prompt=f"Label this agent output:\n\n{clipped}",
        system=_LABEL_SYSTEM_PROMPT.format(
            min_chars=settings.label_min_chars, max_chars=settings.label_max_chars
        ),
        label=True,
        max_output_tokens=64,
        min_words=3,
        settings=settings,
        client=client,
    )
    line = " ".join(summary.text.split())
    summary.text = line if len(line) <= 80 else line[:77].rstrip() + "..."
    return summary


__all__ = [
    "SETTINGS_PATH",
    "Summary",
    "SummarySettings",
    "build_run_digest",
    "label_output",
    "load_summary_settings",
    "summarise",
    "summarise_run",
]
