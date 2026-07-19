from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QMessageBox, QProgressDialog

from quicklingo import app as ql_app
from quicklingo.i18n import tr
from quicklingo.ui.qt_utils import confirm, warn
from quicklingo.update.checker import UpdateInfo, current_version, default_download_path, is_newer
from quicklingo.update.install import launch_update, updater_available
from quicklingo.workers.update_worker import UpdateCheckWorker, UpdateDownloadWorker

if TYPE_CHECKING:
    from quicklingo.ui.main_window import MainWindow


class UpdateController:
    """In-app update check and download flow."""

    def __init__(self, window: MainWindow) -> None:
        self._window = window
        self._check_worker: UpdateCheckWorker | None = None
        self._download_worker: UpdateDownloadWorker | None = None
        self._progress: QProgressDialog | None = None
        self._pending_info: UpdateInfo | None = None

    def check_for_updates(self) -> None:
        if self._check_worker is not None and self._check_worker.isRunning():
            return
        self._check_worker = UpdateCheckWorker(self._window)
        self._check_worker.finished_ok.connect(self._on_check_ok)
        self._check_worker.finished_error.connect(self._on_check_error)
        self._check_worker.start()

    def _on_check_error(self, message: str) -> None:
        warn(self._window, tr("update.error").format(message=message))

    def _on_check_ok(self, info: UpdateInfo) -> None:
        current = current_version()
        if not is_newer(info.latest_version, current):
            QMessageBox.information(
                self._window,
                tr("main.menu_help_check_updates"),
                tr("update.up_to_date").format(version=current),
            )
            return
        self._pending_info = info
        message = tr("update.available").format(current=current, latest=info.latest_version)
        box = QMessageBox(self._window)
        box.setWindowTitle(tr("main.menu_help_check_updates"))
        box.setText(message)
        box.setIcon(QMessageBox.Icon.Information)
        install_btn = box.addButton(tr("update.install_now"), QMessageBox.ButtonRole.AcceptRole)
        browser_btn = box.addButton(tr("update.open_browser"), QMessageBox.ButtonRole.ActionRole)
        box.addButton(tr("common.cancel"), QMessageBox.ButtonRole.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        if clicked is browser_btn and info.release_url:
            QDesktopServices.openUrl(QUrl(info.release_url))
        elif clicked is install_btn:
            self._start_download(info)

    def _start_download(self, info: UpdateInfo) -> None:
        if sys.platform != "win32":
            warn(self._window, tr("update.windows_only"))
            return
        if not updater_available():
            warn(self._window, tr("update.updater_missing"))
            if info.release_url:
                QDesktopServices.openUrl(QUrl(info.release_url))
            return
        if not confirm(self._window, tr("update.confirm_quit")):
            return
        dest = default_download_path(info.latest_version)
        self._progress = QProgressDialog(
            tr("update.downloading"), tr("common.cancel"), 0, 100, self._window
        )
        self._progress.setWindowTitle(tr("main.menu_help_check_updates"))
        self._progress.setWindowModality(Qt.WindowModality.WindowModal)
        self._progress.setMinimumDuration(0)
        self._progress.canceled.connect(self._cancel_download)
        self._progress.show()
        self._download_worker = UpdateDownloadWorker(info, dest, self._window)
        self._download_worker.progress.connect(self._on_download_progress)
        self._download_worker.finished_ok.connect(self._on_download_ok)
        self._download_worker.finished_error.connect(self._on_download_error)
        self._download_worker.start()

    def _cancel_download(self) -> None:
        if self._download_worker is not None and self._download_worker.isRunning():
            self._download_worker.terminate()
            self._download_worker.wait(2000)

    def _on_download_progress(self, downloaded: int, total: object) -> None:
        if self._progress is None:
            return
        if total is None:
            self._progress.setRange(0, 0)
            return
        total_int = int(total)
        if total_int <= 0:
            return
        self._progress.setRange(0, total_int)
        self._progress.setValue(min(downloaded, total_int))

    def _on_download_error(self, message: str) -> None:
        if self._progress is not None:
            self._progress.close()
            self._progress = None
        warn(self._window, tr("update.error").format(message=message))

    def _on_download_ok(self, zip_path: str) -> None:
        if self._progress is not None:
            self._progress.close()
            self._progress = None
        app_instance = ql_app.get_app()
        if app_instance is None:
            warn(self._window, tr("update.error").format(message="app"))
            return
        try:
            app_instance.prepare_quit_for_update()
            launch_update(Path(zip_path), pid=os.getpid())
            # Updater waits for this PID, then installs and restarts the app.
            self._window.close()
            QApplication.quit()
        except Exception as exc:
            warn(self._window, tr("update.error").format(message=str(exc)))
