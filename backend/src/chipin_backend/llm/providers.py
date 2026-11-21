"""The provider registry: which OpenAI-compatible endpoint serves a model.

Each provider is a name, a base URL, the NAME of the environment variable that
holds its key, and a default model (``providers`` in the config). Keys are read
from the environment only and never printed or logged.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

from chipin_backend.config import ProviderConfig
from chipin_backend.llm.endpoints import BASE_URL
from chipin_backend.llm.keys import OPENROUTER_KEY_ENV, MissingKeyError

DEFAULT_PROVIDER = "openrouter"


class ProviderError(ValueError):
    """An unknown or unconfigured provider, or no model to use with it."""


@dataclass(frozen=True)
class Provider:
    """A configured provider, ready to call."""

    name: str
    base_url: str
    key_env: str
    default_model: str = ""

    def api_key(self) -> str:
        """The key from the environment; :class:`MissingKeyError` naming the variable if unset."""
        key = os.environ.get(self.key_env, "").strip() if self.key_env else ""
        if not key:
            raise MissingKeyError(
                f"provider {self.name!r} needs {self.key_env or 'a key variable'}, which is not set "
                "(export it or pass --env-file)"
            )
        return key

    def model_for(self, model: str | None, *, fallback: str = "") -> str:
        """``model``, else the provider default, else ``fallback``; :class:`ProviderError` if none."""
        chosen = (model or self.default_model or fallback).strip()
        if not chosen:
            raise ProviderError(
                f"provider {self.name!r} has no default model; pass --model (or set "
                f"providers.{self.name}.default_model)"
            )
        return chosen


def _registry(providers: Mapping[str, ProviderConfig]) -> Mapping[str, ProviderConfig]:
    """``providers`` with the built-in OpenRouter entry when the config has none."""
    if DEFAULT_PROVIDER in providers:
        return providers
    builtin = ProviderConfig(base_url=BASE_URL, key_env=OPENROUTER_KEY_ENV)
    return {DEFAULT_PROVIDER: builtin, **providers}


def resolve_provider(providers: Mapping[str, ProviderConfig], name: str | None = None) -> Provider:
    """The provider called ``name`` (default OpenRouter).

    :class:`ProviderError` for an unknown name, or for one whose base URL is
    empty (not configured), with the reason from its ``note``.
    """
    name = name or DEFAULT_PROVIDER
    registry = _registry(providers)
    if name not in registry:
        raise ProviderError(f"unknown provider {name!r}; known: {sorted(registry)}")
    cfg = registry[name]
    if not cfg.base_url.strip():
        why = cfg.note or f"not configured: set providers.{name}.base_url"
        raise ProviderError(f"provider {name!r}: {why}")
    return Provider(name, cfg.base_url.strip(), cfg.key_env, cfg.default_model)


def provider_status(providers: Mapping[str, ProviderConfig]) -> list[dict[str, object]]:
    """Per provider, by name only: whether it is configured and its key is present."""
    status: list[dict[str, object]] = []
    for name, cfg in _registry(providers).items():
        configured = bool(cfg.base_url.strip())
        has_key = bool(cfg.key_env and os.environ.get(cfg.key_env, "").strip())
        status.append({"name": name, "configured": configured, "key_present": configured and has_key})
    return status


__all__ = ["DEFAULT_PROVIDER", "Provider", "ProviderError", "provider_status", "resolve_provider"]
