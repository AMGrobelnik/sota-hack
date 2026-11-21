"""Every OpenRouter URL this backend calls, declared once."""

from __future__ import annotations

#: OpenAI-compatible API root; clients that append their own paths take this.
BASE_URL = "https://openrouter.ai/api/v1"
#: Model catalogue: pricing, context length, supported parameters.
MODELS_URL = f"{BASE_URL}/models"
#: Chat completions. Also the only honest "does this model serve today" probe.
CHAT_COMPLETIONS_URL = f"{BASE_URL}/chat/completions"
#: Key probe: the key's own limits and usage, spends nothing.
KEY_URL = f"{BASE_URL}/key"

__all__ = ["BASE_URL", "CHAT_COMPLETIONS_URL", "KEY_URL", "MODELS_URL"]
