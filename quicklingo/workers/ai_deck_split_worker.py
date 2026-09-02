from __future__ import annotations

import asyncio

from PySide6.QtCore import QThread, Signal

from quicklingo.learning.deck_split.models import DeckSplitAnalysisResult
from quicklingo.learning.deck_split.service import AiDeckSplitService
from quicklingo.providers.registry import ModelEntry


class AiDeckSplitWorker(QThread):
    finished = Signal(object)
    error = Signal(str)

    def __init__(
        self,
        deck_id: int,
        *,
        model_entry: ModelEntry,
        user_note: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._deck_id = deck_id
        self._model_entry = model_entry
        self._user_note = user_note
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True
        self.requestInterruption()

    def _was_cancelled(self) -> bool:
        return self._cancelled or self.isInterruptionRequested()

    def run(self) -> None:
        try:
            result = asyncio.run(self._analyze())
        except Exception as exc:
            if self._was_cancelled():
                self.finished.emit(None)
                return
            self.error.emit(str(exc))
            return
        if self._was_cancelled():
            self.finished.emit(None)
            return
        self.finished.emit(result)

    async def _analyze(self) -> DeckSplitAnalysisResult:
        service = AiDeckSplitService()
        return await service.analyze_deck(
            self._deck_id,
            self._model_entry,
            user_note=self._user_note,
            cancel_flag=self._was_cancelled,
        )
