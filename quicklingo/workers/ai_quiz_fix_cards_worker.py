from __future__ import annotations

import asyncio
from dataclasses import dataclass

from PySide6.QtCore import QThread, Signal

from quicklingo.learning.quiz.ai_card_fix_service import AiQuizCardFixService, QuizCardFixResult
from quicklingo.providers.registry import ModelEntry


@dataclass(frozen=True)
class QuizFixOutcome:
    result: QuizCardFixResult
    cancelled: bool = False


class AiQuizFixCardsWorker(QThread):
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

    def run(self) -> None:
        result = QuizCardFixResult(fixed=0, failed=0, total=0)
        try:
            result = asyncio.run(self._fix())
        except Exception as exc:
            if self._was_cancelled():
                self.finished.emit(QuizFixOutcome(result=result, cancelled=True))
                return
            self.error.emit(str(exc))
            return
        self.finished.emit(QuizFixOutcome(result=result, cancelled=self._was_cancelled()))

    async def _fix(self) -> QuizCardFixResult:
        service = AiQuizCardFixService()
        return await service.fix_ineligible_for_deck(
            self._deck_id,
            self._model_entry,
            progress_cb=self.progress.emit,
            cancel_flag=self._was_cancelled,
        )
