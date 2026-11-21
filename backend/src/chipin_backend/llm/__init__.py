"""Direct OpenRouter model access: client, key, retry policy, presets and summaries."""

from chipin_backend.llm.client import ChatResult, Message, ModelInfo, OpenRouterClient, OpenRouterError
from chipin_backend.llm.keys import MissingKeyError, has_openrouter_key, openrouter_api_key
from chipin_backend.llm.presets import resolve_model
from chipin_backend.llm.providers import Provider, ProviderError, provider_status, resolve_provider
from chipin_backend.llm.summarise import Summary, label_output, summarise_run

__all__ = [
    "ChatResult",
    "Message",
    "MissingKeyError",
    "ModelInfo",
    "OpenRouterClient",
    "OpenRouterError",
    "Provider",
    "ProviderError",
    "Summary",
    "has_openrouter_key",
    "label_output",
    "openrouter_api_key",
    "provider_status",
    "resolve_model",
    "resolve_provider",
    "summarise_run",
]
