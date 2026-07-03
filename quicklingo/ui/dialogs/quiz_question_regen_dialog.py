from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from quicklingo.db.learning import QuizQuestionRow
from quicklingo.i18n import tr
from quicklingo.learning.quiz.models import QuizQuestionType
from quicklingo.providers.registry import get_model_by_index, get_model_entries
from quicklingo.ui.qt_utils import configure_single_line_combo, reload_combo
from quicklingo.workers.ai_quiz_regen_worker import AiQuizRegenWorker

_DIALOG_STYLE = """
QuizQuestionRegenDialog {
    background-color: #ffffff;
}
QFrame#infoCard {
    background-color: #f3f4f6;
    border: none;
    border-radius: 8px;
}
QLabel#infoFieldLabel {
    color: #64748b;
    font-weight: 600;
    font-size: 13px;
    min-width: 64px;
}
QLabel#infoValueLabel {
    color: #1e293b;
    font-size: 13px;
}
QLabel#fieldCaption {
    color: #64748b;
    font-weight: 600;
    font-size: 12px;
}
QPlainTextEdit#contextField {
    border: 1px solid #d1d5db;
    border-radius: 6px;
    padding: 8px;
    background-color: #ffffff;
    color: #1e293b;
    font-size: 13px;
}
QPlainTextEdit#contextField:focus {
    border-color: #3b82f6;
}
QComboBox#modelCombo {
    min-height: 32px;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    padding: 4px 10px;
    background-color: #ffffff;
    color: #1e293b;
    font-size: 13px;
}
QComboBox#modelCombo:hover {
    border-color: #94a3b8;
}
QComboBox#modelCombo:focus {
    border-color: #3b82f6;
}
QComboBox#modelCombo::drop-down {
    border: none;
    width: 24px;
}
QPushButton#btnPrimary {
    background-color: #3b82f6;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 8px 18px;
    font-size: 13px;
    font-weight: 600;
    min-height: 34px;
}
QPushButton#btnPrimary:hover:enabled {
    background-color: #2563eb;
}
QPushButton#btnPrimary:pressed:enabled {
    background-color: #1d4ed8;
}
QPushButton#btnPrimary:disabled {
    background-color: #94a3b8;
    color: #e2e8f0;
}
QPushButton#btnSecondary {
    background-color: #ffffff;
    color: #1e293b;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    padding: 8px 18px;
    font-size: 13px;
    min-height: 34px;
}
QPushButton#btnSecondary:hover:enabled {
    background-color: #f8fafc;
    border-color: #94a3b8;
}
QPushButton#btnSecondary:pressed:enabled {
    background-color: #f1f5f9;
}
QLabel#progressLabel {
    color: #64748b;
    font-size: 12px;
}
"""


def _question_type_label(qtype: str) -> str:
    mapping = {
        "fill_blank": tr("learning.quiz_type_fill_blank"),
        "definition_match": tr("learning.quiz_type_definition"),
        "translation_recall": tr("learning.quiz_type_translation"),
    }
    return mapping.get(qtype, qtype)


def _info_row(field: str, value: str) -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(12)
    name = QLabel(f"{field}:")
    name.setObjectName("infoFieldLabel")
    text = QLabel(value)
    text.setObjectName("infoValueLabel")
    text.setWordWrap(True)
    text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    layout.addWidget(name, alignment=Qt.AlignmentFlag.AlignTop)
    layout.addWidget(text, stretch=1, alignment=Qt.AlignmentFlag.AlignTop)
    return row


