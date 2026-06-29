from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal

from quicklingo.update.checker import UpdateInfo, download_release, fetch_latest


class UpdateCheckWorker(QThread):
    finished_ok = Signal(object)
    finished_error = Signal(str)

    def run(self) -> None:
        try:
            info = fetch_latest()
        except Exception as exc:
            self.finished_error.emit(str(exc))
            return
        self.finished_ok.emit(info)


class UpdateDownloadWorker(QThread):
    progress = Signal(int, object)
    finished_ok = Signal(str)
    finished_error = Signal(str)

    def __init__(self, info: UpdateInfo, dest: Path, parent=None) -> None:
        super().__init__(parent)
        self._info = info
        self._dest = dest

    def run(self) -> None:
        try:
            path = download_release(
                self._info,
                self._dest,
                progress_cb=lambda done, total: self.progress.emit(done, total),
            )
        except Exception as exc:
            self.finished_error.emit(str(exc))
            return
        self.finished_ok.emit(str(path))
