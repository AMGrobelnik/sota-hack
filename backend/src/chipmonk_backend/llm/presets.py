"""Short model names (``llm.presets`` in the config) resolved to OpenRouter ids."""

from __future__ import annotations

from collections.abc import Mapping


def resolve_model(name_or_id: str, presets: Mapping[str, str]) -> str:
    """The OpenRouter id for a preset name; an id (``vendor/model``) passes through.

    ``ValueError`` for a bare name that is not a preset, so a typo fails
    before a call is paid for.
    """
    if name_or_id in presets:
        return presets[name_or_id]
    if "/" in name_or_id:
        return name_or_id
    raise ValueError(f"{name_or_id!r} is neither a preset ({sorted(presets)}) nor a model id")


__all__ = ["resolve_model"]
