from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from quicklingo.sync.models import SyncResult
from quicklingo.sync.service import sync_now


class SyncWorker(QThread):
    finished_result = Signal(object)

    def run(self) -> None:
        self.finished_result.emit(sync_now())
