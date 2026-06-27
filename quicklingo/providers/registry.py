from dataclasses import dataclass

from quicklingo import settings
from quicklingo.providers.base import TranslationProvider
from quicklingo.providers.gemini import GeminiProvider
from quicklingo.providers.groq import GroqProvider

_groq = GroqProvider()
_gemini = GeminiProvider()


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
)

_PROVIDERS: dict[str, TranslationProvider] = {
    "groq": _groq,
    "gemini": _gemini,
}

MODEL_CATALOG: list[ModelEntry] = [
    ModelEntry(model_id, display_name, _PROVIDERS[api_provider], api_provider)
    for model_id, display_name, api_provider in _CATALOG_SPECS
]

_CATALOG_BY_ID: dict[str, ModelEntry] = {entry.model_id: entry for entry in MODEL_CATALOG}


def infer_api_provider(model_id: str) -> str:
    _, provider = parse_model_id(model_id)
    return provider


def parse_model_id(model_id: str) -> tuple[str, str]:
    cleaned = model_id.strip()
    lowered = cleaned.lower()
    for prefix, provider in (("groq:", "groq"), ("gemini:", "gemini")):
        if lowered.startswith(prefix):
            rest = cleaned[len(prefix) :].strip()
            if rest:
                return rest, provider
    normalized = cleaned.lower()
    if normalized.startswith("gemini"):
        return cleaned, "gemini"
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
