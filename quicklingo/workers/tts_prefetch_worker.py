from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from quicklingo.learning.pronunciation import ensure_card_pronunciation
from quicklingo.learning.tts.prefetch import unique_texts
from quicklingo.learning.tts.synth import resolve_sentence_audio, synthesize_sentence


class TtsPrefetchWorker(QThread):
    progress = Signal(int, int)
    finished_count = Signal(int)

    def __init__(self, texts: list[str], parent=None) -> None:
        super().__init__(parent)
        self._texts = unique_texts(texts)

    def run(self) -> None:
        total = len(self._texts)
        if total == 0:
            self.finished_count.emit(0)
            return
        synthesized = 0
        for index, text in enumerate(self._texts, start=1):
            if self.isInterruptionRequested():
                break
            if resolve_sentence_audio(text) is None and synthesize_sentence(text) is not None:
                synthesized += 1
            self.progress.emit(index, total)
        self.finished_count.emit(synthesized)


class TtsTermPrefetchWorker(QThread):
    finished_card = Signal(int)

    def __init__(self, card_id: int, *, direction: str, parent=None) -> None:
        super().__init__(parent)
        self._card_id = card_id
        self._direction = direction

    def run(self) -> None:
        if self.isInterruptionRequested():
            return
        ensure_card_pronunciation(self._card_id, direction=self._direction)
        if not self.isInterruptionRequested():
            self.finished_card.emit(self._card_id)


class TtsSynthWorker(QThread):
    finished_path = Signal(str)

    def __init__(self, text: str, parent=None) -> None:
        super().__init__(parent)
        self._text = text.strip()

    def run(self) -> None:
        if not self._text:
            self.finished_path.emit("")
            return
        path = resolve_sentence_audio(self._text)
        if path is None:
            path = synthesize_sentence(self._text)
        self.finished_path.emit(str(path) if path else "")
