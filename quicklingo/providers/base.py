from __future__ import annotations

import contextlib
import json
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Iterator

import httpx

from quicklingo.i18n.translator import TranslatableError

REQUEST_TIMEOUT = 30.0


@contextlib.contextmanager
def map_network_errors(*, unreachable_key: str | None = None) -> Iterator[None]:
    """Translate httpx transport errors into user-facing TranslatableError codes."""
    try:
        yield
    except httpx.TimeoutException as exc:
        raise TranslatableError("errors.api_timeout") from exc
    except httpx.RequestError as exc:
        key = unreachable_key or "errors.network"
        raise TranslatableError(key, detail=str(exc)) from exc


async def iter_sse_json(response: httpx.Response) -> AsyncIterator[dict]:
    """Yield decoded JSON objects from a Server-Sent Events response stream."""
    async for line in response.aiter_lines():
        if not line.startswith("data:"):
            continue
        data_str = line[5:].strip()
        if not data_str or data_str == "[DONE]":
            continue
        try:
            yield json.loads(data_str)
        except json.JSONDecodeError:
            continue


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
