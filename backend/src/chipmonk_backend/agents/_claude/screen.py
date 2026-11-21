"""Reading the ``claude`` terminal: startup dialogs, the mode marker, held submits.

Adapted from AI Inventor's ``_repl_driver/_dialogs.py``. The CLI renders a
blocking dialog on a config dir that has not answered it yet (the Bypass
Permissions warning, the auto-mode offer). A prompt typed into a dialog never
runs, so :class:`DialogPilot` answers each known dialog by its LABEL and the
start fails on any dialog it does not know.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_CSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")
_WS_RE = re.compile(r"\s+")

DOWN, ENTER, ESCAPE = "\x1b[B", "\r", "\x1b"
_KEY_NAMES = {DOWN: "DOWN", ENTER: "ENTER", ESCAPE: "ESC"}


def visible_text(pty_output: str) -> str:
    """Raw PTY bytes collapsed to the rendered text with no escapes and no whitespace.

    ``"⏵⏵ bypass permissions on"`` becomes ``"⏵⏵bypasspermissionson"``, whether
    the spaces arrived as spaces or as cursor-forward escapes.
    """
    return _WS_RE.sub("", _CSI_RE.sub("", pty_output))


@dataclass(frozen=True)
class _Dialog:
    """One blocking dialog: how it is recognised and how it is answered.

    ``accept`` names the option to pick by its label (walked to with Down,
    confirmed with Enter once the focus is on it); ``keys`` is a fixed answer.
    """

    name: str
    markers: tuple[str, ...]
    accept: str = ""
    keys: str = ""


_STARTUP_DIALOGS = (
    _Dialog("bypass", ("BypassPermissionsmode", "Yes,Iaccept"), accept="Yes,Iaccept"),
    _Dialog("auto-mode-offer", ("No,keepbypasspermissions",), keys=ESCAPE),
)

#: Footer of every CLI selection dialog; seen with no known dialog, it blocks.
_UNKNOWN_DIALOG_MARKER = "Entertoconfirm"

_FOCUS_GLYPH = "\u276f"  # the focus arrow
_OPTION_INDEX_RE = re.compile(r"^\d+[.)]")
_INDEX_ONLY_RE = re.compile(r"^\d+[.)]?$")
_PARTIAL_ESCAPE_RE = re.compile(r"\x1b(?:\[[0-?]*[ -/]*|\][^\x07\x1b]*)?$")
_NO_DRAW_RE = re.compile(r"\x1b\[\?[0-9;]*[hl]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b\[[IO]")

_REDRAW_S = 1.5
_MAX_DOWNS = 6
_MAX_CANCELS = 3
_WINDOW = 4096


def focused_label(pty_output: str) -> str | None:
    """The text after the last focus glyph, its option number dropped; ``None`` with no glyph."""
    seen = visible_text(_PARTIAL_ESCAPE_RE.sub("", pty_output))
    at = seen.rfind(_FOCUS_GLYPH)
    if at < 0:
        return None
    after = seen[at + 1 :]
    return "" if _INDEX_ONLY_RE.match(after) else _OPTION_INDEX_RE.sub("", after, count=1)


def draws_nothing(pty_output: str) -> bool:
    """Whether ``pty_output`` holds only escapes that draw nothing (or nothing at all)."""
    return not _NO_DRAW_RE.sub("", pty_output)


def _identify(seen: str) -> _Dialog | None:
    return next((d for d in _STARTUP_DIALOGS if all(m in seen for m in d.markers)), None)


class DialogPilot:
    """Answers one spawn's startup dialogs by label and refuses any other.

    :meth:`reply` reads only the PTY text written since the last key it
    pressed (the log is append-only, so a dismissed dialog's text would
    otherwise re-trigger). Enter goes only on a frame that shows the focus on
    the accepting label; a frame it cannot read gets no key, and
    :meth:`blocker` then fails the start.
    """

    def __init__(self) -> None:
        self._upto = 0
        self._dialog: _Dialog | None = None
        self._seen: list[str] = []
        self._sent: list[str] = []
        self._sent_at = 0.0
        self._focused = ""

    def reply(self, raw: str, *, now: float) -> str | None:
        """The key to press now for the PTY log ``raw``, or ``None``; a key returned is sent."""
        fresh = raw[self._upto :][-_WINDOW:]
        found = _identify(visible_text(fresh))
        if found is not None:
            self._dialog = found
            self._seen += [] if found.name in self._seen else [found.name]
        dialog = self._dialog
        if dialog is None:
            return None
        if dialog.keys:
            self._dialog = None
            if self._sent.count(_KEY_NAMES[dialog.keys]) >= _MAX_CANCELS:
                return None
            return self._press(dialog.keys, raw, now)
        focus = focused_label(fresh)
        if focus is None:
            late = now - self._sent_at >= _REDRAW_S
            key = DOWN if draws_nothing(fresh) and self._sent[-1:] == ["DOWN"] and late else None
        elif len(focus) < len(dialog.accept) and dialog.accept.startswith(focus):
            self._focused = focus
            key = None
        else:
            self._focused = focus[: len(dialog.accept)]
            key = ENTER if focus.startswith(dialog.accept) else DOWN
        if key is None or (key == DOWN and self._sent.count("DOWN") >= _MAX_DOWNS):
            return None
        if key == ENTER:
            self._dialog = None
        return self._press(key, raw, now)

    def _press(self, key: str, raw: str, now: float) -> str:
        self._sent.append(_KEY_NAMES[key])
        self._sent_at, self._upto = now, len(raw)
        return key

    def blocker(self, raw: str) -> str | None:
        """Why the screen in ``raw`` must not get the prompt, or ``None``."""
        fresh = raw[self._upto :][-_WINDOW:]
        seen = visible_text(fresh)
        if self._dialog is not None:
            why = f"the {self._dialog.name} dialog is still open, focus on {self._focused!r}"
        elif (drawn := _identify(seen)) is not None:
            why = f"the {drawn.name} dialog is still on screen with no key left for it"
        elif self._sent[-1:] in (["ENTER"], ["ESC"]) and not seen:
            why = f"the {self._seen[-1]} dialog drew nothing after its {self._sent[-1]}"
        elif _UNKNOWN_DIALOG_MARKER in seen:
            why = "a dialog the driver does not know is on screen (its text is in the PTY log)"
        else:
            return None
        return f"{why} [{self.report()}]"

    def report(self) -> str:
        """One line on this spawn's dialogs and the keys sent."""
        return (
            f"dialog={','.join(self._seen) or '-'} keys_sent={','.join(self._sent) or '-'} "
            f"focused={self._focused or '-'}"
        )


_RESUME_REFUSED_MARKER = "noconversationfound"

#: Status-line text proving a permission mode is live (in :func:`visible_text` form).
_MODE_STATUS_MARKERS = {"bypassPermissions": "bypasspermissionson"}

_SUBMIT_HELD_RE = re.compile(r"Removed\d+invisiblecharacters?.?(?:reviewandpress\w+tosend|nothinglefttosend)")


def resume_refused(pty_output: str) -> bool:
    """Whether ``pty_output`` shows the CLI declining a ``--resume`` id."""
    return _RESUME_REFUSED_MARKER in visible_text(pty_output).lower()


def permission_mode_marker(permission_mode: str) -> str | None:
    """The status-line marker proving ``permission_mode`` is actually live."""
    return _MODE_STATUS_MARKERS.get(permission_mode)


def submit_held(pty_output: str) -> str | None:
    """The CLI's hint when it holds a submit to strip invisible characters, else ``None``."""
    match = _SUBMIT_HELD_RE.search(visible_text(pty_output))
    return match.group() if match else None


__all__ = [
    "DialogPilot",
    "focused_label",
    "permission_mode_marker",
    "resume_refused",
    "submit_held",
    "visible_text",
]
