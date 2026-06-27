import json
from collections.abc import AsyncIterator

import httpx

from quicklingo import settings
from quicklingo.i18n.translator import TranslatableError
from quicklingo.providers.base import TranslationProvider

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MAX_TOKENS = 4096
REQUEST_TIMEOUT = 30.0


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
    ) -> dict:
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
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.post(
                    ANTHROPIC_API_URL,
                    headers=self._headers(api_key),
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise TranslatableError("errors.api_timeout") from exc
        except httpx.RequestError as exc:
            raise TranslatableError("errors.network", detail=str(exc)) from exc

        if response.status_code in (401, 403):
            raise TranslatableError("errors.anthropic_invalid_key")
        if response.status_code == 429:
            raise TranslatableError("errors.anthropic_rate_limit")
        if response.status_code >= 400:
            detail = _format_api_error(response)
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
        try:
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
                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data_str = line[5:].strip()
                        if not data_str:
                            continue
                        try:
                            chunk = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue
                        piece = _extract_anthropic_text(chunk)
                        if piece:
                            yield piece
        except httpx.TimeoutException as exc:
            raise TranslatableError("errors.api_timeout") from exc
        except httpx.RequestError as exc:
            raise TranslatableError("errors.network", detail=str(exc)) from exc


def _extract_anthropic_text(chunk: dict) -> str:
    if chunk.get("type") != "content_block_delta":
        return ""
    delta = chunk.get("delta")
    if not isinstance(delta, dict) or delta.get("type") != "text_delta":
        return ""
    text = delta.get("text")
    return text if isinstance(text, str) else ""


def _format_api_error(response: httpx.Response) -> str:
    try:
        body = response.json()
        error = body.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str):
                return message[:300]
    except (json.JSONDecodeError, TypeError):
        pass
    return (response.text.strip() or response.reason_phrase or "")[:300]
