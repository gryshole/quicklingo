import sys

from PySide6.QtWidgets import QApplication

from quicklingo.app_icon import configure_windows_app_id, load_app_icon
from quicklingo.db import history
from quicklingo.features import feature_changed, is_enabled
from quicklingo.i18n import init_language, language_changed
from quicklingo.input.hotkeys import HotkeyManager
from quicklingo.ui.main_window import MainWindow
from quicklingo.ui.tray import TrayManager


class QuickLingoApp:
    def __init__(self, qt_app: QApplication) -> None:
        self._app = qt_app
        self._window = MainWindow()
        self._hotkeys = HotkeyManager()
        self._tray: TrayManager | None = None
        icon = load_app_icon()
        if icon is not None:
            self._window.setWindowIcon(icon)

        language_changed().connect(self._window.retranslate_ui)
        feature_changed().changed.connect(self._on_features_changed)

        self._hotkeys.translate_selection.connect(self._window.translate_selection)
        self._hotkeys.translate_clipboard.connect(self._window.translate_clipboard)
        self._hotkeys.toggle_window.connect(self._toggle_window)
        self._hotkeys.double_ctrl_c.connect(self._window.translate_double_ctrl_c)

        self._apply_features()
        self._window.show()

    def _toggle_window(self) -> None:
        if self._tray is not None:
            self._tray.toggle_window()
        elif self._window.isVisible():
            self._window.hide()
        else:
            self._window.show()
            self._window.raise_()
            self._window.activateWindow()

    def _on_features_changed(self) -> None:
        from quicklingo import settings

        if is_enabled("privacy.encrypted_keys"):
            settings.migrate_api_keys_to_encrypted()
        self._apply_features()
        self._window.retranslate_ui()

    def _apply_features(self) -> None:
        from quicklingo.platform import autostart

        if autostart.autostart_supported():
            autostart.set_enabled(is_enabled("ui.autostart"))
        self._window.apply_features()
        if is_enabled("ui.system_tray"):
            icon = load_app_icon()
            if icon is not None and self._tray is None:
                self._tray = TrayManager(self._app, self._window, icon)
                self._window._tray_manager = self._tray
            if self._tray is not None:
                self._tray.show()
                self._tray.retranslate_ui()
        elif self._tray is not None:
            self._tray.hide()
        self._hotkeys.start()


def run() -> int:
    configure_windows_app_id()
    history.init_db()
    init_language()

    app = QApplication(sys.argv)
    app.setApplicationName("QuickLingo")
    icon = load_app_icon()
    if icon is not None:
        app.setWindowIcon(icon)

    QuickLingoApp(app)
    return app.exec()
