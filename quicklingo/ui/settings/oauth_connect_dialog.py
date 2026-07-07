from __future__ import annotations

from PySide6.QtCore import QEventLoop, QThread, Signal, Qt
from PySide6.QtWidgets import QMessageBox, QProgressDialog, QWidget

from quicklingo import settings
from quicklingo.i18n import tr
from quicklingo.sync.oauth.flow import connect_provider
from quicklingo.ui.qt_utils import suspend_always_on_top_for_oauth


class _OAuthConnectWorker(QThread):
    finished_ok = Signal(object)
    finished_error = Signal(str)

    def __init__(self, provider: str) -> None:
        super().__init__()
        self._provider = provider

    def run(self) -> None:
        try:
            tokens = connect_provider(self._provider)
        except Exception as exc:
            self.finished_error.emit(str(exc))
            return
        self.finished_ok.emit(tokens)


def run_oauth_connect(parent: QWidget, provider: str) -> bool:
    host_window = parent.window() if parent is not None else None

    dialog = QProgressDialog(
        tr("settings.sync.oauth_waiting"),
        tr("common.cancel"),
        0,
        0,
        None,
    )
    dialog.setWindowTitle(tr("settings.sync.oauth_title"))
    dialog.setMinimumDuration(0)
    dialog.setValue(0)
    dialog.setAutoClose(False)
    dialog.setAutoReset(False)
    dialog.setWindowModality(Qt.WindowModality.NonModal)
    dialog.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, False)

    worker = _OAuthConnectWorker(provider)
    result = {"ok": False}
    error_message: list[str | None] = [None]
    loop = QEventLoop()

    def on_ok(tokens) -> None:
        settings.save_sync_oauth_tokens(provider, tokens)
        result["ok"] = True
        dialog.close()
        loop.quit()

    def on_error(message: str) -> None:
        error_message[0] = message
        dialog.close()
        loop.quit()

    def on_cancel() -> None:
        worker.requestInterruption()
        dialog.close()
        loop.quit()

    worker.finished_ok.connect(on_ok)
    worker.finished_error.connect(on_error)
    dialog.canceled.connect(on_cancel)

    worker.start()
    with suspend_always_on_top_for_oauth(parent):
        dialog.show()
        dialog.lower()
        loop.exec()

    worker.wait(5000)

    if error_message[0]:
        QMessageBox.warning(
            host_window or parent,
            tr("settings.sync.oauth_error_title"),
            error_message[0],
        )

    return bool(result["ok"])
