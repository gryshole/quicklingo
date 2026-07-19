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

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MAX_TOKENS = 4096


class AnthropicProvider(TranslationProvider):
    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key

    def _get_api_key(self) -> str:
        if self._api_key:
            return self._api_key
        return settings.get_api_key("anthropic")

    def _headers(self, api_key: str) -> dict[str, str]:
        return {
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        }

    def _payload(
        self,
        text: str,
        prompt: str,
        model: str,
        *,
        temperature: float,
        stream: bool,
    ) -> dict[str, Any]:
        return {
            "model": model,
            "max_tokens": DEFAULT_MAX_TOKENS,
            "system": prompt,
            "messages": [{"role": "user", "content": text}],
            "temperature": temperature,
            "stream": stream,
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
            raise TranslatableError("errors.anthropic_api_key_missing")

        payload = self._payload(text, prompt, model, temperature=temperature, stream=False)
        with map_network_errors():
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.post(
                    ANTHROPIC_API_URL,
                    headers=self._headers(api_key),
                    json=payload,
                )

        if response.status_code in (401, 403):
            raise TranslatableError("errors.anthropic_invalid_key")
        if response.status_code == 429:
            raise TranslatableError("errors.anthropic_rate_limit")
        if response.status_code >= 400:
            detail = format_api_error(response)
            raise TranslatableError(
                "errors.api_error",
                status=response.status_code,
                detail=detail,
            )

        data = response.json()
        try:
            return data["content"][0]["text"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise TranslatableError("errors.anthropic_unexpected") from exc

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
            raise TranslatableError("errors.anthropic_api_key_missing")

        payload = self._payload(text, prompt, model, temperature=temperature, stream=True)
        with map_network_errors():
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                async with client.stream(
                    "POST",
                    ANTHROPIC_API_URL,
                    headers=self._headers(api_key),
                    json=payload,
                ) as response:
                    if response.status_code in (401, 403):
                        raise TranslatableError("errors.anthropic_invalid_key")
                    if response.status_code == 429:
                        raise TranslatableError("errors.anthropic_rate_limit")
                    if response.status_code >= 400:
                        body = (await response.aread()).decode("utf-8", errors="replace")
                        raise TranslatableError(
                            "errors.api_error",
                            status=response.status_code,
                            detail=body[:300],
                        )
                    async for chunk in iter_sse_json(response):
                        piece = _extract_anthropic_text(chunk)
                        if piece:
                            yield piece


def _extract_anthropic_text(chunk: dict[str, Any]) -> str:
    if chunk.get("type") != "content_block_delta":
        return ""
    delta = chunk.get("delta")
    if not isinstance(delta, dict) or delta.get("type") != "text_delta":
        return ""
    text = delta.get("text")
    return text if isinstance(text, str) else ""
