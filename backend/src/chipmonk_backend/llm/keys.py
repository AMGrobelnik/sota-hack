"""The OpenRouter key, read from the environment by name and never logged."""

from __future__ import annotations

import os

OPENROUTER_KEY_ENV = "OPENROUTER_API_KEY"


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

    Such an answer must not be retried. Port the classification from AI
    Inventor's ``aii_lib/openrouter_key.py::is_key_exhausted`` (402, and 403
    whose body names a key limit).
    """
    raise NotImplementedError("port aii_lib/openrouter_key.py::is_key_exhausted")


__all__ = [
    "OPENROUTER_KEY_ENV",
    "MissingKeyError",
    "has_openrouter_key",
    "is_key_exhausted",
    "openrouter_api_key",
]
