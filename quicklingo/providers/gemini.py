import json
import os

import httpx

from quicklingo.providers.base import TranslationProvider

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
REQUEST_TIMEOUT = 30.0


class GeminiProvider(TranslationProvider):
    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key

    def _get_api_key(self) -> str:
        if self._api_key:
            return self._api_key
        return os.environ.get("GEMINI_API_KEY", "")

    async def translate(self, text: str, prompt: str, model: str) -> str:
        api_key = self._get_api_key()
        if not api_key or api_key == "your_key_here":
            raise ValueError("GEMINI_API_KEY не налаштовано. Додайте ключ у файл .env")

        url = GEMINI_API_URL.format(model=model)
        params = {"key": api_key}
        payload = {
            "systemInstruction": {"parts": [{"text": prompt}]},
            "contents": [{"role": "user", "parts": [{"text": text}]}],
            "generationConfig": {"temperature": 0.2},
        }

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.post(url, params=params, json=payload)
        except httpx.TimeoutException as exc:
            raise ConnectionError("Час очікування API минув. Спробуйте ще раз.") from exc
        except httpx.RequestError as exc:
            raise ConnectionError(f"Помилка мережі: {exc}") from exc

        if response.status_code in (401, 403):
            raise ValueError("Невірний GEMINI_API_KEY. Перевірте ключ у .env")
        if response.status_code >= 400:
            detail = _format_api_error(response)
            raise RuntimeError(f"Помилка Gemini API ({response.status_code}): {detail}")

        data = response.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("Неочікувана відповідь від Gemini API") from exc


def _format_api_error(response: httpx.Response) -> str:
    try:
        message = response.json()["error"]["message"]
    except (json.JSONDecodeError, KeyError, TypeError):
        message = response.text.strip() or response.reason_phrase

    if response.status_code == 503:
        return "Модель тимчасово перевантажена. Спробуйте іншу Gemini-модель або зачекайте."
    if response.status_code == 429:
        return "Перевищено ліміт запитів Gemini. Спробуйте пізніше або іншу модель."

    return message[:300]
