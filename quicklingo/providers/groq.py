import os

import httpx

from quicklingo.i18n.translator import TranslatableError, translate_message
from quicklingo.providers.base import TranslationProvider

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
REQUEST_TIMEOUT = 30.0


class GroqProvider(TranslationProvider):
    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key

    def _get_api_key(self) -> str:
        if self._api_key:
            return self._api_key
        return os.environ.get("GROQ_API_KEY", "")

    async def translate(
        self,
        text: str,
        prompt: str,
        model: str,
        *,
        temperature: float = 0.2,
    ) -> str:
        api_key = self._get_api_key()
        if not api_key or api_key == "your_key_here":
            raise TranslatableError("errors.groq_api_key_missing")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": text},
            ],
            "temperature": temperature,
        }

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.post(GROQ_API_URL, headers=headers, json=payload)
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
