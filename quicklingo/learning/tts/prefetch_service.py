from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import QObject, Signal

from quicklingo.db import learning
from quicklingo.features import is_enabled
from quicklingo.learning.pronunciation import resolve_audio_path
from quicklingo.learning.tts.synth import resolve_sentence_audio
from quicklingo.learning.tts.text import prepare_text_for_tts
from quicklingo.workers.tts_prefetch_worker import TtsPrefetchWorker, TtsTermPrefetchWorker

_service: TtsPrefetchService | None = None


class TtsPrefetchService(QObject):
    term_ready = Signal(int)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._sentence_queue: list[str] = []
        self._term_queue: list[tuple[int, str]] = []
        self._seen_sentences: set[str] = set()
        self._seen_terms: set[tuple[int, str]] = set()
        self._sentence_worker: TtsPrefetchWorker | None = None
        self._term_worker: TtsTermPrefetchWorker | None = None

    def prefetch_texts(self, texts: Iterable[str], *, priority: bool = False) -> None:
        if not is_enabled("learning.tts_enabled"):
            return
        new_items: list[str] = []
        for raw in texts:
            cleaned = prepare_text_for_tts(raw)
            if not cleaned or cleaned in self._seen_sentences:
                continue
            if resolve_sentence_audio(cleaned) is not None:
                self._seen_sentences.add(cleaned)
                continue
            self._seen_sentences.add(cleaned)
            new_items.append(cleaned)
        if not new_items:
            return
        if priority:
            self._sentence_queue = new_items + self._sentence_queue
        else:
            self._sentence_queue.extend(new_items)
        if priority and self._sentence_worker is not None and self._sentence_worker.isRunning():
            self._sentence_worker.requestInterruption()
        self._start_sentence_worker()

    def prefetch_card_term(self, card_id: int, *, direction: str, priority: bool = False) -> None:
        if not is_enabled("learning.tts_enabled"):
            return
        key = (card_id, direction)
        if key in self._seen_terms:
            return
        card = learning.get_card(card_id)
        if card is not None and resolve_audio_path(card) is not None:
            self._seen_terms.add(key)
            return
        self._seen_terms.add(key)
        if priority:
            self._term_queue.insert(0, key)
        else:
            self._term_queue.append(key)
        if priority and self._term_worker is not None and self._term_worker.isRunning():
            self._term_worker.requestInterruption()
        self._start_term_worker()

    def _start_sentence_worker(self) -> None:
        if self._sentence_worker is not None and self._sentence_worker.isRunning():
            return
        if not self._sentence_queue:
            return
        batch = list(self._sentence_queue)
        self._sentence_queue.clear()
        self._sentence_worker = TtsPrefetchWorker(batch, parent=self)
        self._sentence_worker.finished.connect(self._on_sentence_worker_finished)
        self._sentence_worker.start()

    def _on_sentence_worker_finished(self) -> None:
        self._sentence_worker = None
        self._start_sentence_worker()

    def _start_term_worker(self) -> None:
        if self._term_worker is not None and self._term_worker.isRunning():
            return
        if not self._term_queue:
            return
        card_id, direction = self._term_queue.pop(0)
        self._term_worker = TtsTermPrefetchWorker(card_id, direction=direction, parent=self)
        self._term_worker.finished_card.connect(self._on_term_worker_card_ready)
        self._term_worker.finished.connect(self._on_term_worker_finished)
        self._term_worker.start()

    def _on_term_worker_card_ready(self, card_id: int) -> None:
        self.term_ready.emit(card_id)

    def _on_term_worker_finished(self) -> None:
        self._term_worker = None
        self._start_term_worker()


def tts_prefetch_service() -> TtsPrefetchService:
    global _service
    if _service is None:
        _service = TtsPrefetchService()
    return _service
