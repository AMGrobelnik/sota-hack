r"""Typing a prompt into the ``claude`` TUI whole, and proving the transcript got it.

Adapted from AI Inventor.

* A prompt goes in as ONE bracketed paste (``ESC[200~`` ... ``ESC[201~``);
  typed raw, the CLI guesses the paste's extent from how the PTY slices it
  and under load kept only the last slice.
* :func:`typeable` drops the invisible characters the CLI strips on submit;
  when the CLI strips one itself it holds the prompt in the input box instead
  of sending it.
* :func:`check_delivery` fails loudly when the transcript journals less than
  was typed, rather than letting the agent work from a fragment.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from typing import Any

PASTE_START = "\x1b[200~"
PASTE_END = "\x1b[201~"


class PromptNotDeliveredError(TimeoutError):
    """The CLI journaled a turn that does not carry the whole prompt typed.

    A ``TimeoutError`` so the stall-restart path retries it.
    """


_STRIPPED_RANGES = (
    (0x00, 0x08),  # C0 controls but tab and newline
    (0x0B, 0x1F),
    (0x7F, 0x9F),  # DEL and C1
    (0x00AD, 0x00AD),  # soft hyphen
    (0x034F, 0x034F),  # combining grapheme joiner
    (0x061C, 0x061C),  # Arabic letter mark
    (0x115F, 0x1160),  # Hangul fillers
    (0x17B4, 0x17B5),  # Khmer inherent vowels
    (0x180B, 0x180F),  # Mongolian selectors and vowel separator
    (0x200B, 0x200F),  # zero width, LRM, RLM
    (0x2028, 0x202E),  # line/paragraph separators, bidi embeddings
    (0x2060, 0x206F),  # word joiner, invisible operators, bidi isolates
    (0x3164, 0x3164),  # Hangul filler
    (0xFE00, 0xFE0F),  # variation selectors
    (0xFEFF, 0xFEFF),  # byte order mark
    (0xFFA0, 0xFFA0),  # halfwidth Hangul filler
    (0xFFF0, 0xFFFB),  # interlinear annotation
    (0x1107F, 0x1107F),  # Brahmi number joiner
    (0x13430, 0x1343F),  # Egyptian hieroglyph format controls
    (0x16FE4, 0x16FE4),  # Khitan filler
    (0x1BCA0, 0x1BCA3),  # shorthand format controls
    (0x1D173, 0x1D17A),  # musical format controls
    (0xE0000, 0xE0FFF),  # tags and variation selectors supplement
)

_LINE_BREAKS = re.compile("\r\n?|[\x0b\x0c\x85\u2028\u2029]")
_MAYBE_INVISIBLE = re.compile("[^\t\n\x20-\x7e]")
_WS_RE = re.compile(r"\s+")
_PASTED_BLOCK_RE = re.compile(
    r'\n\n<pasted_content id="(?P<id>[^"\n]+)">\n(?P<body>.*?)\n</pasted_content id="(?P=id)">\n',
    re.DOTALL,
)


def invisible(char: str) -> bool:
    """Whether the CLI strips ``char`` from a prompt (and so holds the submit)."""
    if unicodedata.category(char) in ("Cf", "Cs"):
        return True
    cp = ord(char)
    return any(first <= cp <= last for first, last in _STRIPPED_RANGES)


def typeable(text: str) -> str:
    r"""``text`` as the CLI would submit it, safe inside a bracketed paste.

    Line breaks become ``\n`` and every :func:`invisible` character is
    dropped, ESC (which could end the paste early) among them.
    """
    text = _LINE_BREAKS.sub("\n", text)
    return _MAYBE_INVISIBLE.sub(lambda m: "" if invisible(m.group()) else m.group(), text)


def bracketed_paste(text: str) -> str:
    """``text`` framed as one bracketed paste. ``text`` must be :func:`typeable`."""
    return f"{PASTE_START}{text}{PASTE_END}"


def collapsed(text: str) -> str:
    """``text`` with every whitespace run flattened to one space, trimmed."""
    return _WS_RE.sub(" ", text).strip()


def expand_pasted_content(text: str) -> str:
    """``text`` with each ``<pasted_content>`` placeholder block replaced by the text pasted."""
    return _PASTED_BLOCK_RE.sub(lambda m: m.group("body"), text)


def typed_text(record: dict[str, Any]) -> str | None:
    """The text of a user turn someone typed, or ``None`` for any other record.

    Tool results, sidechain turns, meta records and compaction summaries are
    user-role records too; none of them was typed.
    """
    if record.get("type") != "user":
        return None
    if record.get("isMeta") or record.get("isSidechain") or record.get("isCompactSummary"):
        return None
    content = (record.get("message") or {}).get("content")
    if isinstance(content, list):
        if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
            return None
        content = "".join(
            b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
        )
    return content if isinstance(content, str) else None


def check_delivery(records: Iterable[dict[str, Any]], typed: str) -> bool:
    """Whether ``records`` hold the turn typed as ``typed``.

    ``False`` while no typed turn is journaled yet; ``True`` once the first
    one carries all of ``typed`` (whitespace-insensitive, pasted blocks
    expanded); :class:`PromptNotDeliveredError` when it is missing part.
    """
    for record in records:
        text = typed_text(record)
        if text is None:
            continue
        journaled = collapsed(expand_pasted_content(text))
        expected = collapsed(typed)
        if expected not in journaled:
            raise PromptNotDeliveredError(
                "REPL turn stalled (prompt not delivered whole: the transcript journaled "
                f"{len(journaled)} of its {len(expected)} characters)"
            )
        return True
    return False


__all__ = [
    "PromptNotDeliveredError",
    "bracketed_paste",
    "check_delivery",
    "collapsed",
    "expand_pasted_content",
    "typeable",
    "typed_text",
]
