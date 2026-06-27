from quicklingo import settings
from quicklingo.settings import API_PROVIDERS

__all__ = (
    "API_PROVIDERS",
    "KEY_PROVIDERS",
    "PROVIDER_HINT_KEYS",
    "provider_needs_api_key",
    "is_provider_configured",
)

KEY_PROVIDERS: tuple[str, ...] = (
    "groq",
    "gemini",
    "openrouter",
    "mistral",
    "deepseek",
    "openai",
    "anthropic",
)

PROVIDER_HINT_KEYS: dict[str, str] = {
    "groq": "settings.api_keys.hint_groq",
    "gemini": "settings.api_keys.hint_gemini",
    "openrouter": "settings.api_keys.hint_openrouter",
    "mistral": "settings.api_keys.hint_mistral",
    "ollama": "settings.api_keys.hint_ollama",
    "deepseek": "settings.api_keys.hint_deepseek",
    "openai": "settings.api_keys.hint_openai",
    "anthropic": "settings.api_keys.hint_anthropic",
}


def provider_needs_api_key(provider_id: str) -> bool:
    return provider_id in KEY_PROVIDERS


def is_provider_configured(provider_id: str) -> bool:
    if provider_id == "ollama":
        return bool(settings.get_ollama_base_url().strip())
    if provider_id in KEY_PROVIDERS:
        return bool(settings.get_api_key(provider_id))
    return False
