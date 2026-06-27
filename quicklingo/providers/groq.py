import json
from collections.abc import AsyncIterator

import httpx

from quicklingo import settings
from quicklingo.i18n.translator import TranslatableError
from quicklingo.providers.base import TranslationProvider

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
REQUEST_TIMEOUT = 30.0


class GroqProvider(TranslationProvider):
    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key

    def _get_api_key(self) -> str:
        if self._api_key:
            return self._api_key
        return settings.get_api_key("groq")

    def _headers(self, api_key: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def _payload(self, text: str, prompt: str, model: str, *, temperature: float, stream: bool) -> dict:
        return {
            "model": model,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": text},
            ],
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
            raise TranslatableError("errors.groq_api_key_missing")

        payload = self._payload(text, prompt, model, temperature=temperature, stream=False)
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.post(
                    GROQ_API_URL,
                    headers=self._headers(api_key),
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise TranslatableError("errors.api_timeout") from exc
        except httpx.RequestError as exc:
            raise TranslatableError("errors.network", detail=str(exc)) from exc

        if response.status_code == 401:
            raise TranslatableError("errors.groq_invalid_key")
        if response.status_code >= 400:
            detail = response.text.strip() or response.reason_phrase
            raise TranslatableError(
                "errors.api_error",
                status=response.status_code,
                detail=detail,
            )

        data = response.json()
        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise TranslatableError("errors.groq_unexpected") from exc

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
            raise TranslatableError("errors.groq_api_key_missing")

        payload = self._payload(text, prompt, model, temperature=temperature, stream=True)
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                async with client.stream(
                    "POST",
                    GROQ_API_URL,
                    headers=self._headers(api_key),
                    json=payload,
                ) as response:
                    if response.status_code == 401:
                        raise TranslatableError("errors.groq_invalid_key")
                    if response.status_code >= 400:
                        body = (await response.aread()).decode("utf-8", errors="replace")
                        detail = body.strip() or response.reason_phrase
                        raise TranslatableError(
                            "errors.api_error",
                            status=response.status_code,
                            detail=detail,
                        )
                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data_str = line[5:].strip()
                        if not data_str or data_str == "[DONE]":
                            continue
                        try:
                            chunk = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        piece = delta.get("content")
                        if piece:
                            yield piece
        except httpx.TimeoutException as exc:
            raise TranslatableError("errors.api_timeout") from exc
        except httpx.RequestError as exc:
            raise TranslatableError("errors.network", detail=str(exc)) from exc
