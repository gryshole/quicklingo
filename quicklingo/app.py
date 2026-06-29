import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from quicklingo.app_icon import configure_windows_app_id, load_app_icon
from quicklingo.db import history
from quicklingo.features import feature_changed, is_enabled, save_features
from quicklingo.i18n import init_language, language_changed
from quicklingo.input.hotkeys import HotkeyManager
from quicklingo.input.tutor_capture import TutorCaptureManager
from quicklingo.input.tutor_capture_log import log_info, log_file_path
from quicklingo.ui.main_window import MainWindow
from quicklingo.ui.tray import TrayManager

_app: "QuickLingoApp | None" = None


def get_app() -> "QuickLingoApp | None":
    return _app


class QuickLingoApp:
    def __init__(self, qt_app: QApplication) -> None:
        self._app = qt_app
        self._window = MainWindow()
        self._hotkeys = HotkeyManager()
        self._tutor_capture = TutorCaptureManager(
            should_capture=self._tutor_should_capture,
            should_capture_reason=self._tutor_should_capture_reason,
        )
        self._tray: TrayManager | None = None
        icon = load_app_icon()
        if icon is not None:
            self._window.setWindowIcon(icon)

        language_changed().connect(self._window.retranslate_ui)
        feature_changed().changed.connect(self._on_features_changed)

        self._hotkeys.translate_selection.connect(self._window.translate_selection)
        self._hotkeys.translate_clipboard.connect(self._window.translate_clipboard)
        self._hotkeys.toggle_window.connect(self._toggle_window)
        self._hotkeys.tutor_capture_toggle.connect(self._toggle_tutor_capture)
        self._hotkeys.double_ctrl_c.connect(self._window.translate_double_ctrl_c)

        self._tutor_capture.character_typed.connect(self._window.on_tutor_character)
        self._tutor_capture.backspace_pressed.connect(self._window.on_tutor_backspace)
        self._tutor_capture.enter_pressed.connect(self._window.on_tutor_enter)

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

    def _toggle_tutor_capture(self) -> None:
        new_state = not is_enabled("input.tutor_capture")
        log_info(f"hotkey toggle global input -> enabled={new_state}")
        save_features({"input.tutor_capture": {"enabled": new_state}})

    def _tutor_should_capture(self) -> bool:
        if not is_enabled("input.tutor_capture"):
            return False
        if QApplication.activeModalWidget() is not None:
            return False
        if self._window.is_translation_busy():
            return False
        return sys.platform == "win32"

    def _tutor_should_capture_reason(self) -> str:
        if not is_enabled("input.tutor_capture"):
            return "feature_disabled"
        modal = QApplication.activeModalWidget()
        if modal is not None:
            return f"modal_open:{type(modal).__name__}"
        if self._window.is_translation_busy():
            return "translation_busy"
        if sys.platform != "win32":
            return "not_windows"
        return "ok"

    def _on_features_changed(self, changed_keys: list | None = None) -> None:
        from quicklingo import settings

        if is_enabled("privacy.encrypted_keys"):
            settings.migrate_api_keys_to_encrypted()

        keys = changed_keys or []
        if keys == ["input.tutor_capture"]:
            self._window.sync_tutor_capture_ui()
            QTimer.singleShot(0, self._apply_tutor_capture)
            return

        self._apply_features()
        self._window.retranslate_ui()

    def _apply_tutor_capture(self) -> None:
        want_hook = is_enabled("input.tutor_capture") and sys.platform == "win32"
        running = self._tutor_capture.is_running()
        if want_hook and not running:
            log_info(f"apply_tutor_capture: start (log: {log_file_path()})")
            self._tutor_capture.start()
        elif not want_hook and running:
            reason = self._tutor_should_capture_reason()
            log_info(f"apply_tutor_capture: stop ({reason})")
            self._tutor_capture.stop()

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
        self._apply_tutor_capture()

    def prepare_quit_for_update(self) -> None:
        self._hotkeys.stop()
        self._tutor_capture.stop()
        if self._tray is not None:
            self._tray.hide()
        self._window._force_quit = True


def run() -> int:
    global _app
    configure_windows_app_id()
    history.init_db()
    init_language()

    app = QApplication(sys.argv)
    app.setApplicationName("QuickLingo")
    icon = load_app_icon()
    if icon is not None:
        app.setWindowIcon(icon)

    _app = QuickLingoApp(app)
    return app.exec()
