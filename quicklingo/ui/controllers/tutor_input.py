from __future__ import annotations

from quicklingo.ui.zoomable_text_edit import ZoomableInputEdit, ZoomableLineEdit


def append_character(field: ZoomableInputEdit, char: str) -> None:
    if isinstance(field, ZoomableLineEdit):
        field.setText(field.text() + char)
    else:
        field.setPlainText(field.toPlainText() + char)


def backspace(field: ZoomableInputEdit) -> None:
    if isinstance(field, ZoomableLineEdit):
        text = field.text()
        if text:
            field.setText(text[:-1])
    else:
        text = field.toPlainText()
        if text:
            field.setPlainText(text[:-1])
