"""Direct OpenRouter model access: client, key, retry policy and presets."""

from chipmonk_backend.llm.client import ChatResult, Message, ModelInfo, OpenRouterClient, OpenRouterError
from chipmonk_backend.llm.keys import MissingKeyError, has_openrouter_key, openrouter_api_key
from chipmonk_backend.llm.presets import resolve_model

__all__ = [
    "ChatResult",
    "Message",
    "MissingKeyError",
    "ModelInfo",
    "OpenRouterClient",
    "OpenRouterError",
    "has_openrouter_key",
    "openrouter_api_key",
    "resolve_model",
]
