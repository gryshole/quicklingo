from __future__ import annotations

import asyncio

from PySide6.QtCore import QThread, Signal

from quicklingo.db.learning import QuizQuestionRecord
from quicklingo.learning.quiz.ai_quiz_service import AiQuizService
from quicklingo.learning.quiz.models import QuizQuestionType
from quicklingo.providers.registry import ModelEntry


class AiQuizRegenWorker(QThread):
    finished = Signal(object)
    error = Signal(str)
    progress = Signal(str)

    def __init__(
        self,
        card_id: int,
        question_type: QuizQuestionType,
        *,
        model_entry: ModelEntry,
        user_context: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._card_id = card_id
        self._question_type = question_type
        self._model_entry = model_entry
        self._user_context = user_context
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True
        self.requestInterruption()

    def _was_cancelled(self) -> bool:
        return self._cancelled or self.isInterruptionRequested()

    def run(self) -> None:
        try:
            record = asyncio.run(self._regenerate())
        except Exception as exc:
            if self._was_cancelled():
                return
            self.error.emit(str(exc))
            return
        if self._was_cancelled():
            return
        self.finished.emit(record)

    async def _regenerate(self) -> QuizQuestionRecord:
        service = AiQuizService()
        return await service.regenerate_question(
            self._card_id,
            self._question_type,
            self._model_entry,
            user_context=self._user_context,
            progress_cb=self.progress.emit,
            cancel_flag=self._was_cancelled,
        )