class QuizQuestionRegenDialog(QDialog):
    def __init__(self, row: QuizQuestionRow, *, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("QuizQuestionRegenDialog")
        self.setStyleSheet(_DIALOG_STYLE)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._row = row
        self._worker: AiQuizRegenWorker | None = None
        self._result: QuizQuestionRow | None = None
        self.setMinimumWidth(540)
        self.setModal(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(16)

        self._info_card = QFrame()
        self._info_card.setObjectName("infoCard")
        info_layout = QVBoxLayout(self._info_card)
        info_layout.setContentsMargins(12, 12, 12, 12)
        info_layout.setSpacing(12)
        info_layout.addWidget(
            _info_row(tr("learning.quiz_questions_col_word"), f"{row.card_front} — {row.card_back}")
        )
        info_layout.addWidget(
            _info_row(tr("learning.quiz_questions_col_type"), _question_type_label(row.question_type))
        )
        info_layout.addWidget(
            _info_row(tr("learning.quiz_question_edit_prompt"), row.prompt_text.strip())
        )
        root.addWidget(self._info_card)

        self._context_caption = QLabel(tr("learning.quiz_question_regen_context_label"))
        self._context_caption.setObjectName("fieldCaption")
        root.addWidget(self._context_caption)

        self._context = QPlainTextEdit()
        self._context.setObjectName("contextField")
        self._context.setPlaceholderText(tr("learning.quiz_question_regen_hint"))
        self._context.setMinimumHeight(88)
        self._context.setMaximumHeight(120)
        root.addWidget(self._context)

        self._model_caption = QLabel(tr("learning.model"))
        self._model_caption.setObjectName("fieldCaption")
        root.addWidget(self._model_caption)

        self._model_combo = QComboBox()
        self._model_combo.setObjectName("modelCombo")
        configure_single_line_combo(self._model_combo)
        reload_combo(
            self._model_combo,
            [(entry.model_id, entry.display_name) for entry in get_model_entries()],
        )
        if self._model_combo.count() and self._model_combo.currentIndex() < 0:
            self._model_combo.setCurrentIndex(0)
        root.addWidget(self._model_combo)

        self._progress_label = QLabel()
        self._progress_label.setObjectName("progressLabel")
        self._progress_label.setWordWrap(True)
        self._progress_label.setVisible(False)
        root.addWidget(self._progress_label)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()
        self._cancel_btn = QPushButton(tr("main.cancel"))
        self._cancel_btn.setObjectName("btnSecondary")
        self._cancel_btn.clicked.connect(self._on_cancel)
        self._regen_btn = QPushButton(tr("learning.quiz_question_regen_action"))
        self._regen_btn.setObjectName("btnPrimary")
        self._regen_btn.clicked.connect(self._start_regen)
        btn_row.addWidget(self._cancel_btn)
        btn_row.addWidget(self._regen_btn)
        root.addLayout(btn_row)

        self.setWindowTitle(tr("learning.quiz_question_regen_title"))

    @property
    def result_row(self) -> QuizQuestionRow | None:
        return self._result

    def _set_busy(self, busy: bool) -> None:
        self._context.setEnabled(not busy)
        self._model_combo.setEnabled(not busy)
        self._regen_btn.setEnabled(not busy)
        self._cancel_btn.setText(
            tr("main.cancel") if not busy else tr("learning.quiz_question_regen_stop")
        )
        self._progress_label.setVisible(busy)

    def _start_regen(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
            return

        model_entry = get_model_by_index(self._model_combo.currentIndex())
        if model_entry is None:
            return

        self._set_busy(True)
        self._progress_label.setText(tr("learning.quiz_generating"))

        self._worker = AiQuizRegenWorker(
            self._row.card_id,
            QuizQuestionType(self._row.question_type),
            model_entry=model_entry,
            user_context=self._context.toPlainText(),
            parent=self,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_progress(self, message: str) -> None:
        self._progress_label.setText(message)

    def _on_error(self, message: str) -> None:
        self._set_busy(False)
        self._progress_label.setText(message)

    def _on_finished(self, record) -> None:
        from quicklingo.db import learning

        self._set_busy(False)
        self._worker = None
        refreshed = learning.get_quiz_question_by_id(record.id)
        self._result = refreshed
        self.accept()

    def _on_cancel(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
            return
        self.reject()

    def closeEvent(self, event) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(3000)
        super().closeEvent(event)
