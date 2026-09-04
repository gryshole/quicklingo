from __future__ import annotations

from PySide6.QtCore import Qt, QSize
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
from quicklingo.learning.card_display import highlight_term_styled
from quicklingo.learning.quiz.quiz_feedback_content import (
    QuizFeedbackContent,
    feedback_content_has_body,
)
from quicklingo.learning.tts.audio_service import AudioService
from quicklingo.ui.widgets.quiz_ui import (
    EXAMPLE_SPEAKER_GHOST_STYLE,
    quiz_term_highlight_style,
    speaker_icon,
)

_WORD_ANALYSIS_GAP = 12
_SECTION_DIVIDER_STYLE = "background:#e2e8f0; max-height:1px; min-height:1px; border:none;"
_CALLOUT_WRONG_STYLE = (
    "QFrame#quizFeedbackCallout {"
    "background:#fff1f2; border:none; border-radius:8px;"
    "}"
    "QLabel { color:#881337; font-size:14px; line-height:1.45; background:transparent; }"
)
_CALLOUT_NEUTRAL_STYLE = (
    "QFrame#quizFeedbackCallout {"
    "background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px;"
    "}"
    "QLabel { color:#334155; font-size:13px; line-height:1.45; background:transparent; }"
)
_EXAMPLES_TITLE_STYLE = (
    "QLabel#quizExamplesTitle {"
    "color:#94a3b8; font-size:11px; font-weight:600;"
    "letter-spacing:0.06em; padding:4px 0 2px 2px; background:transparent;"
    "}"
)


def _transparent_widget(parent: QWidget | None = None) -> QWidget:
    widget = QWidget(parent)
    widget.setAutoFillBackground(False)
    widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    widget.setStyleSheet("background: transparent;")
    return widget


