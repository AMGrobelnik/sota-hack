"""The OpenRouter key, read from the environment by name and never logged."""

from __future__ import annotations

import os
import re

OPENROUTER_KEY_ENV = "OPENROUTER_API_KEY"


#: OpenRouter's body for a key over its own credit cap. It comes with the same
#: 401/403 a wrong key gets, so only this text tells the two apart.
_KEY_LIMIT_TEXT = re.compile(r"key limit exceeded(?:\s*\((\w+) limit\))?", re.IGNORECASE)


class MissingKeyError(RuntimeError):
    """A required key is not set in the environment (or ``backend/.env``)."""


def openrouter_api_key() -> str:
    """The OpenRouter key; :class:`MissingKeyError` naming the variable if unset."""
    key = os.environ.get(OPENROUTER_KEY_ENV, "").strip()
    if not key:
        raise MissingKeyError(f"{OPENROUTER_KEY_ENV} is not set (see backend/.env.example)")
    return key


def has_openrouter_key() -> bool:
    """Whether the key is set, without exposing it."""
    return bool(os.environ.get(OPENROUTER_KEY_ENV, "").strip())


def is_key_exhausted(status: int | None, body: str | None) -> bool:
    """Whether a response means the key itself is out of credit or over its limit.

    A ``402``, or a ``401``/``403`` whose body says "Key limit exceeded". Such
    an answer must not be retried.
    """
    if status == 402:
        return True
    return status in (401, 403) and bool(_KEY_LIMIT_TEXT.search(body or ""))


__all__ = [
    "OPENROUTER_KEY_ENV",
    "MissingKeyError",
    "has_openrouter_key",
    "is_key_exhausted",
    "openrouter_api_key",
]
