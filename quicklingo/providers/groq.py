import os

import httpx

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

    async def translate(self, text: str, prompt: str, model: str) -> str:
        api_key = self._get_api_key()
        if not api_key or api_key == "your_key_here":
            raise ValueError("GROQ_API_KEY не налаштовано. Додайте ключ у файл .env")

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
            "temperature": 0.2,
        }

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.post(GROQ_API_URL, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise ConnectionError("Час очікування API минув. Спробуйте ще раз.") from exc
        except httpx.RequestError as exc:
            raise ConnectionError(f"Помилка мережі: {exc}") from exc

        if response.status_code == 401:
            raise ValueError("Невірний GROQ_API_KEY. Перевірте ключ у .env")
        if response.status_code >= 400:
            detail = response.text.strip() or response.reason_phrase
            raise RuntimeError(f"Помилка API ({response.status_code}): {detail}")

        data = response.json()
        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("Неочікувана відповідь від Groq API") from exc
