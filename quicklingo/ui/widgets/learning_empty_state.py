from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget


class LearningEmptyStateWidget(QWidget):
    action_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 32, 24, 32)
        layout.setSpacing(12)
        self._title = QLabel()
        self._title.setStyleSheet("font-size: 14pt; font-weight: 600; color: #0f172a;")
        self._title.setWordWrap(True)
        self._title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._body = QLabel()
        self._body.setStyleSheet("font-size: 11pt; color: #64748b;")
        self._body.setWordWrap(True)
        self._body.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._action = QPushButton()
        self._action.setStyleSheet(
            "background: #3b82f6; color: white; border: none; border-radius: 8px;"
            "padding: 10px 20px; font-weight: 600;"
        )
        self._action.clicked.connect(self.action_requested.emit)
        self._action.setVisible(False)
        layout.addStretch(1)
        layout.addWidget(self._title)
        layout.addWidget(self._body)
        layout.addWidget(self._action, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(2)
        self.hide()

    def set_content(self, title: str, body: str, *, action: str = "") -> None:
        self._title.setText(title)
        self._body.setText(body)
        self._action.setText(action)
        self._action.setVisible(bool(action))
        self.show()

    def hide_state(self) -> None:
        self.hide()
