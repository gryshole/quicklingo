from __future__ import annotations

from quicklingo import settings
from quicklingo.providers.openai_compat import OpenAICompatProvider


class OpenRouterProvider(OpenAICompatProvider):
    def __init__(self) -> None:
        super().__init__(
            "openrouter",
            "https://openrouter.ai/api/v1",
            extra_headers={
                "HTTP-Referer": "https://github.com/gryshole/quicklingo",
                "X-Title": "QuickLingo",
            },
        )


class MistralProvider(OpenAICompatProvider):
    def __init__(self) -> None:
        super().__init__("mistral", "https://api.mistral.ai/v1")


class OllamaProvider(OpenAICompatProvider):
    def __init__(self) -> None:
        super().__init__(
            "ollama",
            "http://localhost:11434/v1",
            auth_required=False,
            base_url_resolver=settings.get_ollama_base_url,
        )


class DeepSeekProvider(OpenAICompatProvider):
    def __init__(self) -> None:
        super().__init__("deepseek", "https://api.deepseek.com/v1")


class OpenAIProvider(OpenAICompatProvider):
    def __init__(self) -> None:
        super().__init__("openai", "https://api.openai.com/v1")
