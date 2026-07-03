from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Awaitable, Callable

from quicklingo.logging import ai_requests
from quicklingo.providers.base import TranslationProvider


class LoggingProviderWrapper(TranslationProvider):
    def __init__(self, inner: TranslationProvider, *, provider_id: str) -> None:
        self._inner = inner
        self._provider_id = provider_id

    async def translate(
        self,
        text: str,
        prompt: str,
        model: str,
        *,
        temperature: float = 0.2,
    ) -> str:
        return await self._run_logged(
            method="translate",
            coro_factory=lambda: self._inner.translate(
                text,
                prompt,
                model,
                temperature=temperature,
            ),
            system_text=prompt,
            user_text=text,
            model=model,
            temperature=temperature,
            stream=False,
        )

    async def translate_stream(
        self,
        text: str,
        prompt: str,
        model: str,
        *,
        temperature: float = 0.2,
    ) -> AsyncIterator[str]:
        purpose = ai_requests.current_purpose()
        ai_requests.log_request_start(
            provider_id=self._provider_id,
            model=model,
            method="translate_stream",
            purpose=purpose,
            stream=True,
            temperature=temperature,
            system_chars=len(prompt),
            user_chars=len(text),
        )
        ai_requests.log_request_prompts(system_text=prompt, user_text=text)

        started = time.perf_counter()
        parts: list[str] = []
        try:
            async for piece in self._inner.translate_stream(
                text,
                prompt,
                model,
                temperature=temperature,
            ):
                parts.append(piece)
                yield piece
        except asyncio.CancelledError:
            duration_ms = (time.perf_counter() - started) * 1000
            ai_requests.log_request_cancelled(
                provider_id=self._provider_id,
                model=model,
                method="translate_stream",
                purpose=purpose,
                duration_ms=duration_ms,
            )
            raise
        except Exception as exc:
            duration_ms = (time.perf_counter() - started) * 1000
            ai_requests.log_request_error(
                provider_id=self._provider_id,
                model=model,
                method="translate_stream",
                purpose=purpose,
                duration_ms=duration_ms,
                exc=exc,
            )
            raise

        response = "".join(parts)
        duration_ms = (time.perf_counter() - started) * 1000
        ai_requests.log_request_success(
            provider_id=self._provider_id,
            model=model,
            method="translate_stream",
            purpose=purpose,
            stream=True,
            duration_ms=duration_ms,
            response_chars=len(response),
            response_text=response,
        )

    async def complete(
        self,
        system: str,
        user: str,
        model: str,
        *,
        temperature: float = 0.2,
    ) -> str:
        return await self._run_logged(
            method="complete",
            coro_factory=lambda: self._inner.complete(
                system,
                user,
                model,
                temperature=temperature,
            ),
            system_text=system,
            user_text=user,
            model=model,
            temperature=temperature,
            stream=False,
        )

    async def _run_logged(
        self,
        *,
        method: str,
        coro_factory: Callable[[], Awaitable[str]],
        system_text: str,
        user_text: str,
        model: str,
        temperature: float,
        stream: bool,
    ) -> str:
        purpose = ai_requests.current_purpose()
        ai_requests.log_request_start(
            provider_id=self._provider_id,
            model=model,
            method=method,
            purpose=purpose,
            stream=stream,
            temperature=temperature,
            system_chars=len(system_text),
            user_chars=len(user_text),
        )
        ai_requests.log_request_prompts(system_text=system_text, user_text=user_text)

        started = time.perf_counter()
        try:
            result = await coro_factory()
        except asyncio.CancelledError:
            duration_ms = (time.perf_counter() - started) * 1000
            ai_requests.log_request_cancelled(
                provider_id=self._provider_id,
                model=model,
                method=method,
                purpose=purpose,
                duration_ms=duration_ms,
            )
            raise
        except Exception as exc:
            duration_ms = (time.perf_counter() - started) * 1000
            ai_requests.log_request_error(
                provider_id=self._provider_id,
                model=model,
                method=method,
                purpose=purpose,
                duration_ms=duration_ms,
                exc=exc,
            )
            raise

        duration_ms = (time.perf_counter() - started) * 1000
        ai_requests.log_request_success(
            provider_id=self._provider_id,
            model=model,
            method=method,
            purpose=purpose,
            stream=stream,
            duration_ms=duration_ms,
            response_chars=len(result),
            response_text=result,
        )
        return result
