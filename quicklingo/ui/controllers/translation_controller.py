from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from PySide6.QtGui import QGuiApplication

from quicklingo.db import history
from quicklingo.features import get_feature, is_enabled
from quicklingo.input.hotkeys import paste_text
from quicklingo.providers.registry import get_model_by_index
from quicklingo.workers.translate_worker import TranslateWorker

if TYPE_CHECKING:
    from quicklingo.ui.main_window import MainWindow


@dataclass
class QueuedRequest:
    text: str
    direction: str
    profile_id: str
    model_index: int


class TranslationController:
    """Manages translation workers, cache lookup, and request queue."""

    def __init__(self, window: MainWindow) -> None:
        self._window = window
        self._worker: TranslateWorker | None = None
        self._worker_gen = 0
        self._stream_buffer = ""
        self._pending_source = ""
        self._pending_direction = "ua-en"
        self._pending_profile_id = "detailed"
        self._pending_model_id = ""
        self._pending_from_cache = False
        self._last_error_message = ""
        self._request_queue: list[QueuedRequest] = []
        self._replace_after_translate = False

    @property
    def last_error_message(self) -> str:
        return self._last_error_message

    @property
    def pending_source(self) -> str:
        return self._pending_source

    def is_busy(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def set_replace_after_translate(self, enabled: bool) -> None:
        self._replace_after_translate = enabled

    def submit(self) -> None:
        text = self._window._input_field.input_text()
        if not text:
            return
        if self.is_busy():
            if is_enabled("translation.request_queue"):
                self._request_queue.append(
                    QueuedRequest(
                        text,
                        self._window._current_direction(),
                        self._window._current_profile_id(),
                        self._window._model_combo.currentIndex(),
                    )
                )
                self._window._input_field.clear_input()
                self._window._set_status(
                    "main.status_queued", error=False, count=len(self._request_queue)
                )
            return
        self.start(text)

    def start(self, text: str) -> None:
        self._pending_source = text
        self._pending_direction = self._window._current_direction()
        self._pending_profile_id = self._window._current_profile_id()
        model_entry = get_model_by_index(self._window._model_combo.currentIndex())
        self._pending_model_id = model_entry.model_id
        self._pending_from_cache = False
        self._last_error_message = ""
        self._stream_buffer = ""

        cached = None
        if is_enabled("translation.response_cache"):
            ttl = int(get_feature("translation.response_cache").get("ttl_days", 30))
            cached = history.find_cached(
                self._pending_direction,
                text,
                self._pending_profile_id,
                ttl_days=ttl,
            )

        self._window._input_field.clear_input()

        if cached is not None:
            self._pending_from_cache = True
            self._on_finished(cached)
            return

        self._window._set_busy(True)
        self._window._set_status("main.status_translating", error=False)
        self._start_worker(text, model_entry)

    def _start_worker(self, text: str, model_entry) -> None:
        self._disconnect_worker()
        self._worker_gen += 1
        gen = self._worker_gen
        worker = TranslateWorker(
            text,
            self._pending_direction,
            model_entry,
            profile_id=self._pending_profile_id,
            parent=self._window,
        )
        self._worker = worker
        worker.finished.connect(lambda result, g=gen: self._on_worker_finished(result, g))
        worker.chunk.connect(lambda piece, g=gen: self._on_worker_chunk(piece, g))
        worker.error.connect(lambda message, g=gen: self._on_worker_error(message, g))
        worker.cancelled.connect(lambda g=gen: self._on_worker_cancelled(g))
        worker.finished.connect(worker.deleteLater)
        worker.error.connect(worker.deleteLater)
        worker.cancelled.connect(worker.deleteLater)
        worker.start()

    def _disconnect_worker(self) -> None:
        if self._worker is None:
            return
        for signal in (self._worker.finished, self._worker.chunk, self._worker.error, self._worker.cancelled):
            try:
                signal.disconnect()
            except RuntimeError:
                pass

    def cancel(self) -> None:
        if self.is_busy() and self._worker is not None:
            self._worker.cancel()

    def retry(self) -> None:
        if not self._pending_source:
            return
        self._window._input_field.set_input_text(self._pending_source)
        self.submit()

    def _on_worker_chunk(self, piece: str, gen: int) -> None:
        if gen != self._worker_gen:
            return
        self._stream_buffer += piece
        self._window._output_field.set_result_plain(self._stream_buffer)

    def _on_worker_finished(self, result: str, gen: int) -> None:
        if gen != self._worker_gen:
            return
        self._on_finished(result)

    def _on_finished(self, result: str) -> None:
        from_cache = self._pending_from_cache
        self._window._show_result(result, self._pending_direction, self._pending_profile_id)
        if is_enabled("history.auto_save") and not from_cache:
            tag = self._window._current_tag()
            history.save_translation(
                self._pending_direction,
                self._pending_source,
                result,
                self._pending_model_id,
                profile_id=self._pending_profile_id,
                tags=[tag] if tag else None,
            )
            if tag and is_enabled("history.tags"):
                self._window._reload_tag_combo()
        if is_enabled("ui.auto_copy_result"):
            QGuiApplication.clipboard().setText(result)
        if self._replace_after_translate:
            paste_text(result)
            self._replace_after_translate = False
        self._worker = None
        self._window._set_busy(False)
        self._window._set_status(
            "main.status_cached" if from_cache else "main.status_ready",
            error=False,
        )
        self._process_queue()
        self._window._input_field.setFocus()

    def _on_worker_error(self, message: str, gen: int) -> None:
        if gen != self._worker_gen:
            return
        self._last_error_message = message
        self._worker = None
        self._window._set_busy(False)
        self._window._retry_btn.setVisible(True)
        self._window._set_status("main.status_error", error=True, message=message)
        self._process_queue()
        self._window._input_field.setFocus()

    def _on_worker_cancelled(self, gen: int) -> None:
        if gen != self._worker_gen:
            return
        self._worker = None
        self._window._set_busy(False)
        self._window._set_status("main.status_cancelled", error=False)
        self._process_queue()
        self._window._input_field.setFocus()

    def _process_queue(self) -> None:
        if not is_enabled("translation.request_queue") or not self._request_queue:
            return
        if self.is_busy():
            return
        next_req = self._request_queue.pop(0)
        if 0 <= next_req.model_index < self._window._model_combo.count():
            self._window._model_combo.setCurrentIndex(next_req.model_index)
        for radio, direction_id in self._window._direction_radios:
            radio.setChecked(direction_id == next_req.direction)
        self._window._refresh_profile_combo()
        profile_index = self._window._profile_combo.findData(next_req.profile_id)
        if profile_index >= 0:
            self._window._profile_combo.setCurrentIndex(profile_index)
        self.start(next_req.text)
