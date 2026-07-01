from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from PySide6.QtWidgets import QComboBox, QWidget

from quicklingo.ui.help_dialog import show_help


def raise_window(widget: QWidget) -> None:
    widget.show()
    widget.raise_()
    widget.activateWindow()


def reload_combo(
    combo: QComboBox,
    items: Iterable[tuple[Any, str]],
    *,
    current_data: Any = None,
) -> None:
    if current_data is None and combo.count():
        current_data = combo.currentData()
    combo.blockSignals(True)
    combo.clear()
    for data, label in items:
        combo.addItem(label, data)
    if current_data is not None:
        index = combo.findData(current_data)
        if index >= 0:
            combo.setCurrentIndex(index)
    combo.blockSignals(False)


def open_help(topic: str, parent: QWidget | None = None) -> None:
    show_help(topic, parent)
