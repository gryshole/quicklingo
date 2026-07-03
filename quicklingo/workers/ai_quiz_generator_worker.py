from __future__ import annotations

import asyncio

from PySide6.QtCore import QThread, Signal

from quicklingo.db import learning
from quicklingo.learning.quiz.ai_quiz_service import AiQuizService
from quicklingo.learning.quiz.generation_outcome import QuizGenerationOutcome
from quicklingo.providers.registry import ModelEntry


class AiQuizGeneratorWorker(QThread):
    finished = Signal(object)
    error = Signal(str)
    progress = Signal(str)

    def __init__(
        self,
        deck_id: int,
        *,
        model_entry: ModelEntry,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._deck_id = deck_id
        self._model_entry = model_entry
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True
        self.requestInterruption()

    def _was_cancelled(self) -> bool:
        return self._cancelled or self.isInterruptionRequested()

    def _build_outcome(self, stats: learning.QuizCoverageStats) -> QuizGenerationOutcome:
        return QuizGenerationOutcome(
            stats=stats,
            cancelled=self._was_cancelled(),
            failed_questions=learning.count_failed_quiz_questions_for_deck(self._deck_id),
        )

    def run(self) -> None:
        stats = learning.get_quiz_coverage(self._deck_id)
        try:
            stats = asyncio.run(self._generate())
        except Exception as exc:
            if self._was_cancelled():
                self.finished.emit(self._build_outcome(stats))
                return
            self.error.emit(str(exc))
            return
        self.finished.emit(self._build_outcome(stats))

    async def _generate(self) -> learning.QuizCoverageStats:
        service = AiQuizService()
        return await service.generate_for_deck(
            self._deck_id,
            self._model_entry,
            progress_cb=self.progress.emit,
            cancel_flag=self._was_cancelled,
        )
