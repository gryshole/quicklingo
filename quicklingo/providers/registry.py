from dataclasses import dataclass

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


MODELS: list[ModelEntry] = [
    ModelEntry("llama-3.1-8b-instant", "Groq Llama 3.1 8B", _groq, "groq"),
    ModelEntry("llama-3.3-70b-versatile", "Groq Llama 3.3 70B", _groq, "groq"),
    ModelEntry("gemini-2.5-flash", "Gemini 2.5 Flash", _gemini, "gemini"),
    ModelEntry("gemini-2.5-flash-lite", "Gemini 2.5 Flash Lite", _gemini, "gemini"),
]


def get_model_entries() -> list[ModelEntry]:
    return MODELS


def get_model_by_index(index: int) -> ModelEntry:
    return MODELS[index]
