from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from quicklingo.db import learning
from quicklingo.features import get_feature, is_enabled
from quicklingo.learning.image_resolver import fetch_card_image, resolve_image_path


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


class CardImagePrefetchWorker(QThread):
    """Background-fetch illustrations for cards that already have image_prompt."""

    card_ready = Signal(int, str)
    finished_all = Signal()

    def __init__(
        self,
        deck_id: int,
        cards: list[learning.LearningCard],
        *,
        limit: int | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._deck_id = deck_id
        self._cards = list(cards)
        if limit is None:
            limit = int(get_feature("learning.card_images").get("max_images_per_batch", 25))
        self._limit = max(0, limit)

    def run(self) -> None:
        if not is_enabled("learning.card_images") or self._limit <= 0:
            self.finished_all.emit()
            return
        done = 0
        for card in self._cards:
            if self.isInterruptionRequested() or done >= self._limit:
                break
            prompt = (card.image_prompt or "").strip()
            if not prompt:
                continue
            if card.image_path and resolve_image_path(card.image_path):
                continue
            rel = fetch_card_image(
                self._deck_id,
                card.id,
                prompt=prompt,
                search_term=card.front or "",
            )
            if self.isInterruptionRequested():
                break
            if rel:
                learning.update_card(card.id, image_path=rel)
                self.card_ready.emit(card.id, rel)
                done += 1
        self.finished_all.emit()
