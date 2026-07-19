from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx

from quicklingo import settings
from quicklingo.i18n.translator import TranslatableError
from quicklingo.providers.api_errors import format_api_error
from quicklingo.providers.base import (
    REQUEST_TIMEOUT,
    TranslationProvider,
    iter_sse_json,
    map_network_errors,
)

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GEMINI_STREAM_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent"
)


class GeminiProvider(TranslationProvider):
    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key

    def _get_api_key(self) -> str:
        if self._api_key:
            return self._api_key
        return settings.get_api_key("gemini")

    def _payload(self, text: str, prompt: str, *, temperature: float) -> dict[str, Any]:
        return {
            "systemInstruction": {"parts": [{"text": prompt}]},
            "contents": [{"role": "user", "parts": [{"text": text}]}],
            "generationConfig": {"temperature": temperature},
        }

    async def translate(
        self,
        text: str,
        prompt: str,
        model: str,
        *,
        temperature: float = 0.2,
    ) -> str:
        api_key = self._get_api_key()
        if not api_key:
            raise TranslatableError("errors.gemini_api_key_missing")

        url = GEMINI_API_URL.format(model=model)
        params = {"key": api_key}
        payload = self._payload(text, prompt, temperature=temperature)

        with map_network_errors():
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.post(url, params=params, json=payload)

        if response.status_code in (401, 403):
            raise TranslatableError("errors.gemini_invalid_key")
        if response.status_code == 503:
            raise TranslatableError("errors.gemini_overloaded")
        if response.status_code == 429:
            raise TranslatableError("errors.gemini_rate_limit")
        if response.status_code >= 400:
            detail = format_api_error(response)
            raise TranslatableError(
                "errors.gemini_api",
                status=response.status_code,
                detail=detail,
            )

        data = response.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise TranslatableError("errors.gemini_unexpected") from exc

    async def translate_stream(
        self,
        text: str,
        prompt: str,
        model: str,
        *,
        temperature: float = 0.2,
    ) -> AsyncIterator[str]:
        api_key = self._get_api_key()
        if not api_key:
            raise TranslatableError("errors.gemini_api_key_missing")

        url = GEMINI_STREAM_URL.format(model=model)
        params = {"key": api_key, "alt": "sse"}
        payload = self._payload(text, prompt, temperature=temperature)

        with map_network_errors():
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                async with client.stream(
                    "POST",
                    url,
                    params=params,
                    json=payload,
                ) as response:
                    if response.status_code in (401, 403):
                        raise TranslatableError("errors.gemini_invalid_key")
                    if response.status_code == 503:
                        raise TranslatableError("errors.gemini_overloaded")
                    if response.status_code == 429:
                        raise TranslatableError("errors.gemini_rate_limit")
                    if response.status_code >= 400:
                        body = (await response.aread()).decode("utf-8", errors="replace")
                        raise TranslatableError(
                            "errors.gemini_api",
                            status=response.status_code,
                            detail=body[:300],
                        )
                    async for chunk in iter_sse_json(response):
                        piece = _extract_gemini_text(chunk)
                        if piece:
                            yield piece


def _extract_gemini_text(chunk: dict[str, Any]) -> str:
    try:
        parts = chunk["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError, TypeError):
        return ""
    text_parts: list[str] = []
    for part in parts:
        if isinstance(part, dict) and part.get("text"):
            text_parts.append(str(part["text"]))
    return "".join(text_parts)
