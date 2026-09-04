from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from quicklingo.features import is_enabled
from quicklingo.i18n import tr
from quicklingo.learning.card_display import highlight_term_in_context, highlight_term_styled
from quicklingo.learning.quiz.quiz_feedback_content import (
    QuizFeedbackContent,
    feedback_content_has_body,
)
from quicklingo.learning.tts.audio_service import AudioService


class QuizFeedbackEnrichmentWidget(QWidget):
    def __init__(self, audio: AudioService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._audio = audio
        self._example_rows: list[QWidget] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(10)

        self._ukrainian_label = QLabel()
        self._ukrainian_label.setWordWrap(True)
        self._ukrainian_label.setStyleSheet(
            "color:#0f172a;font-size:15px;font-weight:600;line-height:1.4;"
        )
        layout.addWidget(self._ukrainian_label)

        self._definition_frame = QFrame()
        self._definition_frame.setStyleSheet(
            "QFrame { background:#ffffff; border:1px solid #e2e8f0; border-radius:10px; }"
        )
        definition_layout = QVBoxLayout(self._definition_frame)
        definition_layout.setContentsMargins(12, 12, 12, 12)
        self._definition_label = QLabel()
        self._definition_label.setWordWrap(True)
        self._definition_label.setTextFormat(Qt.TextFormat.RichText)
        self._definition_label.setStyleSheet("color:#475569;font-size:14px;line-height:1.4;")
        definition_layout.addWidget(self._definition_label)
        layout.addWidget(self._definition_frame)

        self._examples_host = QWidget()
        examples_outer = QVBoxLayout(self._examples_host)
        examples_outer.setContentsMargins(0, 0, 0, 0)
        examples_outer.setSpacing(8)
        self._examples_title = QLabel()
        self._examples_title.setStyleSheet(
            "color:#64748b;font-size:13px;font-weight:700;"
        )
        examples_outer.addWidget(self._examples_title)
        self._examples_layout = QVBoxLayout()
        self._examples_layout.setContentsMargins(0, 0, 0, 0)
        self._examples_layout.setSpacing(8)
        examples_outer.addLayout(self._examples_layout)
        layout.addWidget(self._examples_host)

        self.setVisible(False)

    def retranslate_ui(self) -> None:
        self._examples_title.setText(tr("learning.quiz_feedback_examples"))

    def set_content(self, content: QuizFeedbackContent | None) -> None:
        self._clear_example_rows()
        if content is None or not feedback_content_has_body(content):
            self._ukrainian_label.clear()
            self._definition_label.clear()
            self._definition_frame.setVisible(False)
            self._examples_host.setVisible(False)
            self.setVisible(False)
            return

        if content.ukrainian:
            self._ukrainian_label.setText(
                tr("learning.quiz_feedback_ukrainian", word=content.ukrainian)
            )
            self._ukrainian_label.setVisible(True)
        else:
            self._ukrainian_label.clear()
            self._ukrainian_label.setVisible(False)

        if content.definition:
            label = tr("learning.review_definition")
            body = highlight_term_styled(content.definition, content.highlight_term)
            self._definition_label.setText(
                f'<span style="font-weight:700;">{label}</span> '
                f'<span style="font-style:italic;">{body}</span>'
            )
            self._definition_frame.setVisible(True)
        else:
            self._definition_label.clear()
            self._definition_frame.setVisible(False)

        tts_enabled = is_enabled("learning.tts_enabled")
        if content.examples:
            self._examples_title.setText(tr("learning.quiz_feedback_examples"))
            for sentence in content.examples:
                row = QWidget()
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(0, 0, 0, 0)
                row_layout.setSpacing(8)

                text_label = QLabel()
                text_label.setWordWrap(True)
                text_label.setTextFormat(Qt.TextFormat.RichText)
                text_label.setText(highlight_term_in_context(sentence, content.highlight_term))
                text_label.setStyleSheet("color:#334155;font-size:14px;line-height:1.4;")
                text_label.setSizePolicy(
                    QSizePolicy.Policy.Expanding,
                    QSizePolicy.Policy.Preferred,
                )
                row_layout.addWidget(text_label, 1)

                if tts_enabled:
                    audio_btn = self._make_speaker_button()
                    audio_btn.setToolTip(tr("learning.tts_play_example"))
                    audio_btn.clicked.connect(
                        lambda _checked=False, s=sentence: self._audio.speak_sentence(s)
                    )
                    row_layout.addWidget(audio_btn)

                self._examples_layout.addWidget(row)
                self._example_rows.append(row)
            self._examples_host.setVisible(True)
        else:
            self._examples_host.setVisible(False)

        self.setVisible(True)

    def _clear_example_rows(self) -> None:
        while self._examples_layout.count():
            item = self._examples_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._example_rows.clear()

    @staticmethod
    def _make_speaker_button() -> QPushButton:
        btn = QPushButton("🔊")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFlat(True)
        btn.setFixedSize(28, 28)
        btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        return btn
