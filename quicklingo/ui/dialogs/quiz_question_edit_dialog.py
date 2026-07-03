from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
)

from quicklingo.db import learning
from quicklingo.db.learning import QuizQuestionRow
from quicklingo.i18n import tr
from quicklingo.learning.card_display import parse_context
from quicklingo.learning.quiz.models import QuizQuestionType
from quicklingo.learning.quiz.quiz_validator import filter_valid_choices


class QuizQuestionEditDialog(QDialog):
    def __init__(self, row: QuizQuestionRow, *, direction: str = "ua-en", parent=None) -> None:
        super().__init__(parent)
        self._row = row
        self._direction = direction
        self.setMinimumWidth(520)

        layout = QFormLayout(self)
        self._word_label = QLabel(f"{row.card_front} — {row.card_back}")
        self._type_label = QLabel(_question_type_label(row.question_type))
        layout.addRow(tr("learning.quiz_questions_col_word"), self._word_label)
        layout.addRow(tr("learning.quiz_questions_col_type"), self._type_label)

        self._prompt = QPlainTextEdit(row.prompt_text)
        self._prompt.setMaximumHeight(100)
        layout.addRow(tr("learning.quiz_question_edit_prompt"), self._prompt)

        self._example = QPlainTextEdit(row.example_sentence)
        self._example.setMaximumHeight(70)
        self._example_label = QLabel(tr("learning.quiz_question_edit_example"))
        layout.addRow(self._example_label, self._example)
        is_fill_blank = row.question_type == QuizQuestionType.FILL_BLANK.value
        self._example_label.setVisible(is_fill_blank)
        self._example.setVisible(is_fill_blank)

        self._choices = QPlainTextEdit("\n".join(row.choices_pool))
        self._choices.setMaximumHeight(120)
        self._choices.setPlaceholderText(tr("learning.quiz_question_edit_choices_hint"))
        layout.addRow(tr("learning.quiz_question_edit_choices"), self._choices)

        self._correct = QLineEdit(row.correct_english)
        layout.addRow(tr("learning.quiz_question_edit_correct"), self._correct)

        self._status = QComboBox()
        self._status.addItem(tr("learning.quiz_questions_status_active"), "active")
        self._status.addItem(tr("learning.quiz_questions_status_failed"), "failed")
        status_index = self._status.findData(row.status)
        if status_index >= 0:
            self._status.setCurrentIndex(status_index)
        layout.addRow(tr("learning.quiz_questions_col_status"), self._status)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        self.setWindowTitle(tr("learning.quiz_question_edit_title"))
        self._buttons = buttons

    def _save(self) -> None:
        qtype = QuizQuestionType(self._row.question_type)
        raw_choices = [
            line.strip() for line in self._choices.toPlainText().splitlines() if line.strip()
        ]
        card = learning.get_card(self._row.card_id)
        deck = learning.get_deck(self._row.deck_id) if card else None
        direction = deck.direction if deck else self._direction
        examples = parse_context(card.context, direction=direction) if card else []
        definition = (card.back or "").strip() if card else self._row.card_back
        example_sentence = self._example.toPlainText().strip()
        correct = self._correct.text().strip()
        if not correct:
            QMessageBox.warning(self, tr("common.error"), tr("learning.quiz_question_edit_no_correct"))
            return

        validated = filter_valid_choices(
            question_type=qtype,
            correct=correct,
            candidates=raw_choices,
            examples=examples,
            definition=definition,
            example_sentence=example_sentence if qtype == QuizQuestionType.FILL_BLANK else "",
        )
        if len(validated) < 4:
            reply = QMessageBox.warning(
                self,
                tr("learning.quiz_question_edit_title"),
                tr("learning.quiz_question_edit_few_choices", count=len(validated)),
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if reply != QMessageBox.StandardButton.Save:
                return

        learning.upsert_quiz_question(
            card_id=self._row.card_id,
            question_type=self._row.question_type,
            prompt_text=self._prompt.toPlainText().strip(),
            example_sentence=example_sentence if qtype == QuizQuestionType.FILL_BLANK else "",
            choices_pool=validated or raw_choices,
            correct_english=correct,
            status=self._status.currentData(),
            model_id=self._row.model_id,
            prompt_version=self._row.prompt_version,
        )
        self.accept()


def _question_type_label(qtype: str) -> str:
    mapping = {
        "fill_blank": tr("learning.quiz_type_fill_blank"),
        "definition_match": tr("learning.quiz_type_definition"),
        "translation_recall": tr("learning.quiz_type_translation"),
    }
    return mapping.get(qtype, qtype)
