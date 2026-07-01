from __future__ import annotations

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from quicklingo.i18n import tr
from quicklingo.ui.qt_utils import raise_window


class TrayManager:
    def __init__(self, app, main_window, icon) -> None:
        self._app = app
        self._window = main_window
        self._tray = QSystemTrayIcon(icon, main_window)
        self._menu = QMenu()
        self._show_action = QAction("", main_window)
        self._show_action.triggered.connect(self._toggle_window)
        self._settings_action = QAction("", main_window)
        self._settings_action.triggered.connect(main_window._open_settings)
        self._quit_action = QAction("", main_window)
        self._quit_action.triggered.connect(self._quit)
        self._menu.addAction(self._show_action)
        self._menu.addAction(self._settings_action)
        self._menu.addSeparator()
        self._menu.addAction(self._quit_action)
        self._tray.setContextMenu(self._menu)
        self._tray.activated.connect(self._on_activated)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self._show_action.setText(tr("tray.show_hide"))
        self._settings_action.setText(tr("main.menu_settings"))
        self._quit_action.setText(tr("tray.quit"))
        self._tray.setToolTip("QuickLingo")

    def show(self) -> None:
        self._tray.show()

    def hide(self) -> None:
        self._tray.hide()

    def toggle_window(self) -> None:
        self._toggle_window()

    def _toggle_window(self) -> None:
        if self._window.isVisible():
            self._window.hide()
        else:
            raise_window(self._window)

    def _on_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._toggle_window()

    def _quit(self) -> None:
        self._window._force_quit = True
        self._app.quit()
