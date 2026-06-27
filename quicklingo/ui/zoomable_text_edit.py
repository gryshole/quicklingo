from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent, QKeySequence, QShortcut, QWheelEvent
from PySide6.QtWidgets import QLineEdit, QTextEdit

from quicklingo.ui.format_output import RESULT_WRAP_STYLE


def _base_font_point_size(widget) -> int:
    size = widget.font().pointSize()
    if size <= 0:
        size = round(widget.font().pointSizeF())
    return size if size > 0 else 10


def _handle_zoom_key(event: QKeyEvent, zoom_in, zoom_out, reset) -> bool:
    if not event.modifiers() & Qt.KeyboardModifier.ControlModifier:
        return False
    key = event.key()
    if key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
        zoom_in()
        return True
    if key == Qt.Key.Key_Minus:
        zoom_out()
        return True
    if key == Qt.Key.Key_0:
        reset()
        return True
    return False


def _handle_zoom_wheel(event: QWheelEvent, zoom_in, zoom_out) -> bool:
    if not event.modifiers() & Qt.KeyboardModifier.ControlModifier:
        return False
    delta = event.angleDelta().y()
    if delta > 0:
        zoom_in()
        return True
    if delta < 0:
        zoom_out()
        return True
    return False


def _scaled_result_html(html: str, point_size: float) -> str:
    sized_style = f"{RESULT_WRAP_STYLE};font-size:{point_size:.1f}pt"
    return html.replace(f'style="{RESULT_WRAP_STYLE}"', f'style="{sized_style}"', 1)


def _install_zoom_shortcuts(host, zoom_in, zoom_out, reset) -> None:
    for seq in ("Ctrl+=", "Ctrl++"):
        shortcut = QShortcut(QKeySequence(seq), host)
        shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
        shortcut.activated.connect(zoom_in)

    shortcut = QShortcut(QKeySequence("Ctrl+-"), host)
    shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
    shortcut.activated.connect(zoom_out)

    shortcut = QShortcut(QKeySequence("Ctrl+0"), host)
    shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
    shortcut.activated.connect(reset)


class ZoomableLineEdit(QLineEdit):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._zoom_steps = 0
        self._base_point_size = _base_font_point_size(self)
        _install_zoom_shortcuts(self, self._zoom_in, self._zoom_out, self.reset_zoom)

    def reset_zoom(self) -> None:
        self._zoom_steps = 0
        self._apply_zoom()

    def zoom_steps(self) -> int:
        return self._zoom_steps

    def set_zoom_steps(self, steps: int) -> None:
        self._zoom_steps = steps
        self._apply_zoom()

    def _zoom_in(self) -> None:
        self._zoom_steps += 1
        self._apply_zoom()

    def _zoom_out(self) -> None:
        self._zoom_steps -= 1
        self._apply_zoom()

    def _apply_zoom(self) -> None:
        font = self.font()
        font.setPointSizeF(max(6.0, self._base_point_size + self._zoom_steps))
        self.setFont(font)
        self.updateGeometry()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if _handle_zoom_key(event, self._zoom_in, self._zoom_out, self.reset_zoom):
            return
        super().keyPressEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        if _handle_zoom_wheel(event, self._zoom_in, self._zoom_out):
            event.accept()
            return
        super().wheelEvent(event)


class ZoomableInputEdit(QTextEdit):
    submit_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._zoom_steps = 0
        self._base_point_size = _base_font_point_size(self)
        self.setAcceptRichText(False)
        self.setTabChangesFocus(True)
        self.setMaximumHeight(120)
        _install_zoom_shortcuts(self, self._zoom_in, self._zoom_out, self.reset_zoom)

    def reset_zoom(self) -> None:
        self._zoom_steps = 0
        self._apply_zoom()

    def zoom_steps(self) -> int:
        return self._zoom_steps

    def set_zoom_steps(self, steps: int) -> None:
        self._zoom_steps = steps
        self._apply_zoom()

    def input_text(self) -> str:
        return self.toPlainText().strip()

    def clear_input(self) -> None:
        self.clear()

    def _zoom_in(self) -> None:
        self._zoom_steps += 1
        self._apply_zoom()

    def _zoom_out(self) -> None:
        self._zoom_steps -= 1
        self._apply_zoom()

    def _apply_zoom(self) -> None:
        font = self.font()
        font.setPointSizeF(max(6.0, self._base_point_size + self._zoom_steps))
        self.setFont(font)
        self.updateGeometry()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if _handle_zoom_key(event, self._zoom_in, self._zoom_out, self.reset_zoom):
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & (
                Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.AltModifier
            ):
                super().keyPressEvent(event)
                return
            self.submit_requested.emit()
            return
        super().keyPressEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        if _handle_zoom_wheel(event, self._zoom_in, self._zoom_out):
            event.accept()
            return
        super().wheelEvent(event)


class ZoomableTextEdit(QTextEdit):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._zoom_steps = 0
        self._base_point_size = _base_font_point_size(self)
        self._result_html: str | None = None
        self._result_plain: str | None = None
        self._selectable = False
        self.setReadOnly(True)
        self._apply_interaction_flags()
        self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        _install_zoom_shortcuts(self, self._zoom_in, self._zoom_out, self.reset_zoom)

    def set_text_selectable(self, selectable: bool) -> None:
        self._selectable = selectable
        self._apply_interaction_flags()

    def _apply_interaction_flags(self) -> None:
        if self._selectable:
            self.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
                | Qt.TextInteractionFlag.TextSelectableByKeyboard
            )
        else:
            self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)

    def set_result_html(self, html: str) -> None:
        self._result_html = html
        self._result_plain = None
        self._apply_zoom()

    def set_result_plain(self, text: str) -> None:
        self._result_html = None
        self._result_plain = text
        self._apply_zoom()

    def reset_zoom(self) -> None:
        self._zoom_steps = 0
        self._apply_zoom()

    def zoom_steps(self) -> int:
        return self._zoom_steps

    def set_zoom_steps(self, steps: int) -> None:
        self._zoom_steps = steps
        self._apply_zoom()

    def _zoom_in(self) -> None:
        self._zoom_steps += 1
        self._apply_zoom()

    def _zoom_out(self) -> None:
        self._zoom_steps -= 1
        self._apply_zoom()

    def _apply_zoom(self) -> None:
        size = max(6.0, self._base_point_size + self._zoom_steps)
        font = self.font()
        font.setPointSizeF(size)
        self.setFont(font)
        if self._result_html is not None:
            self.setHtml(_scaled_result_html(self._result_html, size))
        elif self._result_plain is not None:
            self.setPlainText(self._result_plain)
        self.document().setDefaultFont(font)
        self.viewport().setCursor(Qt.CursorShape.ArrowCursor)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if _handle_zoom_key(event, self._zoom_in, self._zoom_out, self.reset_zoom):
            return
        super().keyPressEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        if _handle_zoom_wheel(event, self._zoom_in, self._zoom_out):
            event.accept()
            return
        super().wheelEvent(event)
