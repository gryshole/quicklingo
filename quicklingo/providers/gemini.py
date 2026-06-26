import json

import httpx

from quicklingo import settings
from quicklingo.i18n.translator import TranslatableError
from quicklingo.providers.base import TranslationProvider

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
REQUEST_TIMEOUT = 30.0


class GeminiProvider(TranslationProvider):
    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key

    def _get_api_key(self) -> str:
        if self._api_key:
            return self._api_key
        return settings.get_api_key("gemini")

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
        payload = {
            "systemInstruction": {"parts": [{"text": prompt}]},
            "contents": [{"role": "user", "parts": [{"text": text}]}],
            "generationConfig": {"temperature": temperature},
        }

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.post(url, params=params, json=payload)
        except httpx.TimeoutException as exc:
            raise TranslatableError("errors.api_timeout") from exc
        except httpx.RequestError as exc:
            raise TranslatableError("errors.network", detail=str(exc)) from exc

        if response.status_code in (401, 403):
            raise TranslatableError("errors.gemini_invalid_key")
        if response.status_code == 503:
            raise TranslatableError("errors.gemini_overloaded")
        if response.status_code == 429:
            raise TranslatableError("errors.gemini_rate_limit")
        if response.status_code >= 400:
            detail = _format_api_error(response)
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


def _format_api_error(response: httpx.Response) -> str:
    try:
        message = response.json()["error"]["message"]
    except (json.JSONDecodeError, KeyError, TypeError):
        message = response.text.strip() or response.reason_phrase
    return message[:300]
