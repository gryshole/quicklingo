from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from quicklingo.db import learning
from quicklingo.learning.image_resolver import fetch_card_image


class CardImageFetchWorker(QThread):
    finished_card = Signal(int, str)

    def __init__(
        self,
        deck_id: int,
        card_id: int,
        *,
        prompt: str,
        search_term: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._deck_id = deck_id
        self._card_id = card_id
        self._prompt = prompt.strip()
        self._search_term = search_term.strip()

    def run(self) -> None:
        if self.isInterruptionRequested() or not self._prompt:
            self.finished_card.emit(self._card_id, "")
            return
        rel = fetch_card_image(
            self._deck_id,
            self._card_id,
            prompt=self._prompt,
            search_term=self._search_term,
        )
        if rel:
            learning.update_card(self._card_id, image_path=rel)
        self.finished_card.emit(self._card_id, rel or "")
