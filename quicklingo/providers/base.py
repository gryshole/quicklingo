from abc import ABC, abstractmethod


class TranslationProvider(ABC):
    @abstractmethod
    async def translate(self, text: str, prompt: str, model: str) -> str:
        """Return translated text from the provider."""
