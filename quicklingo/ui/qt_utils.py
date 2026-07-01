from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QSizePolicy, QWidget
from shiboken6 import isValid

from quicklingo.ui.help_dialog import show_help


class _ComboLineEditPopupFilter(QObject):
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() != QEvent.Type.MouseButtonPress:
            return False
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        combo = self.parent()
        if not isinstance(combo, QComboBox) or not isValid(combo):
            return False
        try:
            line_edit = combo.lineEdit()
        except RuntimeError:
            return False
        if watched is not line_edit:
            return False
        combo.showPopup()
        return True


def raise_window(widget: QWidget) -> None:
    widget.show()
    widget.raise_()
    widget.activateWindow()


def configure_single_line_combo(combo: QComboBox) -> None:
    """Keep the selected model name on one line (no wrap inside the control)."""
    combo.setEditable(True)
    line_edit = combo.lineEdit()
    if line_edit is not None:
        line_edit.setReadOnly(True)
        line_edit.setFrame(False)
        line_edit.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        line_edit.installEventFilter(_ComboLineEditPopupFilter(combo))
    combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    combo.setSizeAdjustPolicy(
        QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
    )
    combo.view().setTextElideMode(Qt.TextElideMode.ElideRight)

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
