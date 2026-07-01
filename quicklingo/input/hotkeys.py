from __future__ import annotations

import sys
import time
from collections.abc import Callable

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from quicklingo.input.key_simulation import send_ctrl_c, send_ctrl_v


class HotkeyManager(QObject):
    translate_selection = Signal()
    translate_clipboard = Signal()
    toggle_window = Signal()
    tutor_capture_toggle = Signal()
    double_ctrl_c = Signal()

    _HOTKEY_BINDINGS: tuple[tuple[str, str, Callable[[], None]], ...] = (
        (
            "input.global_hotkey.translate_selection",
            "combo",
            lambda self: self.translate_selection.emit(),
        ),
        (
            "input.global_hotkey.translate_clipboard",
            "combo",
            lambda self: self.translate_clipboard.emit(),
        ),
        (
            "ui.system_tray",
            "hotkey",
            lambda self: self.toggle_window.emit(),
        ),
        (
            "input.tutor_capture",
            "hotkey",
            lambda self: self.tutor_capture_toggle.emit(),
        ),
    )

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._hotkeys = None
        self._listener = None
        self._ctrl_pressed = False
        self._last_ctrl_c = 0.0
        self._running = False

    def start(self) -> None:
        self.stop()
        try:
            from pynput import keyboard
        except ImportError:
            return

        from quicklingo.features import get_feature, is_enabled

        bindings: dict[str, callable] = {}
        defaults = {
            "input.global_hotkey.translate_selection": "<ctrl>+<shift>+t",
            "input.global_hotkey.translate_clipboard": "<ctrl>+<shift>+v",
            "ui.system_tray": "<ctrl>+<shift>+q",
            "input.tutor_capture": "",
        }

        for feature_key, field, handler in self._HOTKEY_BINDINGS:
            if feature_key == "input.tutor_capture":
                combo = str(get_feature(feature_key).get(field, defaults[feature_key])).strip()
                if not combo:
                    continue
            elif feature_key == "ui.system_tray":
                if not is_enabled(feature_key):
                    continue
                combo = str(get_feature(feature_key).get(field, defaults[feature_key]))
            elif not is_enabled(feature_key):
                continue
            else:
                combo = str(get_feature(feature_key).get(field, defaults[feature_key]))
            bindings[combo] = lambda handler=handler: handler(self)

        if bindings:
            self._hotkeys = keyboard.GlobalHotKeys(bindings)
            self._hotkeys.start()
            self._running = True

        if is_enabled("input.double_ctrl_c"):
            self._listener = keyboard.Listener(
                on_press=self._on_key_press,
                on_release=self._on_key_release,
            )
            self._listener.start()
            self._running = True

    def stop(self) -> None:
        if self._hotkeys is not None:
            self._hotkeys.stop()
            self._hotkeys = None
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
        self._ctrl_pressed = False
        self._running = False

    def is_running(self) -> bool:
        return self._running

    def _on_key_press(self, key) -> None:
        from quicklingo.features import is_enabled

        if not is_enabled("input.double_ctrl_c"):
            return
        try:
            from pynput.keyboard import Key, KeyCode
        except ImportError:
            return
        if key in (Key.ctrl_l, Key.ctrl_r):
            self._ctrl_pressed = True
            return
        if not self._ctrl_pressed:
            return
        char = getattr(key, "char", None)
        if char not in ("c", "C") and key != KeyCode.from_char("c"):
            return
        now = time.monotonic()
        if now - self._last_ctrl_c < 0.45:
            self.double_ctrl_c.emit()
            self._last_ctrl_c = 0.0
        else:
            self._last_ctrl_c = now

    def _on_key_release(self, key) -> None:
        try:
            from pynput.keyboard import Key
        except ImportError:
            return
        if key in (Key.ctrl_l, Key.ctrl_r):
            self._ctrl_pressed = False


def copy_selection_to_clipboard() -> str:
    clipboard = QGuiApplication.clipboard()
    previous = clipboard.text()
    send_ctrl_c()
    QApplication.processEvents()
    time.sleep(0.08)
    text = clipboard.text()
    if text and text != previous:
        return text.strip()
    return text.strip() if text else ""


def paste_text(text: str) -> None:
    if not text or sys.platform != "win32":
        return
    clipboard = QGuiApplication.clipboard()
    previous = clipboard.text()
    clipboard.setText(text)
    QApplication.processEvents()
    time.sleep(0.03)
    send_ctrl_v()
    time.sleep(0.05)
    clipboard.setText(previous)
