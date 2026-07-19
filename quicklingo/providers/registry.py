from __future__ import annotations

from dataclasses import dataclass

from quicklingo import settings
from quicklingo.providers.anthropic import AnthropicProvider
from quicklingo.providers.base import TranslationProvider
from quicklingo.providers.extra_providers import (
    DeepSeekProvider,
    MistralProvider,
    OllamaProvider,
    OpenAIProvider,
    OpenRouterProvider,
)
from quicklingo.providers.gemini import GeminiProvider
from quicklingo.providers.groq import GroqProvider
from quicklingo.providers.logging_wrapper import LoggingProviderWrapper


def _wrap_provider(provider_id: str, provider: TranslationProvider) -> TranslationProvider:
    return LoggingProviderWrapper(provider, provider_id=provider_id)


_groq = _wrap_provider("groq", GroqProvider())
_gemini = _wrap_provider("gemini", GeminiProvider())
_openrouter = _wrap_provider("openrouter", OpenRouterProvider())
_mistral = _wrap_provider("mistral", MistralProvider())
_ollama = _wrap_provider("ollama", OllamaProvider())
_deepseek = _wrap_provider("deepseek", DeepSeekProvider())
_openai = _wrap_provider("openai", OpenAIProvider())
_anthropic = _wrap_provider("anthropic", AnthropicProvider())


@dataclass(frozen=True)
class ModelEntry:
    model_id: str
    display_name: str
    provider: TranslationProvider
    api_provider: str


DEFAULT_MAIN_MODEL_IDS: tuple[str, ...] = (
    "llama-3.1-8b-instant",
    "llama-3.3-70b-versatile",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
)

_CATALOG_SPECS: tuple[tuple[str, str, str], ...] = (
    ("llama-3.1-8b-instant", "Groq Llama 3.1 8B", "groq"),
    ("llama-3.3-70b-versatile", "Groq Llama 3.3 70B", "groq"),
    ("openai/gpt-oss-20b", "Groq GPT-OSS 20B", "groq"),
    ("openai/gpt-oss-120b", "Groq GPT-OSS 120B", "groq"),
    ("meta-llama/llama-4-scout-17b-16e-instruct", "Groq Llama 4 Scout 17B", "groq"),
    ("qwen/qwen3-32b", "Groq Qwen3 32B", "groq"),
    ("qwen/qwen3.6-27b", "Groq Qwen3.6 27B", "groq"),
    ("gemini-2.5-flash", "Gemini 2.5 Flash", "gemini"),
    ("gemini-3.5-flash", "Gemini 3.5 Flash", "gemini"),
    ("gemini-3.1-pro-preview", "Gemini 3.1 Pro Preview", "gemini"),
    ("gemini-2.5-pro", "Gemini 2.5 Pro", "gemini"),
    ("gemini-2.5-flash-lite", "Gemini 2.5 Flash Lite", "gemini"),
    ("gemini-3.1-flash-lite", "Gemini 3.1 Flash Lite", "gemini"),
    ("gemini-2.0-flash", "Gemini 2.0 Flash", "gemini"),
    ("gemini-2.0-flash-lite", "Gemini 2.0 Flash Lite", "gemini"),
    ("meta-llama/llama-3.3-70b-instruct:free", "OR Llama 3.3 70B (free)", "openrouter"),
    ("google/gemma-3-27b-it:free", "OR Gemma 3 27B (free)", "openrouter"),
    ("mistralai/mistral-small-3.1-24b-instruct:free", "OR Mistral Small 3.1 (free)", "openrouter"),
    ("mistral-small-latest", "Mistral Small", "mistral"),
    ("open-mixtral-8x7b", "Mistral Mixtral 8x7B", "mistral"),
    ("codestral-latest", "Mistral Codestral", "mistral"),
    ("llama3.2", "Ollama Llama 3.2", "ollama"),
    ("mistral", "Ollama Mistral", "ollama"),
    ("qwen2.5", "Ollama Qwen 2.5", "ollama"),
    ("gemma2", "Ollama Gemma 2", "ollama"),
    ("deepseek-chat", "DeepSeek Chat", "deepseek"),
    ("deepseek-reasoner", "DeepSeek Reasoner", "deepseek"),
    ("gpt-4o-mini", "GPT-4o mini", "openai"),
    ("gpt-4o", "GPT-4o", "openai"),
    ("claude-sonnet-4-20250514", "Claude Sonnet 4", "anthropic"),
    ("claude-3-5-haiku-20241022", "Claude 3.5 Haiku", "anthropic"),
)

