from __future__ import annotations

import html

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from quicklingo import settings
from quicklingo.i18n import tr

_ONBOARDING_STYLE = """
LearningOnboardingDialog {
    background-color: #ffffff;
}
LearningOnboardingDialog QPushButton#btnPrimary {
    background-color: #3b82f6;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 8px 24px;
    font-size: 13px;
    font-weight: 600;
    min-width: 88px;
}
LearningOnboardingDialog QPushButton#btnPrimary:hover:enabled {
    background-color: #2563eb;
}
LearningOnboardingDialog QPushButton#btnPrimary:pressed:enabled {
    background-color: #1d4ed8;
}
LearningOnboardingDialog QPushButton#btnSecondary {
    background-color: #ffffff;
    color: #475569;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 8px 20px;
    font-size: 13px;
    font-weight: 500;
    min-width: 88px;
}
LearningOnboardingDialog QPushButton#btnSecondary:hover:enabled {
    background-color: #f8fafc;
    border-color: #94a3b8;
    color: #1e293b;
}
LearningOnboardingDialog QPushButton#btnSecondary:disabled {
    color: #64748b;
    border-color: #e2e8f0;
    background-color: #f8fafc;
}
LearningOnboardingDialog QCheckBox {
    color: #64748b;
    font-size: 12px;
    spacing: 8px;
    padding: 0;
    margin: 0;
}
"""


def _format_body(text: str) -> str:
    return (
        f'<p style="line-height: 1.5; color: #475569; margin: 0; font-size: 11pt;">'
        f"{html.escape(text)}"
        f"</p>"
    )


class LearningOnboardingDialog(QDialog):
    def __init__(self, parent=None, *, standalone: bool = False) -> None:
        super().__init__(parent)
        self._standalone = standalone
        self.setObjectName("LearningOnboardingDialog")
        self.setStyleSheet(_ONBOARDING_STYLE)
        self.setWindowTitle(tr("learning.onboarding.title"))
        self.setMinimumWidth(480)
        self.setMaximumWidth(520)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(0)

        self._stack = QStackedWidget()
        self._slide_titles: list[QLabel] = []
        self._slide_bodies: list[QLabel] = []
        for _index in range(3):
            page = QWidget()
            page_layout = QVBoxLayout(page)
            page_layout.setContentsMargins(0, 0, 0, 0)
            page_layout.setSpacing(12)
            title = QLabel()
            title.setWordWrap(True)
            title.setStyleSheet(
                "font-size: 18px; font-weight: 600; color: #1e293b; margin: 0; padding: 0;"
            )
            body = QLabel()
            body.setWordWrap(True)
            body.setTextFormat(Qt.TextFormat.RichText)
            body.setOpenExternalLinks(False)
            body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            page_layout.addWidget(title)
            page_layout.addWidget(body)
            self._slide_titles.append(title)
            self._slide_bodies.append(body)
            self._stack.addWidget(page)

        root.addWidget(self._stack)
        root.addStretch(1)

        footer = QHBoxLayout()
        footer.setSpacing(12)
        footer.setContentsMargins(0, 16, 0, 0)
        footer.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self._dont_show = QCheckBox()
        self._back_btn = QPushButton()
        self._back_btn.setObjectName("btnSecondary")
        self._next_btn = QPushButton()
        self._next_btn.setObjectName("btnPrimary")
        self._finish_btn = QPushButton()
        self._finish_btn.setObjectName("btnPrimary")
        self._finish_btn.hide()
        self._back_btn.clicked.connect(self._go_back)
        self._next_btn.clicked.connect(self._go_next)
        self._finish_btn.clicked.connect(self.accept)

        footer.addWidget(self._dont_show, alignment=Qt.AlignmentFlag.AlignVCenter)
        footer.addStretch(1)
        footer.addWidget(self._back_btn, alignment=Qt.AlignmentFlag.AlignVCenter)
        footer.addWidget(self._next_btn, alignment=Qt.AlignmentFlag.AlignVCenter)
        footer.addWidget(self._finish_btn, alignment=Qt.AlignmentFlag.AlignVCenter)
        root.addLayout(footer)

        self._index = 0
        self.retranslate_ui()
        self._update_nav()

    def _content_width(self) -> int:
        margins = self.layout().contentsMargins()
        return self.maximumWidth() - margins.left() - margins.right()

    def _slide_content_height(self, index: int) -> int:
        width = self._content_width()
        title = self._slide_titles[index]
        body = self._slide_bodies[index]
        title_h = title.heightForWidth(width)
        body_h = body.heightForWidth(width)
        if title_h < 0:
            title_h = title.sizeHint().height()
        if body_h < 0:
            body_h = body.sizeHint().height()
        return title_h + 12 + body_h

    def _apply_uniform_height(self) -> None:
        max_stack_h = max(self._slide_content_height(i) for i in range(self._stack.count()))
        self._stack.setMinimumHeight(max_stack_h)

        saved_back = self._back_btn.isVisible()
        saved_next = self._next_btn.isVisible()
        saved_finish = self._finish_btn.isVisible()
        self._back_btn.setVisible(True)
        self._next_btn.setVisible(True)
        self._finish_btn.setVisible(False)

        self.adjustSize()
        self.setFixedHeight(self.sizeHint().height())

        self._back_btn.setVisible(saved_back)
        self._next_btn.setVisible(saved_next)
        self._finish_btn.setVisible(saved_finish)

    def retranslate_ui(self) -> None:
        self.setWindowTitle(tr("learning.onboarding.title"))
        self._dont_show.setText(tr("learning.onboarding.dont_show"))
        self._back_btn.setText(tr("learning.onboarding.back"))
        self._next_btn.setText(tr("learning.onboarding.next"))
        self._finish_btn.setText(tr("learning.onboarding.finish"))
        slides = [
            (tr("learning.onboarding.step1_title"), self._step1_body()),
            (tr("learning.onboarding.step2_title"), tr("learning.onboarding.step2_body")),
            (tr("learning.onboarding.step3_title"), tr("learning.onboarding.step3_body")),
        ]
        for index, (title, body) in enumerate(slides):
            self._slide_titles[index].setText(title)
            self._slide_bodies[index].setText(_format_body(body))
        self._apply_uniform_height()

    def _step1_body(self) -> str:
        if self._standalone:
            return tr("learning.onboarding.step1_body_standalone")
        return tr("learning.onboarding.step1_body")

    def _go_back(self) -> None:
        if self._index > 0:
            self._index -= 1
            self._stack.setCurrentIndex(self._index)
            self._update_nav()

    def _go_next(self) -> None:
        if self._index < self._stack.count() - 1:
            self._index += 1
            self._stack.setCurrentIndex(self._index)
            self._update_nav()

    def _update_nav(self) -> None:
        show_back = self._index > 0
        self._back_btn.setVisible(show_back)
        self._back_btn.setEnabled(show_back)
        last = self._index >= self._stack.count() - 1
        self._next_btn.setVisible(not last)
        self._finish_btn.setVisible(last)

    def accept(self) -> None:
        if self._dont_show.isChecked():
            settings.set_learning_show_onboarding(False)
        super().accept()

    @staticmethod
    def show_guide(parent, *, standalone: bool = False) -> None:
        """Open the onboarding guide regardless of the don't-show-again setting."""
        dialog = LearningOnboardingDialog(parent, standalone=standalone)
        dialog.exec()

    @staticmethod
    def maybe_show(parent, *, standalone: bool = False) -> None:
        if not settings.get_learning_show_onboarding():
            return
        dialog = LearningOnboardingDialog(parent, standalone=standalone)
        dialog.exec()