class QuizFeedbackEnrichmentWidget(QWidget):
    def __init__(self, audio: AudioService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._audio = audio
        self.setAutoFillBackground(False)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._word_analysis = QWidget()
        self._word_analysis.setObjectName("quizWordAnalysis")
        self._word_analysis.setAutoFillBackground(False)
        self._word_analysis.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._word_analysis.setStyleSheet("background: transparent;")
        word_analysis_layout = QVBoxLayout(self._word_analysis)
        word_analysis_layout.setContentsMargins(0, 0, 0, 0)
        word_analysis_layout.setSpacing(_WORD_ANALYSIS_GAP)

        self._callout = QFrame()
        self._callout.setObjectName("quizFeedbackCallout")
        callout_layout = QVBoxLayout(self._callout)
        callout_layout.setContentsMargins(12, 10, 12, 10)
        callout_layout.setSpacing(4)
        self._callout_label = QLabel()
        self._callout_label.setWordWrap(True)
        self._callout_label.setTextFormat(Qt.TextFormat.RichText)
        callout_layout.addWidget(self._callout_label)
        word_analysis_layout.addWidget(self._callout)
        self._callout.setVisible(False)

        self._definition_label = QLabel()
        self._definition_label.setWordWrap(True)
        self._definition_label.setTextFormat(Qt.TextFormat.RichText)
        self._definition_label.setStyleSheet(
            "color:#64748b;font-size:13px;line-height:1.35;margin:0;padding:0;background:transparent;"
        )
        word_analysis_layout.addWidget(self._definition_label)

        self._examples_host = _transparent_widget()
        examples_outer = QVBoxLayout(self._examples_host)
        examples_outer.setContentsMargins(0, 0, 0, 0)
        examples_outer.setSpacing(0)
        self._examples_title = QLabel()
        self._examples_title.setObjectName("quizExamplesTitle")
        self._examples_title.setStyleSheet(_EXAMPLES_TITLE_STYLE)
        examples_outer.addWidget(self._examples_title)
        self._examples_layout = QVBoxLayout()
        self._examples_layout.setContentsMargins(0, 0, 0, 0)
        self._examples_layout.setSpacing(0)
        examples_outer.addLayout(self._examples_layout)
        word_analysis_layout.addWidget(self._examples_host)

        layout.addWidget(self._word_analysis)
        self.setVisible(False)

    def retranslate_ui(self) -> None:
        self._examples_title.setText(tr("learning.quiz_feedback_examples").upper())

    def set_feedback(
        self,
        content: QuizFeedbackContent | None,
        *,
        wrong_hint_html: str = "",
        is_wrong: bool = False,
    ) -> None:
        self._clear_example_rows()
        self._callout_label.clear()
        self._definition_label.clear()
        self._callout.setVisible(False)
        self._definition_label.setVisible(False)
        self._examples_host.setVisible(False)

        if content is None:
            self.setVisible(False)
            return

        has_body = bool(wrong_hint_html) or feedback_content_has_body(content)
        if not has_body:
            self.setVisible(False)
            return

        callout_parts: list[str] = []
        if wrong_hint_html:
            callout_parts.append(wrong_hint_html)
        elif content.ukrainian:
            callout_parts.append(
                f'<span style="color:#334155;">{tr("learning.quiz_feedback_ukrainian", word=content.ukrainian)}</span>'
            )

        if wrong_hint_html and content.ukrainian and not self._ukrainian_in_hint(
            content.ukrainian, wrong_hint_html
        ):
            callout_parts.append(
                f'<span style="color:#334155;">{tr("learning.quiz_feedback_ukrainian", word=content.ukrainian)}</span>'
            )

        if callout_parts:
            self._callout_label.setText("<br>".join(callout_parts))
            self._callout.setStyleSheet(
                _CALLOUT_WRONG_STYLE if is_wrong else _CALLOUT_NEUTRAL_STYLE
            )
            self._callout.setVisible(True)

        if content.definition:
            label = tr("learning.review_definition")
            body = highlight_term_styled(
                content.definition,
                content.highlight_term,
                style="font-style:italic;color:#64748b;",
            )
            self._definition_label.setText(
                f'<span style="font-weight:600;color:#374151;">{label}</span> '
                f'<span style="font-style:italic;color:#64748b;">{body}</span>'
            )
            self._definition_label.setVisible(True)

        highlight_style = quiz_term_highlight_style()
        tts_enabled = is_enabled("learning.tts_enabled")
        if content.examples:
            self._examples_title.setText(tr("learning.quiz_feedback_examples").upper())
            for index, sentence in enumerate(content.examples):
                if index > 0:
                    divider = QFrame()
                    divider.setFixedHeight(1)
                    divider.setStyleSheet(_SECTION_DIVIDER_STYLE)
                    self._examples_layout.addWidget(divider)

                row = _transparent_widget()
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(0, 10, 0, 10)
                row_layout.setSpacing(10)
                row_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

                text_label = QLabel()
                text_label.setWordWrap(True)
                text_label.setTextFormat(Qt.TextFormat.RichText)
                text_label.setAlignment(
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
                )
                text_label.setText(
                    highlight_term_styled(sentence, content.highlight_term, style=highlight_style)
                )
                text_label.setStyleSheet(
                    "color:#334155;font-size:13px;line-height:1.55;background:transparent;"
                )
                text_label.setSizePolicy(
                    QSizePolicy.Policy.Expanding,
                    QSizePolicy.Policy.Preferred,
                )
                row_layout.addWidget(
                    text_label,
                    1,
                    Qt.AlignmentFlag.AlignTop,
                )

                if tts_enabled:
                    audio_btn = self._make_speaker_button()
                    audio_btn.setToolTip(tr("learning.tts_play_example"))
                    audio_btn.clicked.connect(
                        lambda _checked=False, s=sentence: self._audio.speak_sentence(s)
                    )
                    row_layout.addWidget(
                        audio_btn,
                        0,
                        Qt.AlignmentFlag.AlignTop,
                    )

                self._examples_layout.addWidget(row)

            self._examples_host.setVisible(True)

        self.setVisible(True)

    @staticmethod
    def _ukrainian_in_hint(ukrainian: str, hint_html: str) -> bool:
        normalized = ukrainian.strip().casefold()
        if not normalized:
            return True
        plain = hint_html.casefold()
        return normalized in plain

    def _clear_example_rows(self) -> None:
        while self._examples_layout.count():
            item = self._examples_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    @staticmethod
    def _make_speaker_button() -> QPushButton:
        btn = QPushButton()
        btn.setObjectName("quizExampleSpeakerBtn")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(EXAMPLE_SPEAKER_GHOST_STYLE)
        btn.setIcon(speaker_icon(size=14))
        btn.setIconSize(QSize(14, 14))
        btn.setFixedSize(28, 28)
        btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        return btn
