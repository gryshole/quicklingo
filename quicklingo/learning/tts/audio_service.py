from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

from quicklingo.db.learning import LearningCard
from quicklingo.features import is_enabled
from quicklingo.learning.pronunciation import ensure_card_pronunciation, resolve_audio_path
from quicklingo.learning.tts.audio_providers import (
    CachedAudioProvider,
    EdgeTtsProvider,
    QtSpeechProvider,
)
from quicklingo.learning.tts.prefetch_service import tts_prefetch_service
from quicklingo.learning.tts.synth import resolve_sentence_audio
from quicklingo.learning.tts.text import prepare_text_for_tts
from quicklingo.workers.tts_prefetch_worker import TtsSynthWorker


class AudioService(QObject):
    synthesizing = Signal(bool)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._cached = CachedAudioProvider(self._player, self._audio_output)
        self._edge = EdgeTtsProvider(self._cached)
        self._qt_speech = QtSpeechProvider()
        self._synth_worker: TtsSynthWorker | None = None
        self._pending_text = ""

    def stop(self) -> None:
        if self._synth_worker is not None and self._synth_worker.isRunning():
            self._synth_worker.requestInterruption()
            self._synth_worker.wait(200)
        self._synth_worker = None
        self._pending_text = ""
        self._cached.stop()
        self._qt_speech.stop()
        self.synthesizing.emit(False)

    def is_speaking(self) -> bool:
        return self._cached.is_speaking() or self._qt_speech.is_speaking()

    def speak_english(self, text: str) -> bool:
        if not is_enabled("learning.tts_enabled"):
            return False
        cleaned = prepare_text_for_tts(text)
        if not cleaned:
            return False
        tts_prefetch_service().prefetch_texts([cleaned], priority=True)
        self.stop()
        if self._edge.speak(cleaned):
            return True
        return self._start_sentence_synth(cleaned)

    def speak_sentence(self, text: str) -> bool:
        return self.speak_english(text)

    def speak_card_term(self, card: LearningCard, *, direction: str) -> bool:
        if not is_enabled("learning.tts_enabled"):
            return False
        tts_prefetch_service().prefetch_card_term(card.id, direction=direction)
        self.stop()
        updated = ensure_card_pronunciation(card.id, direction=direction)
        target = updated or card
        if self._cached.play_card_audio(target):
            return True
        from quicklingo.learning.review_queue import english_side_text

        english = english_side_text(target, direction).strip()
        if not english:
            return False
        cached = resolve_audio_path(target)
        if cached is not None:
            return self._cached.play_file(cached)
        return self.speak_english(english)

    def _start_sentence_synth(self, text: str) -> bool:
        self._pending_text = text
        self._synth_worker = TtsSynthWorker(text, parent=self)
        self._synth_worker.finished_path.connect(self._on_sentence_synth_finished)
        self.synthesizing.emit(True)
        self._synth_worker.start()
        return True

    def _on_sentence_synth_finished(self, path_text: str) -> None:
        self.synthesizing.emit(False)
        self._synth_worker = None
        pending = self._pending_text
        self._pending_text = ""
        if path_text:
            path = Path(path_text)
            if path.is_file():
                self._cached.play_file(path)
                return
        if pending:
            self._qt_speech.speak(pending)