_PROVIDERS: dict[str, TranslationProvider] = {
    "groq": _groq,
    "gemini": _gemini,
    "openrouter": _openrouter,
    "mistral": _mistral,
    "ollama": _ollama,
    "deepseek": _deepseek,
    "openai": _openai,
    "anthropic": _anthropic,
}

MODEL_CATALOG: list[ModelEntry] = [
    ModelEntry(model_id, display_name, _PROVIDERS[api_provider], api_provider)
    for model_id, display_name, api_provider in _CATALOG_SPECS
]

_CATALOG_BY_ID: dict[str, ModelEntry] = {entry.model_id: entry for entry in MODEL_CATALOG}

_PREFIX_PROVIDERS: tuple[tuple[str, str], ...] = (
    ("groq:", "groq"),
    ("gemini:", "gemini"),
    ("openrouter:", "openrouter"),
    ("mistral:", "mistral"),
    ("ollama:", "ollama"),
    ("deepseek:", "deepseek"),
    ("openai:", "openai"),
    ("anthropic:", "anthropic"),
)


def parse_model_id(model_id: str) -> tuple[str, str]:
    cleaned = model_id.strip()
    lowered = cleaned.lower()
    for prefix, provider in _PREFIX_PROVIDERS:
        if lowered.startswith(prefix):
            rest = cleaned[len(prefix) :].strip()
            if rest:
                return rest, provider
    normalized = cleaned.lower()
    if normalized.startswith("gemini"):
        return cleaned, "gemini"
    if normalized.startswith("claude"):
        return cleaned, "anthropic"
    if normalized.startswith("gpt-"):
        return cleaned, "openai"
    if normalized.startswith("deepseek"):
        return cleaned, "deepseek"
    if normalized.startswith("mistral") or normalized.startswith("codestral"):
        return cleaned, "mistral"
    return cleaned, "groq"


def resolve_model_entry(
    model_id: str,
    *,
    provider: str | None = None,
) -> ModelEntry | None:
    cleaned, inferred = parse_model_id(model_id)
    if not cleaned:
        return None
    entry = _CATALOG_BY_ID.get(cleaned)
    if entry is not None:
        return entry
    api_provider = provider if provider in _PROVIDERS else inferred
    return ModelEntry(
        cleaned,
        cleaned,
        _PROVIDERS[api_provider],
        api_provider,
    )


def get_model_catalog() -> list[ModelEntry]:
    return list(MODEL_CATALOG)


def get_model_entry(model_id: str) -> ModelEntry | None:
    return _CATALOG_BY_ID.get(model_id)


def get_main_model_ids() -> list[str]:
    stored = settings.get_main_model_ids()
    if stored:
        return stored
    return list(DEFAULT_MAIN_MODEL_IDS)


def get_model_entries() -> list[ModelEntry]:
    custom_providers = settings.get_custom_model_providers()
    entries: list[ModelEntry] = []
    for model_id in get_main_model_ids():
        entry = resolve_model_entry(
            model_id,
            provider=custom_providers.get(model_id),
        )
        if entry is not None:
            entries.append(entry)
    if entries:
        return entries
    return [
        _CATALOG_BY_ID[model_id]
        for model_id in DEFAULT_MAIN_MODEL_IDS
        if model_id in _CATALOG_BY_ID
    ]


def get_model_by_index(index: int) -> ModelEntry:
    entries = get_model_entries()
    if not entries:
        raise IndexError("no models configured")
    if index < 0 or index >= len(entries):
        return entries[0]
    return entries[index]
