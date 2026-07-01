from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QListWidget,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from quicklingo.i18n import tr


def build_list_editor_shell(parent: QWidget) -> tuple[QSplitter, QListWidget, QHBoxLayout]:
    """Shared list + action buttons layout for settings entity editors."""
    splitter = QSplitter(parent)
    left = QWidget(splitter)
    left_layout = QVBoxLayout(left)
    item_list = QListWidget(left)
    buttons = QHBoxLayout()
    for label_key in ("common.add", "common.duplicate", "common.delete"):
        buttons.addWidget(QPushButton(tr(label_key)))
    left_layout.addWidget(item_list)
    left_layout.addLayout(buttons)
    return splitter, item_list, buttons
