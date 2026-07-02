from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

from quicklingo.learning.pronunciation import resolve_audio_path
from quicklingo.learning.tts.synth import resolve_sentence_audio
from quicklingo.learning.tts.text import prepare_text_for_tts


class CachedAudioProvider:
    def __init__(self, player: QMediaPlayer, audio_output: QAudioOutput) -> None:
        self._player = player
        self._audio_output = audio_output
        self._player.setAudioOutput(self._audio_output)

    def play_file(self, path: Path) -> bool:
        if not path.is_file():
            return False
        self._player.setSource(QUrl.fromLocalFile(str(path)))
        self._player.play()
        return True

    def play_card_audio(self, card) -> bool:
        path = resolve_audio_path(card)
        if path is None:
            return False
        return self.play_file(path)

    def stop(self) -> None:
        self._player.stop()

    def is_speaking(self) -> bool:
        return self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState


class EdgeTtsProvider:
    def __init__(self, cached: CachedAudioProvider) -> None:
        self._cached = cached

    def speak(self, text: str, *, lang: str = "en-US") -> bool:
        path = resolve_sentence_audio(prepare_text_for_tts(text))
        if path is None:
            return False
        return self._cached.play_file(path)

    def stop(self) -> None:
        self._cached.stop()

    def is_speaking(self) -> bool:
        return self._cached.is_speaking()


class QtSpeechProvider:
    def __init__(self) -> None:
        self._speech = None
        try:
            from PySide6.QtTextToSpeech import QTextToSpeech

            self._speech = QTextToSpeech()
            for voice in self._speech.availableVoices():
                if voice.locale().name().startswith("en"):
                    self._speech.setVoice(voice)
                    break
        except Exception:
            self._speech = None

    def speak(self, text: str, *, lang: str = "en-US") -> bool:
        if self._speech is None:
            return False
        self._speech.say(text.strip())
        return True

    def stop(self) -> None:
        if self._speech is not None:
            self._speech.stop()

    def is_speaking(self) -> bool:
        if self._speech is None:
            return False
        try:
            from PySide6.QtTextToSpeech import QTextToSpeech

            return self._speech.state() == QTextToSpeech.State.Speaking
        except Exception:
            return False
