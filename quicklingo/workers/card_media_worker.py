from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from quicklingo.db import learning
from quicklingo.features import get_feature, is_enabled
from quicklingo.learning.image_resolver import fetch_card_image
from quicklingo.learning.pronunciation import ensure_card_pronunciation


class CardMediaWorker(QThread):
    progress = Signal(str)
    finished = Signal(int)
    error = Signal(str)

    def __init__(
        self,
        deck_id: int,
        card_ids: list[int],
        *,
        direction: str,
        image_prompts: dict[int, str] | None = None,
        imageable: dict[int, bool] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._deck_id = deck_id
        self._card_ids = card_ids
        self._direction = direction
        self._image_prompts = image_prompts or {}
        self._imageable = imageable or {}
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True
        self.requestInterruption()

    def run(self) -> None:
        try:
            self._process()
        except Exception as exc:
            if not self._cancelled:
                self.error.emit(str(exc))
            return
        if not self._cancelled:
            self.finished.emit(self._deck_id)

    def _process(self) -> None:
        images_enabled = is_enabled("learning.card_images")
        pronunciation_enabled = is_enabled("learning.card_pronunciation")
        max_images = int(get_feature("learning.card_images").get("max_images_per_batch", 25))
        images_done = 0

        for index, card_id in enumerate(self._card_ids, start=1):
            if self._cancelled:
                return
            card = learning.get_card(card_id)
            if card is None:
                continue
            self.progress.emit(f"{index}/{len(self._card_ids)}")

            if pronunciation_enabled and not card.audio_path:
                ensure_card_pronunciation(card_id, direction=self._direction)

            if images_enabled and images_done < max_images and self._imageable.get(card_id, False):
                if not card.image_path:
                    prompt = self._image_prompts.get(card_id, card.image_prompt)
                    rel = fetch_card_image(
                        self._deck_id,
                        card_id,
                        prompt=prompt,
                        search_term=card.front,
                    )
                    if rel:
                        learning.update_card(card_id, image_path=rel, image_prompt=prompt)
                        images_done += 1
