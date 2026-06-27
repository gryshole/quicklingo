from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class TranslationProvider(ABC):
    @abstractmethod
    async def translate(
        self,
        text: str,
        prompt: str,
        model: str,
        *,
        temperature: float = 0.2,
    ) -> str:
        """Return translated text from the provider."""

    async def translate_stream(
        self,
        text: str,
        prompt: str,
        model: str,
        *,
        temperature: float = 0.2,
    ) -> AsyncIterator[str]:
        result = await self.translate(text, prompt, model, temperature=temperature)
        yield result

    async def complete(
        self,
        system: str,
        user: str,
        model: str,
        *,
        temperature: float = 0.2,
    ) -> str:
        return await self.translate(user, system, model, temperature=temperature)
