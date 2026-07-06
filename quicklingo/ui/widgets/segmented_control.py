"""Segmented toggle control (Quiz-style direction picker)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QPushButton, QWidget


class SegmentedControl(QWidget):
    selection_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("segmentedControl")
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._segments: list[tuple[QPushButton, str]] = []
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self._layout = layout
        self._group.idClicked.connect(self._on_button_clicked)

    def clear_segments(self) -> None:
        for button, _segment_id in self._segments:
            self._group.removeButton(button)
            self._layout.removeWidget(button)
            button.deleteLater()
        self._segments.clear()

    def add_segment(self, segment_id: str, label: str, *, checked: bool = False) -> None:
        button = QPushButton(label)
        button.setMinimumWidth(48)
        button.setCheckable(True)
        button.setChecked(checked)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button_id = len(self._segments)
        self._group.addButton(button, button_id)
        self._segments.append((button, segment_id))
        self._layout.addWidget(button, stretch=1)

    def current_id(self) -> str:
        for button, segment_id in self._segments:
            if button.isChecked():
                return segment_id
        return self._segments[0][1] if self._segments else ""

    def set_current_id(self, segment_id: str) -> None:
        for button, sid in self._segments:
            button.setChecked(sid == segment_id)

    def set_enabled_all(self, enabled: bool) -> None:
        for button, _segment_id in self._segments:
            button.setEnabled(enabled)

    def _on_button_clicked(self, _button_id: int) -> None:
        self.selection_changed.emit(self.current_id())
