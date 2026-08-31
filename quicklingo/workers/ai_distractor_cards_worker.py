from __future__ import annotations

import asyncio
import time

from PySide6.QtCore import QThread, Signal

from quicklingo.features import get_feature
from quicklingo.learning.quiz.ai_distractor_service import AiDistractorService
from quicklingo.learning.quiz.distractor_generation_outcome import DistractorGenerationOutcome
from quicklingo.learning.quiz.distractor_words import collect_missing_distractor_words
from quicklingo.providers.registry import ModelEntry

_RATE_LIMIT_WAIT_PADDING_SEC = 2.0


def _format_elapsed(seconds: int) -> str:
    minutes, secs = divmod(max(0, seconds), 60)
    if minutes:
        return f"{minutes}:{secs:02d}"
    return f"{secs}s"


def _auto_loop_done_count(source_deck_id: int, initial_total: int) -> int:
    remaining = len(collect_missing_distractor_words(source_deck_id))
    return max(0, initial_total - remaining)


class AiDistractorCardsWorker(QThread):
    finished = Signal(object)
    error = Signal(str)
    progress = Signal(str)

    def __init__(
        self,
        source_deck_id: int,
        words: list[str],
        *,
        model_entry: ModelEntry,
        continuous_on_rate_limit: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._source_deck_id = source_deck_id
        self._words = list(words)
        self._model_entry = model_entry
        self._continuous_on_rate_limit = continuous_on_rate_limit
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True
        self.requestInterruption()

    def _was_cancelled(self) -> bool:
        return self._cancelled or self.isInterruptionRequested()

    def run(self) -> None:
        try:
            outcome = asyncio.run(self._generate())
        except Exception as exc:
            if self._was_cancelled():
                return
            self.error.emit(str(exc))
            return
        if self._was_cancelled() and not outcome.cancelled:
            outcome = DistractorGenerationOutcome(
                created=outcome.created,
                cancelled=True,
                rate_limited=outcome.rate_limited,
                total_attempted=outcome.total_attempted,
                retry_seconds=outcome.retry_seconds,
            )
        self.finished.emit(outcome)

    async def _generate(self) -> DistractorGenerationOutcome:
        quiz_feature = get_feature("learning.quiz")
        word_delay_sec = max(0.0, float(quiz_feature.get("distractor_word_delay_sec", 3)))
        batch_size = max(1, int(quiz_feature.get("distractor_batch_size", 5)))
        if self._continuous_on_rate_limit:
            return await self._generate_continuous(batch_size, word_delay_sec)
        service = AiDistractorService()
        return await service.generate_for_words(
            self._source_deck_id,
            self._words,
            self._model_entry,
            progress_cb=self.progress.emit,
            cancel_flag=self._was_cancelled,
            word_delay_sec=word_delay_sec,
            batch_size=batch_size,
        )

    async def _generate_continuous(
        self,
        batch_size: int,
        word_delay_sec: float,
    ) -> DistractorGenerationOutcome:
        from quicklingo.i18n import tr

        service = AiDistractorService()
        total_created = 0
        loop_start = time.monotonic()
        initial_total = len(collect_missing_distractor_words(self._source_deck_id))
        if initial_total <= 0:
            initial_total = len(self._words)

        def _emit_rate_limit_wait(wait_seconds: int) -> None:
            done = _auto_loop_done_count(self._source_deck_id, initial_total)
            elapsed = int(time.monotonic() - loop_start)
            self.progress.emit(
                tr(
                    "learning.quiz_distractor_cards_auto_wait",
                    wait=wait_seconds,
                    done=done,
                    total=initial_total,
                    elapsed=_format_elapsed(elapsed),
                )
            )

        def _emit_auto_progress(detail: str) -> None:
            done = _auto_loop_done_count(self._source_deck_id, initial_total)
            elapsed = int(time.monotonic() - loop_start)
            self.progress.emit(
                tr(
                    "learning.quiz_distractor_cards_auto_progress",
                    detail=detail,
                    done=done,
                    total=initial_total,
                    elapsed=_format_elapsed(elapsed),
                )
            )

        while not self._was_cancelled():
            words = collect_missing_distractor_words(self._source_deck_id)
            if not words:
                return DistractorGenerationOutcome(
                    created=total_created,
                    cancelled=False,
                    rate_limited=False,
                    total_attempted=0,
                )

            batch_words = words[:batch_size]
            outcome = await service.generate_for_words(
                self._source_deck_id,
                batch_words,
                self._model_entry,
                progress_cb=_emit_auto_progress,
                cancel_flag=self._was_cancelled,
                word_delay_sec=0,
                batch_size=batch_size,
                retry_on_rate_limit=True,
                rate_limit_padding_sec=_RATE_LIMIT_WAIT_PADDING_SEC,
                rate_limit_wait_cb=_emit_rate_limit_wait,
            )
            total_created += outcome.created

            if self._was_cancelled():
                return DistractorGenerationOutcome(
                    created=total_created,
                    cancelled=True,
                    rate_limited=False,
                    total_attempted=len(batch_words),
                    retry_seconds=outcome.retry_seconds,
                )

            if not collect_missing_distractor_words(self._source_deck_id):
                return DistractorGenerationOutcome(
                    created=total_created,
                    cancelled=False,
                    rate_limited=False,
                    total_attempted=len(batch_words),
                )

            if outcome.rate_limited:
                await asyncio.sleep(3.0)
            elif outcome.created == 0:
                await asyncio.sleep(3.0)
            elif word_delay_sec > 0:
                await asyncio.sleep(word_delay_sec)

        return DistractorGenerationOutcome(
            created=total_created,
            cancelled=True,
            rate_limited=False,
            total_attempted=0,
        )
