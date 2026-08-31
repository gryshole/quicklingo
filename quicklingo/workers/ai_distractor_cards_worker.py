from __future__ import annotations

import asyncio

from PySide6.QtCore import QThread, Signal

from quicklingo.features import get_feature
from quicklingo.learning.quiz.ai_distractor_service import AiDistractorService
from quicklingo.learning.quiz.distractor_generation_outcome import DistractorGenerationOutcome
from quicklingo.providers.registry import ModelEntry


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
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._source_deck_id = source_deck_id
        self._words = list(words)
        self._model_entry = model_entry
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
        batch_size = max(1, int(quiz_feature.get("distractor_batch_size", 5)))
        service = AiDistractorService()
        return await service.generate_for_words(
            self._source_deck_id,
            self._words,
            self._model_entry,
            progress_cb=self.progress.emit,
            cancel_flag=self._was_cancelled,
            batch_size=batch_size,
        )
