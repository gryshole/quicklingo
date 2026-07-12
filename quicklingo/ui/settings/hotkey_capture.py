"""Click-to-record hotkey row (Correcta-style): capture field + clear/disable."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFocusEvent, QKeyEvent, QMouseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QWidget,
)

from quicklingo.i18n import tr

_MODIFIER_KEYS = {
    Qt.Key.Key_Control,
    Qt.Key.Key_Shift,
    Qt.Key.Key_Alt,
    Qt.Key.Key_Meta,
    Qt.Key.Key_AltGr,
}

_SPECIAL_KEYS: dict[Qt.Key, str] = {
    Qt.Key.Key_Space: "<space>",
    Qt.Key.Key_Tab: "<tab>",
    Qt.Key.Key_Return: "<enter>",
    Qt.Key.Key_Enter: "<enter>",
    Qt.Key.Key_Backspace: "<backspace>",
    Qt.Key.Key_Delete: "<delete>",
    Qt.Key.Key_Insert: "<insert>",
    Qt.Key.Key_Home: "<home>",
    Qt.Key.Key_End: "<end>",
    Qt.Key.Key_PageUp: "<page_up>",
    Qt.Key.Key_PageDown: "<page_down>",
    Qt.Key.Key_Left: "<left>",
    Qt.Key.Key_Right: "<right>",
    Qt.Key.Key_Up: "<up>",
    Qt.Key.Key_Down: "<down>",
    Qt.Key.Key_Escape: "<esc>",
    Qt.Key.Key_CapsLock: "<caps_lock>",
    Qt.Key.Key_Print: "<print_screen>",
    Qt.Key.Key_ScrollLock: "<scroll_lock>",
    Qt.Key.Key_Pause: "<pause>",
    Qt.Key.Key_Plus: "+",
    Qt.Key.Key_Minus: "-",
    Qt.Key.Key_Comma: ",",
    Qt.Key.Key_Period: ".",
    Qt.Key.Key_Slash: "/",
    Qt.Key.Key_Semicolon: ";",
    Qt.Key.Key_BracketLeft: "[",
    Qt.Key.Key_BracketRight: "]",
    Qt.Key.Key_Backslash: "\\",
    Qt.Key.Key_QuoteLeft: "`",
    Qt.Key.Key_Apostrophe: "'",
}

_DISPLAY_TOKENS: dict[str, str] = {
    "<ctrl>": "Ctrl",
    "<alt>": "Alt",
    "<shift>": "Shift",
    "<cmd>": "Win",
    "<space>": "Space",
    "<tab>": "Tab",
    "<enter>": "Enter",
    "<backspace>": "Backspace",
    "<delete>": "Delete",
    "<insert>": "Insert",
    "<home>": "Home",
    "<end>": "End",
    "<page_up>": "Page Up",
    "<page_down>": "Page Down",
    "<left>": "Left",
    "<right>": "Right",
    "<up>": "Up",
    "<down>": "Down",
    "<esc>": "Esc",
}


def qt_key_event_to_pynput(event: QKeyEvent) -> str | None:
    """Convert a Qt key event to a pynput GlobalHotKeys combo string."""
    key = event.key()
    if key in _MODIFIER_KEYS:
        return None

    mods = event.modifiers()
    parts: list[str] = []
    if mods & Qt.KeyboardModifier.ControlModifier:
        parts.append("<ctrl>")
    if mods & Qt.KeyboardModifier.ShiftModifier:
        parts.append("<shift>")
    if mods & Qt.KeyboardModifier.AltModifier:
        parts.append("<alt>")
    if mods & Qt.KeyboardModifier.MetaModifier:
        parts.append("<cmd>")

    if Qt.Key.Key_A <= key <= Qt.Key.Key_Z:
        parts.append(chr(ord("a") + (key - Qt.Key.Key_A)))
    elif Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
        parts.append(chr(ord("0") + (key - Qt.Key.Key_0)))
    elif Qt.Key.Key_F1 <= key <= Qt.Key.Key_F35:
        parts.append(f"<f{key - Qt.Key.Key_F1 + 1}>")
    elif key in _SPECIAL_KEYS:
        parts.append(_SPECIAL_KEYS[key])
    else:
        text = event.text()
        if text and text.isprintable() and len(text) == 1 and not text.isspace():
            parts.append(text.lower())
        else:
            return None

    if len(parts) == 1 and parts[0].startswith("<") is False and len(parts[0]) == 1:
        # Bare letter without modifiers is too easy to trigger accidentally.
        return None
    return "+".join(parts)


def pynput_to_display(combo: str) -> str:
    if not combo.strip():
        return ""
    tokens = []
    for part in combo.split("+"):
        token = part.strip().lower()
        if token in _DISPLAY_TOKENS:
            tokens.append(_DISPLAY_TOKENS[token])
        elif token.startswith("<f") and token.endswith(">"):
            tokens.append(token[1:-1].upper())
        elif len(token) == 1:
            tokens.append(token.upper())
        else:
            tokens.append(part.strip())
    return " + ".join(tokens)


class _CaptureEdit(QLineEdit):
    """Read-only field that captures key combos while recording."""

    combo_captured = Signal(str)
    recording_cancelled = Signal()
    clicked = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._recording = False

    def set_recording(self, recording: bool) -> None:
        self._recording = recording
        if recording:
            self.setFocus(Qt.FocusReason.OtherFocusReason)
            self.selectAll()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            self.setFocus(Qt.FocusReason.MouseFocusReason)
        super().mousePressEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if not self._recording:
            super().keyPressEvent(event)
            return
        if event.key() == Qt.Key.Key_Escape:
            self.recording_cancelled.emit()
            event.accept()
            return
        combo = qt_key_event_to_pynput(event)
        if combo is None:
            event.accept()
            return
        self.combo_captured.emit(combo)
        event.accept()

    def focusOutEvent(self, event: QFocusEvent) -> None:
        if self._recording:
            self.recording_cancelled.emit()
        super().focusOutEvent(event)


class HotkeyCaptureRow(QWidget):
    """Label + capture field + clear button for one hotkey feature."""

    changed = Signal()

    def __init__(
        self,
        *,
        feature_key: str,
        field: str,
        title_key: str,
        uses_enabled_flag: bool,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.feature_key = feature_key
        self.field = field
        self.uses_enabled_flag = uses_enabled_flag
        self._title_key = title_key
        self._combo = ""
        self._enabled = False
        self._recording = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._label = QLabel()
        self._label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self._label.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred
        )

        self._edit = _CaptureEdit()
        self._edit.clicked.connect(self.begin_recording)
        self._edit.combo_captured.connect(self._on_combo_captured)
        self._edit.recording_cancelled.connect(self._cancel_recording)

        self._clear_btn = QPushButton()
        self._clear_btn.setObjectName("btnSecondary")
        self._clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clear_btn.clicked.connect(self.clear_binding)

        layout.addWidget(self._label, stretch=0)
        layout.addWidget(self._edit, stretch=1)
        layout.addWidget(self._clear_btn, stretch=0)

        self.retranslate_ui()
        self._refresh_display()

    def label_preferred_width(self) -> int:
        return max(self._label.sizeHint().width(), self._label.minimumSizeHint().width())

    def set_label_width(self, width: int) -> None:
        self._label.setFixedWidth(max(0, width))

    def retranslate_ui(self) -> None:
        self._label.setText(tr(self._title_key))
        self._clear_btn.setText(tr("settings.features.hotkey_clear"))
        help_key = f"settings.features.help.{self.feature_key.replace('.', '_')}"
        tip = tr(help_key)
        if tip and tip != help_key:
            self._label.setToolTip(tip)
            self._edit.setToolTip(tip)
        self._refresh_display()

    def set_state(self, *, combo: str, enabled: bool) -> None:
        self._combo = (combo or "").strip()
        if self.uses_enabled_flag:
            self._enabled = bool(enabled) and bool(self._combo)
        else:
            self._enabled = bool(self._combo)
        self._recording = False
        self._edit.set_recording(False)
        self._refresh_display()

    def binding_combo(self) -> str:
        """Value to persist in the combo/hotkey field."""
        if self.uses_enabled_flag:
            return self._combo
        return self._combo if self._enabled else ""

    def binding_enabled(self) -> bool:
        if self.uses_enabled_flag:
            return self._enabled and bool(self._combo)
        return bool(self._combo)

    def begin_recording(self) -> None:
        if self._recording:
            return
        self._recording = True
        self._edit.set_recording(True)
        self._edit.setText(tr("settings.features.hotkey_press"))
        self._clear_btn.setEnabled(False)

    def clear_binding(self) -> None:
        self._recording = False
        self._edit.set_recording(False)
        if self.uses_enabled_flag:
            self._enabled = False
        else:
            self._combo = ""
            self._enabled = False
        self._refresh_display()
        self.changed.emit()

    def _cancel_recording(self) -> None:
        if not self._recording:
            return
        self._recording = False
        self._edit.set_recording(False)
        self._refresh_display()

    def _on_combo_captured(self, combo: str) -> None:
        self._recording = False
        self._edit.set_recording(False)
        self._combo = combo
        self._enabled = True
        self._refresh_display()
        self.changed.emit()

    def _refresh_display(self) -> None:
        if self._recording:
            return
        active = self.binding_enabled()
        if not active:
            self._edit.setText(tr("settings.features.hotkey_disabled"))
            self._clear_btn.setEnabled(False)
            return
        self._edit.setText(pynput_to_display(self._combo) or self._combo)
        self._clear_btn.setEnabled(True)
