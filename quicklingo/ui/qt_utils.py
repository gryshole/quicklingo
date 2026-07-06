from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QSizePolicy, QWidget

from quicklingo.ui.app_theme import apply_combo_font
from quicklingo.ui.help_dialog import show_help


def raise_window(widget: QWidget) -> None:
    widget.show()
    widget.raise_()
    widget.activateWindow()


def configure_single_line_combo(combo: QComboBox) -> None:
    """Select-only combo: one-line label, elided popup items, full text in tooltip."""
    combo.setEditable(False)
    combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    combo.setSizeAdjustPolicy(
        QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
    )
    combo.view().setTextElideMode(Qt.TextElideMode.ElideRight)
    apply_combo_font(combo)

    def _sync_tooltip(_text: str = "") -> None:
        combo.setToolTip(combo.currentText())

    combo.currentIndexChanged.connect(lambda _index: _sync_tooltip())
    combo.currentTextChanged.connect(_sync_tooltip)
    _sync_tooltip()


def labeled_combo_row(label: QLabel, combo: QComboBox) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
    row.addWidget(label)
    row.addWidget(combo, stretch=1)
    return row


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
