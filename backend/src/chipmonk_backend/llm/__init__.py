"""Direct OpenRouter model access: client, key, retry policy, presets and summaries."""

from chipmonk_backend.llm.client import ChatResult, Message, ModelInfo, OpenRouterClient, OpenRouterError
from chipmonk_backend.llm.keys import MissingKeyError, has_openrouter_key, openrouter_api_key
from chipmonk_backend.llm.presets import resolve_model
from chipmonk_backend.llm.summarise import Summary, label_output, summarise_run

__all__ = [
    "ChatResult",
    "Message",
    "MissingKeyError",
    "ModelInfo",
    "OpenRouterClient",
    "OpenRouterError",
    "Summary",
    "has_openrouter_key",
    "label_output",
    "openrouter_api_key",
    "resolve_model",
    "summarise_run",
]
