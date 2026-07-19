from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx

from quicklingo import settings
from quicklingo.i18n.translator import TranslatableError
from quicklingo.providers.api_errors import raise_openai_compat_api_error
from quicklingo.providers.base import (
    REQUEST_TIMEOUT,
    TranslationProvider,
    iter_sse_json,
    map_network_errors,
)


class OpenAICompatProvider(TranslationProvider):
    def __init__(
        self,
        provider_id: str,
        default_base_url: str,
        *,
        auth_required: bool = True,
        extra_headers: dict[str, str] | None = None,
        base_url_resolver: Callable[[], str] | None = None,
    ) -> None:
        self._provider_id = provider_id
        self._default_base_url = default_base_url.rstrip("/")
        self._auth_required = auth_required
        self._extra_headers = extra_headers or {}
        self._base_url_resolver = base_url_resolver

    def _base_url(self) -> str:
        if self._base_url_resolver is not None:
            return self._base_url_resolver().rstrip("/")
        return self._default_base_url

    def _chat_url(self) -> str:
        return f"{self._base_url()}/chat/completions"

    def _get_api_key(self) -> str:
        return settings.get_api_key(self._provider_id)

    def _headers(self, api_key: str) -> dict[str, str]:
        headers = {"Content-Type": "application/json", **self._extra_headers}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def _unreachable_key(self) -> str | None:
        return "errors.ollama_unreachable" if self._provider_id == "ollama" else None

    def _payload(
        self, text: str, prompt: str, model: str, *, temperature: float, stream: bool
    ) -> dict[str, Any]:
        return {
            "model": model,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": text},
            ],
            "temperature": temperature,
            "stream": stream,
        }

    def _require_api_key(self) -> str:
        api_key = self._get_api_key()
        if self._auth_required and not api_key:
            raise TranslatableError(f"errors.{self._provider_id}_api_key_missing")
        return api_key

    async def translate(
        self,
        text: str,
        prompt: str,
        model: str,
        *,
        temperature: float = 0.2,
    ) -> str:
        api_key = self._require_api_key()
        payload = self._payload(text, prompt, model, temperature=temperature, stream=False)
        with map_network_errors(unreachable_key=self._unreachable_key()):
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.post(
                    self._chat_url(),
                    headers=self._headers(api_key),
                    json=payload,
                )

        if response.status_code == 401:
            raise TranslatableError(f"errors.{self._provider_id}_invalid_key")
        if response.status_code >= 400:
            raise_openai_compat_api_error(
                status_code=response.status_code,
                body=response.text.strip() or response.reason_phrase or "",
            )

        data = response.json()
        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise TranslatableError(f"errors.{self._provider_id}_unexpected") from exc

    async def translate_stream(
        self,
        text: str,
        prompt: str,
        model: str,
        *,
        temperature: float = 0.2,
    ) -> AsyncIterator[str]:
        api_key = self._require_api_key()
        payload = self._payload(text, prompt, model, temperature=temperature, stream=True)
        with map_network_errors(unreachable_key=self._unreachable_key()):
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                async with client.stream(
                    "POST",
                    self._chat_url(),
                    headers=self._headers(api_key),
                    json=payload,
                ) as response:
                    if response.status_code == 401:
                        raise TranslatableError(f"errors.{self._provider_id}_invalid_key")
                    if response.status_code >= 400:
                        body = (await response.aread()).decode("utf-8", errors="replace")
                        raise_openai_compat_api_error(
                            status_code=response.status_code,
                            body=body.strip() or response.reason_phrase or "",
                        )
                    async for chunk in iter_sse_json(response):
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        piece = delta.get("content")
                        if piece:
                            yield piece
