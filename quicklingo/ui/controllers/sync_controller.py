from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox, QProgressDialog

from quicklingo.i18n import tr, translate_message
from quicklingo.sync.models import SyncMergeStats, SyncResult
from quicklingo.workers.sync_worker import SyncWorker

if TYPE_CHECKING:
    from quicklingo.ui.main_window import MainWindow


class SyncController:
    """Background database sync with non-blocking progress UI."""

    def __init__(self, window: MainWindow) -> None:
        self._window = window
        self._worker: SyncWorker | None = None
        self._progress: QProgressDialog | None = None

    def is_busy(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def start_sync(self) -> None:
        if self.is_busy():
            return

        self._progress = QProgressDialog(
            tr("main.sync_in_progress"),
            None,
            0,
            0,
            self._window,
        )
        self._progress.setWindowTitle(tr("main.sync_progress_title"))
        self._progress.setWindowModality(Qt.WindowModality.NonModal)
        self._progress.setMinimumDuration(0)
        self._progress.setAutoClose(True)
        self._progress.setAutoReset(True)
        self._progress.show()

        sync_action = getattr(self._window, "_sync_action", None)
        if sync_action is not None:
            sync_action.setEnabled(False)

        self._worker = SyncWorker()
        self._worker.finished_result.connect(self._on_finished)
        self._worker.finished.connect(self._cleanup)
        self._worker.start()

    def _cleanup(self) -> None:
        if self._progress is not None:
            self._progress.close()
            self._progress = None

        sync_action = getattr(self._window, "_sync_action", None)
        if sync_action is not None:
            sync_action.setEnabled(True)

        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None

    def _on_finished(self, result: SyncResult) -> None:
        if result.ok:
            QMessageBox.information(
                self._window,
                tr("main.sync_success_title"),
                self._format_success_message(result),
            )
            return

        message = result.message
        if message == "Sync transport is not configured":
            message = tr("main.sync_not_configured")
        elif message == "Not connected":
            message = tr("main.sync_not_connected")
        QMessageBox.warning(
            self._window,
            tr("main.sync_error_title"),
            translate_message(message),
        )

    @staticmethod
    def _format_stats_line(key: str, stats: SyncMergeStats) -> str:
        return tr(
            key,
            translations=stats.translations_added,
            decks=stats.decks_added,
            cards=stats.cards_added,
            card_updates=stats.cards_updated,
            quiz=stats.quiz_added,
        )

    def _format_success_message(self, result: SyncResult) -> str:
        parts: list[str] = []
        if result.downloaded:
            parts.append(self._format_stats_line("main.sync_success_download", result.merge))
        else:
            parts.append(tr("main.sync_success_no_remote"))
        parts.append(self._format_stats_line("main.sync_success_upload", result.upload))
        return "\n\n".join(parts)
