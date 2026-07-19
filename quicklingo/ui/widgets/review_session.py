from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QKeyEvent, QKeySequence, QPainter, QPainterPath, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from quicklingo.config.loader import resolve_learning_direction
from quicklingo.db import learning
from quicklingo.features import get_feature, is_enabled
from quicklingo.i18n import tr
from quicklingo.learning.answer_check import AnswerResult
from quicklingo.learning.card_display import (
    display_term,
    highlight_term_in_context,
    highlight_term_styled,
    parse_context,
    phonetic_display_text,
)
from quicklingo.learning.cram_queue import cram_hard_cards, cram_train_cards
from quicklingo.learning.fsrs_review import preview_fsrs_intervals
from quicklingo.learning.image_resolver import resolve_image_path
from quicklingo.learning.review_queue import count_due_cards
from quicklingo.learning.tts.audio_service import AudioService
from quicklingo.learning.tts.prefetch import collect_review_card_tts_texts, collect_review_tts_texts
from quicklingo.learning.tts.prefetch_service import tts_prefetch_service
from quicklingo.ui.controllers.review_session_controller import (
    ReviewSessionController,
    SessionStats,
)
from quicklingo.workers.card_image_worker import CardImageFetchWorker, CardImagePrefetchWorker

_PHONETIC_STYLE = "color: #64748b;"
_ANSWER_PHONETIC_STYLE = _PHONETIC_STYLE
_CONTENT_MIN_WIDTH = 600
_CONTENT_MAX_WIDTH = 750
_IMAGE_SIZE = 240
_IMAGE_RADIUS = 12
_MAX_WIDGET = 16777215

_REVIEW_STYLE = """
ReviewSessionWidget QLabel#reviewMetaLabel {
    color: #64748b;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.04em;
}
QPushButton#btnStartReview {
    background-color: #3b82f6;
    color: #ffffff;
    border: none;
    border-radius: 8px;
    padding: 8px 22px;
    font-size: 14px;
    font-weight: 600;
    min-height: 36px;
}
QPushButton#btnStartReview:hover:enabled {
    background-color: #2563eb;
}
QPushButton#btnStartReview:disabled {
    background-color: #e2e8f0;
    color: #94a3b8;
}
QPushButton#btnModeToggle {
    background-color: #ffffff;
    color: #475569;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    padding: 6px 14px;
    font-size: 13px;
    min-height: 32px;
}
QPushButton#btnModeToggle:checked {
    background-color: #eff6ff;
    border-color: #3b82f6;
    color: #1d4ed8;
    font-weight: 600;
}
QPushButton#btnShowAnswer {
    background-color: #ffffff;
    color: #1e293b;
    border: 1px solid #d1d5db;
    border-radius: 8px;
    padding: 8px 18px;
    font-size: 13px;
    font-weight: 600;
    min-height: 36px;
}
QPushButton#btnShowAnswer:hover:enabled {
    background-color: #f8fafc;
    border-color: #94a3b8;
}
QPushButton#btnAgain {
    background-color: #fef2f2;
    color: #dc2626;
    border: none;
    border-radius: 8px;
    padding: 8px 20px;
    font-weight: bold;
    font-size: 13px;
    min-height: 36px;
}
QPushButton#btnAgain:hover:enabled {
    background-color: #fee2e2;
}
QPushButton#btnHard {
    background-color: #fff7ed;
    color: #ea580c;
    border: none;
    border-radius: 8px;
    padding: 8px 20px;
    font-weight: bold;
    font-size: 13px;
    min-height: 36px;
}
QPushButton#btnHard:hover:enabled {
    background-color: #ffedd5;
}
QPushButton#btnGood {
    background-color: #f0fdf4;
    color: #16a34a;
    border: none;
    border-radius: 8px;
    padding: 8px 20px;
    font-weight: bold;
    font-size: 13px;
    min-height: 36px;
}
QPushButton#btnGood:hover:enabled {
    background-color: #dcfce7;
}
QPushButton#btnEasy {
    background-color: #eff6ff;
    color: #2563eb;
    border: none;
    border-radius: 8px;
    padding: 8px 20px;
    font-weight: bold;
    font-size: 13px;
    min-height: 36px;
}
QPushButton#btnEasy:hover:enabled {
    background-color: #dbeafe;
}
QFrame#reviewCardFrame {
    background-color: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
}
QWidget#reviewImageColumn {
    background: transparent;
}
QFrame#reviewImageFrame {
    background: transparent;
    border: none;
}
QLabel#reviewImageLabel {
    background: transparent;
    border: none;
}
QWidget#reviewFrontColumn {
    background: transparent;
}
QPushButton#reviewSpeakerBtn {
    border: none;
    background: transparent;
    font-family: "Segoe UI Emoji", "Segoe UI Symbol", sans-serif;
    font-size: 16px;
    min-width: 28px;
    max-width: 28px;
    min-height: 28px;
    max-height: 28px;
    padding: 0px;
}
QPushButton#reviewSpeakerBtn:hover {
    background-color: #F1F5F9;
    border-radius: 14px;
}
QWidget#reviewMainContent {
    background: transparent;
    min-width: 600px;
    max-width: 750px;
}
QWidget#reviewBackSection {
    background: transparent;
}
QWidget#reviewExampleRow {
    background: transparent;
}
QFrame#reviewExampleQuote {
    background: transparent;
    border: none;
    border-left: 4px solid #CBD5E1;
}
QLabel#reviewDefinitionLabel {
    background: transparent;
}
QLabel#reviewHintLabel {
    color: #64748b;
    background: transparent;
}
QLabel#reviewTermLabel {
    color: #1e293b;
    background: transparent;
}
QLabel#reviewAnswerLabel {
    color: #1d4ed8;
    background: transparent;
}
ReviewSessionWidget QProgressBar#reviewProgressBar {
    border: none;
    background-color: #e2e8f0;
    border-radius: 3px;
    max-height: 4px;
    min-height: 4px;
}
ReviewSessionWidget QProgressBar#reviewProgressBar::chunk {
    background-color: #3b82f6;
    border-radius: 3px;
}
QProgressBar {
    border: none;
    background-color: #e2e8f0;
    border-radius: 4px;
    max-height: 6px;
    min-height: 6px;
}
QProgressBar::chunk {
    background-color: #3b82f6;
    border-radius: 4px;
}
"""


def get_rounded_pixmap(
    pixmap: QPixmap,
    *,
    size: int = _IMAGE_SIZE,
    radius: int = _IMAGE_RADIUS,
) -> QPixmap:
    """Scale-to-fill square crop, then clip to rounded corners (QSS cannot do this)."""
    if pixmap.isNull():
        return pixmap
    scaled = pixmap.scaled(
        size,
        size,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    x = max(0, (scaled.width() - size) // 2)
    y = max(0, (scaled.height() - size) // 2)
    cropped = scaled.copy(x, y, size, size)
    target = QPixmap(cropped.size())
    target.fill(Qt.GlobalColor.transparent)
    painter = QPainter(target)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    path = QPainterPath()
    path.addRoundedRect(0, 0, cropped.width(), cropped.height(), radius, radius)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, cropped)
    painter.end()
    return target


def _html_definition_block(body_html: str) -> str:
    return (
        '<table cellspacing="0" cellpadding="0" border="0" '
        'style="margin:0;border-collapse:separate;">'
        "<tr>"
        '<td style="background-color:#F8FAFC;border:1px solid #E2E8F0;'
        "border-radius:8px;padding:10px 14px;color:#475569;font-size:15px;"
        'white-space:normal;word-wrap:break-word;">'
        f"<b>Definition:</b> <i>{body_html}</i>"
        "</td></tr></table>"
    )


def _definition_body_from_notes(notes: str) -> str:
    plain = (notes or "").strip()
    if plain.lower().startswith("definition:"):
        plain = plain.split(":", 1)[1].strip()
    return plain


class ReviewSessionWidget(QWidget):
    grade_submitted = Signal()
    session_finished = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("ReviewSessionWidget")
        self.setStyleSheet(_REVIEW_STYLE)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._controller = ReviewSessionController()
        self._deck_id: int | None = None
        self._direction = "ua-en"
        self._example_sentences: list[str] = []
        self._image_worker: CardImageFetchWorker | None = None
        self._image_prefetch: CardImagePrefetchWorker | None = None
        self._image_fetch_card_id: int | None = None
        self._height_sync_token = 0

        self._audio = AudioService(self)
        tts_prefetch_service().term_ready.connect(self._on_term_audio_ready)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        info_row = QHBoxLayout()
        self._due_label = QLabel()
        self._due_label.setObjectName("reviewMetaLabel")
        self._streak_label = QLabel()
        self._streak_label.setObjectName("reviewMetaLabel")
        info_row.addWidget(self._due_label)
        info_row.addStretch()
        info_row.addWidget(self._streak_label)
        layout.addLayout(info_row)

        controls_row = QHBoxLayout()
        self._mode_flip_btn = QPushButton()
        self._mode_flip_btn.setObjectName("btnModeToggle")
        self._mode_flip_btn.setCheckable(True)
        self._mode_flip_btn.setChecked(True)
        self._mode_flip_btn.clicked.connect(lambda: self._set_mode("flip"))
        self._mode_typing_btn = QPushButton()
        self._mode_typing_btn.setObjectName("btnModeToggle")
        self._mode_typing_btn.setCheckable(True)
        self._mode_typing_btn.clicked.connect(lambda: self._set_mode("typing"))
        self._start_btn = QPushButton()
        self._start_btn.setObjectName("btnStartReview")
        self._start_btn.clicked.connect(self._start_session)
        for btn in (self._mode_flip_btn, self._mode_typing_btn, self._start_btn):
            btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self._start_btn.setMinimumWidth(160)
        controls_row.addWidget(self._mode_flip_btn)
        controls_row.addWidget(self._mode_typing_btn)
        controls_row.addStretch()
        controls_row.addWidget(self._start_btn)
        layout.addLayout(controls_row)

        self._stack = QStackedWidget()
        self._card_frame = QFrame()
        self._card_frame.setObjectName("reviewCardFrame")
        self._card_frame.setFrameShape(QFrame.Shape.NoFrame)
        self._card_frame.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        card_outer = QVBoxLayout(self._card_frame)
        card_outer.setContentsMargins(24, 24, 24, 24)

        self._card_stack = QStackedWidget()

        idle_page = self._build_idle_page()

        active_page = self._build_active_page()

        self._card_stack.addWidget(idle_page)
        self._card_stack.addWidget(active_page)
        card_outer.addWidget(self._card_stack)

        self._build_summary_and_controls(layout)

        self._setup_review_hotkeys()
        self.retranslate_ui()
        self._show_idle_ui()

    def _build_idle_page(self) -> QWidget:
        idle_page = QWidget()
        idle_layout = QVBoxLayout(idle_page)
        self._idle_stack = QStackedWidget()

        ready_widget = QWidget()
        ready_layout = QVBoxLayout(ready_widget)
        self._idle_label = QLabel()
        self._idle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._idle_label.setWordWrap(True)
        self._idle_label.setStyleSheet("color: #666; font-size: 12pt; padding: 24px;")
        ready_layout.addStretch()
        ready_layout.addWidget(self._idle_label)
        ready_layout.addStretch()

        done_widget = QWidget()
        done_layout = QVBoxLayout(done_widget)
        done_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._done_icon = QLabel("🏆")
        self._done_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        done_icon_font = self._done_icon.font()
        done_icon_font.setPointSize(36)
        self._done_icon.setFont(done_icon_font)
        self._done_title = QLabel()
        self._done_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._done_title.setWordWrap(True)
        done_title_font = self._done_title.font()
        done_title_font.setPointSize(14)
        done_title_font.setBold(True)
        self._done_title.setFont(done_title_font)
        self._done_subtitle = QLabel()
        self._done_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._done_subtitle.setWordWrap(True)
        self._done_subtitle.setStyleSheet("color: #666; font-size: 11pt;")
        cram_btn_row = QHBoxLayout()
        cram_btn_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cram_hard_btn = QPushButton()
        self._cram_hard_btn.clicked.connect(self._start_cram_hard)
        self._cram_train_btn = QPushButton()
        self._cram_train_btn.clicked.connect(self._start_cram_train)
        cram_btn_row.addWidget(self._cram_hard_btn)
        cram_btn_row.addWidget(self._cram_train_btn)
        done_layout.addStretch()
        done_layout.addWidget(self._done_icon)
        done_layout.addWidget(self._done_title)
        done_layout.addWidget(self._done_subtitle)
        done_layout.addLayout(cram_btn_row)
        done_layout.addStretch()

        self._idle_stack.addWidget(ready_widget)
        self._idle_stack.addWidget(done_widget)
        idle_layout.addWidget(self._idle_stack)
        return idle_page

    def _build_active_page(self) -> QWidget:
        active_page = QWidget()
        active_outer = QHBoxLayout(active_page)
        active_outer.setContentsMargins(0, 0, 0, 0)
        active_outer.setSpacing(0)
        active_outer.addStretch(1)

        self._main_column = QWidget()
        self._main_column.setObjectName("reviewMainContent")
        self._main_column.setMinimumWidth(_CONTENT_MIN_WIDTH)
        self._main_column.setMaximumWidth(_CONTENT_MAX_WIDTH)
        self._main_column.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        main_layout = QVBoxLayout(self._main_column)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        front_row = QWidget()
        self._top_layout = QHBoxLayout(front_row)
        self._top_layout.setContentsMargins(0, 0, 0, 0)
        self._top_layout.setSpacing(0)
        self._top_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._image_column = QWidget()
        self._image_column.setObjectName("reviewImageColumn")
        self._image_column.setFixedWidth(_IMAGE_SIZE)
        self._image_column.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        image_col_layout = QVBoxLayout(self._image_column)
        image_col_layout.setContentsMargins(0, 0, 0, 0)
        image_col_layout.setSpacing(0)

        self._image_label = QLabel()
        self._image_label.setObjectName("reviewImageLabel")
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setFixedSize(_IMAGE_SIZE, _IMAGE_SIZE)
        self._image_label.setScaledContents(False)
        self._image_label.setVisible(False)
        image_col_layout.addWidget(self._image_label)
        self._image_column.setVisible(False)

        self._front_column = QWidget()
        self._front_column.setObjectName("reviewFrontColumn")
        self._front_column.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        self._front_layout = QVBoxLayout(self._front_column)
        self._front_layout.setContentsMargins(0, 0, 0, 0)
        self._front_layout.setSpacing(10)
        self._front_layout.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )

        self._term_row = QWidget()
        self._term_row.setObjectName("reviewTermRow")
        self._term_row_layout = QHBoxLayout(self._term_row)
        self._term_row_layout.setContentsMargins(0, 0, 0, 0)
        self._term_row_layout.setSpacing(10)
        self._term_label = QLabel()
        self._term_label.setObjectName("reviewTermLabel")
        self._term_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self._term_label.setTextFormat(Qt.TextFormat.PlainText)
        self._term_label.setWordWrap(True)
        self._term_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )
        self._term_play_btn = self._make_speaker_button()
        self._term_play_btn.clicked.connect(self._play_audio)
        self._term_row_layout.addWidget(self._term_label, stretch=1)
        self._term_row_layout.addWidget(
            self._term_play_btn, alignment=Qt.AlignmentFlag.AlignVCenter
        )

        self._front_phonetic_widget = QWidget()
        self._front_phonetic_layout = QHBoxLayout(self._front_phonetic_widget)
        self._front_phonetic_layout.setContentsMargins(0, 0, 0, 0)
        self._front_phonetic_layout.setSpacing(10)
        self._front_phonetic_label = QLabel()
        self._front_phonetic_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self._front_phonetic_label.setStyleSheet(_PHONETIC_STYLE)
        self._front_phonetic_label.setWordWrap(True)
        self._front_phonetic_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        self._front_play_btn = self._make_speaker_button()
        self._front_play_btn.clicked.connect(self._play_audio)
        self._front_phonetic_layout.addWidget(self._front_phonetic_label, stretch=1)
        self._front_phonetic_layout.addWidget(
            self._front_play_btn, alignment=Qt.AlignmentFlag.AlignVCenter
        )
        self._front_phonetic_widget.setVisible(False)

        self._hint_label = QLabel()
        self._hint_label.setObjectName("reviewHintLabel")
        self._hint_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._hint_label.setWordWrap(True)
        self._hint_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        self._typing_input = QLineEdit()
        self._typing_input.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._typing_input.returnPressed.connect(self._submit_typing)
        self._typing_feedback = QLabel()
        self._typing_feedback.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._enable_wrapping_label(self._typing_feedback)

        self._front_content: list[QWidget] = [
            self._term_row,
            self._front_phonetic_widget,
            self._hint_label,
            self._typing_input,
            self._typing_feedback,
        ]
        for widget in self._front_content:
            self._front_layout.addWidget(widget)

        self._front_has_image: bool | None = None

        self._back_section = QWidget()
        self._back_section.setObjectName("reviewBackSection")
        self._back_section.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        back_layout = QVBoxLayout(self._back_section)
        back_layout.setContentsMargins(0, 0, 0, 0)
        back_layout.setSpacing(12)

        self._answer_block = QWidget()
        self._answer_block.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        answer_layout = QVBoxLayout(self._answer_block)
        answer_layout.setContentsMargins(0, 0, 0, 0)
        answer_layout.setSpacing(8)
        self._answer_label = QLabel()
        self._answer_label.setObjectName("reviewAnswerLabel")
        self._answer_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._answer_label.setTextFormat(Qt.TextFormat.PlainText)
        self._answer_label.setWordWrap(True)
        self._answer_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        self._answer_phonetic_widget = QWidget()
        answer_phonetic_layout = QHBoxLayout(self._answer_phonetic_widget)
        answer_phonetic_layout.setContentsMargins(0, 0, 0, 0)
        answer_phonetic_layout.setSpacing(10)
        self._answer_phonetic_label = QLabel()
        self._answer_phonetic_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self._answer_phonetic_label.setStyleSheet(_ANSWER_PHONETIC_STYLE)
        self._answer_phonetic_label.setWordWrap(True)
        self._answer_phonetic_label.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Preferred,
        )
        self._answer_play_btn = self._make_speaker_button()
        self._answer_play_btn.clicked.connect(self._play_audio)
        answer_phonetic_layout.addStretch(1)
        answer_phonetic_layout.addWidget(self._answer_phonetic_label)
        answer_phonetic_layout.addWidget(
            self._answer_play_btn, alignment=Qt.AlignmentFlag.AlignVCenter
        )
        answer_phonetic_layout.addStretch(1)
        # Full-width add — AlignHCenter on the item squeezes wrapping labels.
        answer_layout.addWidget(self._answer_label)
        answer_layout.addWidget(self._answer_phonetic_widget)
        self._answer_block.setVisible(False)

        self._definition_label = QLabel()
        self._definition_label.setObjectName("reviewDefinitionLabel")
        self._definition_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._definition_label.setTextFormat(Qt.TextFormat.RichText)
        self._definition_label.setWordWrap(True)
        self._definition_label.setMinimumWidth(500)
        self._definition_label.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Preferred,
        )
        self._definition_label.setVisible(False)

        self._definition_row = QWidget()
        definition_row_layout = QHBoxLayout(self._definition_row)
        definition_row_layout.setContentsMargins(0, 0, 0, 0)
        definition_row_layout.setSpacing(0)
        definition_row_layout.addWidget(self._definition_label)
        definition_row_layout.addStretch(1)
        self._definition_row.setVisible(False)

        self._examples_host = QWidget()
        self._examples_layout = QVBoxLayout(self._examples_host)
        self._examples_layout.setContentsMargins(0, 0, 0, 0)
        self._examples_layout.setSpacing(0)
        self._examples_host.setVisible(False)

        back_layout.addWidget(self._answer_block)
        back_layout.addWidget(self._definition_row)
        back_layout.addWidget(self._examples_host)
        self._back_section.setVisible(False)

        self._card_content: list[QWidget] = [
            *self._front_content,
            self._answer_block,
            self._definition_row,
            self._examples_host,
            self._back_section,
        ]

        self._apply_card_fonts()
        self._apply_front_layout(has_image=False, force=True)

        main_layout.addWidget(front_row, stretch=0)
        main_layout.addSpacing(10)
        main_layout.addWidget(self._back_section, stretch=0)
        main_layout.addStretch(1)

        active_outer.addWidget(self._main_column, stretch=0)
        active_outer.addStretch(1)
        return active_page

    def _build_summary_and_controls(self, layout: QVBoxLayout) -> None:
        self._summary_label = QLabel()
        self._summary_label.setWordWrap(True)
        self._summary_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        summary_wrap = QWidget()
        summary_layout = QVBoxLayout(summary_wrap)
        summary_layout.addStretch()
        summary_layout.addWidget(self._summary_label)
        summary_layout.addStretch()

        self._stack.addWidget(self._card_frame)
        self._stack.addWidget(summary_wrap)
        self._stack.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        layout.addWidget(self._stack, stretch=1)

        self._progress_widget = QWidget()
        progress_layout = QVBoxLayout(self._progress_widget)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        self._progress_label = QLabel()
        self._progress_bar = QProgressBar()
        self._progress_bar.setObjectName("reviewProgressBar")
        self._progress_bar.setTextVisible(False)
        self._bucket_label = QLabel()
        self._bucket_label.setStyleSheet("color: #64748b; font-size: 11px;")
        progress_layout.addWidget(self._progress_label)
        progress_layout.addWidget(self._progress_bar)
        progress_layout.addWidget(self._bucket_label)
        layout.addWidget(self._progress_widget)

        self._grade_widget = QWidget()
        grade_row = QHBoxLayout(self._grade_widget)
        grade_row.setContentsMargins(0, 0, 0, 0)
        self._show_answer_btn = QPushButton()
        self._show_answer_btn.setObjectName("btnShowAnswer")
        self._show_answer_btn.clicked.connect(self._reveal_or_flip)
        self._again_btn = QPushButton()
        self._again_btn.setObjectName("btnAgain")
        self._again_btn.clicked.connect(lambda: self._submit_grade(1))
        self._hard_btn = QPushButton()
        self._hard_btn.setObjectName("btnHard")
        self._hard_btn.clicked.connect(lambda: self._submit_grade(2))
        self._good_btn = QPushButton()
        self._good_btn.setObjectName("btnGood")
        self._good_btn.clicked.connect(lambda: self._submit_grade(3))
        self._easy_btn = QPushButton()
        self._easy_btn.setObjectName("btnEasy")
        self._easy_btn.clicked.connect(lambda: self._submit_grade(4))
        grade_row.addStretch()
        grade_row.addWidget(self._show_answer_btn)
        grade_row.addWidget(self._again_btn)
        grade_row.addWidget(self._hard_btn)
        grade_row.addWidget(self._good_btn)
        grade_row.addWidget(self._easy_btn)
        grade_row.addStretch()
        layout.addWidget(self._grade_widget)

    def _setup_review_hotkeys(self) -> None:
        """Hotkeys only while this widget (or a child) has focus — not other tabs."""
        context = Qt.ShortcutContext.WidgetWithChildrenShortcut
        for seq, slot in (
            ("Space", self._hotkey_space),
            ("Return", self._hotkey_enter),
            ("Enter", self._hotkey_enter),
            ("1", lambda: self._hotkey_grade(1)),
            ("2", lambda: self._hotkey_grade(2)),
            ("3", lambda: self._hotkey_grade(3)),
            ("4", lambda: self._hotkey_grade(4)),
        ):
            shortcut = QShortcut(QKeySequence(seq), self)
            shortcut.setContext(context)
            shortcut.activated.connect(slot)

    def _review_hotkeys_context_ok(self) -> bool:
        if not self.isVisible() or not self._controller.session_active:
            return False
        focus = QApplication.focusWidget()
        if focus is None:
            return True
        # Another top-level dialog / different tab owns focus.
        if not (focus is self or self.isAncestorOf(focus)):
            return False
        return True

    def _focus_in_typing_input(self) -> bool:
        focus = QApplication.focusWidget()
        return focus is self._typing_input

    def _hotkey_space(self) -> None:
        if not self._review_hotkeys_context_ok():
            return
        if self._controller.revealed:
            self._hotkey_grade(3)
            return
        # QShortcut consumes Space; re-insert so typing mode still works.
        if self._focus_in_typing_input():
            self._typing_input.insert(" ")
            return
        if self._show_answer_btn.isVisible() and self._show_answer_btn.isEnabled():
            self._reveal_or_flip()

    def _hotkey_enter(self) -> None:
        if not self._review_hotkeys_context_ok():
            return
        if self._controller.revealed:
            self._hotkey_grade(3)
            return
        # QShortcut consumes Enter; keep typing submit wired to returnPressed.
        if self._focus_in_typing_input():
            self._submit_typing()
            return
        if self._show_answer_btn.isVisible() and self._show_answer_btn.isEnabled():
            self._reveal_or_flip()

    def _hotkey_space_or_enter(self) -> None:
        """Shared path for keyPressEvent (Space and Enter behave the same here)."""
        if not self._review_hotkeys_context_ok():
            return
        if self._controller.revealed:
            self._hotkey_grade(3)
            return
        if self._focus_in_typing_input():
            return
        if self._show_answer_btn.isVisible() and self._show_answer_btn.isEnabled():
            self._reveal_or_flip()

    def _hotkey_grade(self, rating: int) -> None:
        if not self._review_hotkeys_context_ok():
            return
        if not self._controller.revealed:
            # Digits are stolen by QShortcut; restore them for typing answers.
            if self._focus_in_typing_input():
                self._typing_input.insert(str(rating))
            return
        grade_buttons = {
            1: self._again_btn,
            2: self._hard_btn,
            3: self._good_btn,
            4: self._easy_btn,
        }
        btn = grade_buttons.get(rating)
        if btn is None or not btn.isVisible() or not btn.isEnabled():
            return
        self._submit_grade(rating)

    def _ensure_review_focus(self) -> None:
        # Keep the typing field focused until the answer is checked; after reveal
        # pull focus back so Space / 1–4 are not trapped in the line edit.
        if (
            not self._controller.revealed
            and self._controller.mode == "typing"
            and self._typing_input.isVisible()
        ):
            return
        self.setFocus(Qt.FocusReason.OtherFocusReason)

    def _make_speaker_button(self) -> QPushButton:
        btn = QPushButton("🔊")
        btn.setObjectName("reviewSpeakerBtn")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFlat(True)
        btn.setFixedSize(28, 28)
        btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        return btn

    def _apply_card_fonts(self) -> None:
        """Fonts via QFont so sizeHint matches painted glyphs (QSS font-size does not)."""
        term_font = QFont(self._term_label.font())
        term_font.setPointSize(24)
        term_font.setBold(True)
        self._term_label.setFont(term_font)

        answer_font = QFont(self._answer_label.font())
        answer_font.setPixelSize(28)
        answer_font.setWeight(QFont.Weight.ExtraBold)
        self._answer_label.setFont(answer_font)

        phonetic_font = QFont(self._front_phonetic_label.font())
        phonetic_font.setPointSize(12)
        phonetic_font.setItalic(True)
        self._front_phonetic_label.setFont(phonetic_font)
        self._answer_phonetic_label.setFont(phonetic_font)

        hint_font = QFont(self._hint_label.font())
        hint_font.setPointSize(11)
        self._hint_label.setFont(hint_font)

    def _clear_height_constraints(self) -> None:
        for widget in (
            self._term_row,
            self._term_label,
            self._front_phonetic_widget,
            self._front_phonetic_label,
            self._hint_label,
            self._front_column,
            self._answer_label,
            self._answer_block,
            self._back_section,
        ):
            widget.setMaximumHeight(_MAX_WIDGET)

    def _sync_label_heights(self) -> None:
        """Ensure painted font fits; clears stale max-heights left after image cards."""
        self._clear_height_constraints()
        for label in (
            self._term_label,
            self._front_phonetic_label,
            self._hint_label,
            self._answer_label,
            self._answer_phonetic_label,
        ):
            self._fit_label_height(label)
        self._term_row.updateGeometry()
        self._front_column.updateGeometry()
        self._answer_block.updateGeometry()
        self._back_section.updateGeometry()
        if self._main_column.layout() is not None:
            self._main_column.layout().activate()
        self._main_column.updateGeometry()
        if self._card_frame.layout() is not None:
            self._card_frame.layout().activate()

    def _schedule_height_sync(self) -> None:
        self._height_sync_token += 1
        token = self._height_sync_token
        QTimer.singleShot(0, lambda t=token: self._run_scheduled_height_sync(t))

    def _run_scheduled_height_sync(self, token: int) -> None:
        if token != self._height_sync_token:
            return
        self._sync_label_heights()

    def _fit_label_height(self, label: QLabel) -> None:
        metrics = label.fontMetrics()
        # Ascents/descents for bold display fonts need more than raw height().
        line = metrics.boundingRect("Åy").height() + metrics.leading() + 8
        line = max(line, metrics.height() + 8)
        if not label.text():
            label.setMinimumHeight(0)
            return
        if not label.wordWrap():
            label.setMinimumHeight(line)
            return
        width = label.width()
        if width < 40:
            parent = label.parentWidget()
            if parent is not None and parent.width() >= 40:
                width = parent.width()
            elif self._front_column.width() >= 40:
                width = max(40, self._front_column.width() - 40)
            else:
                width = _CONTENT_MIN_WIDTH
        wrapped = label.heightForWidth(width)
        label.setMinimumHeight(max(line, wrapped))
        label.updateGeometry()

    def _apply_front_layout(self, *, has_image: bool, force: bool = False) -> None:
        """Image beside text, or full-width text when there is no picture."""
        if not force and self._front_has_image is has_image:
            return
        self._front_has_image = has_image

        while self._top_layout.count():
            self._top_layout.takeAt(0)

        self._front_column.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        if has_image:
            self._top_layout.addWidget(self._image_column, stretch=0)
            self._top_layout.addSpacing(30)
            self._top_layout.addWidget(
                self._front_column,
                stretch=1,
                alignment=Qt.AlignmentFlag.AlignTop,
            )
            text_align = Qt.AlignmentFlag.AlignLeft
        else:
            self._top_layout.addWidget(self._front_column, stretch=1)
            text_align = Qt.AlignmentFlag.AlignHCenter

        self._front_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._term_label.setAlignment(text_align | Qt.AlignmentFlag.AlignTop)
        self._front_phonetic_label.setAlignment(
            text_align | Qt.AlignmentFlag.AlignTop
        )
        self._hint_label.setAlignment(text_align | Qt.AlignmentFlag.AlignTop)
        self._typing_input.setAlignment(text_align)
        self._typing_feedback.setAlignment(text_align)

        self._rebuild_inline_row(
            self._term_row_layout,
            self._term_label,
            self._term_play_btn,
        )
        self._rebuild_inline_row(
            self._front_phonetic_layout,
            self._front_phonetic_label,
            self._front_play_btn,
        )
        self._sync_label_heights()
        self._schedule_height_sync()

    @staticmethod
    def _rebuild_inline_row(
        layout: QHBoxLayout,
        label: QLabel,
        button: QPushButton,
    ) -> None:
        while layout.count():
            layout.takeAt(0)
        # Label expands; text alignment (left/center) handles deck-switch stability.
        layout.addWidget(label, stretch=1)
        layout.addWidget(button, alignment=Qt.AlignmentFlag.AlignVCenter)

    def _set_front_term(self, text: str) -> None:
        self._term_label.setText(text)
        self._term_play_btn.setVisible(self._tts_enabled())
        self._sync_label_heights()

    def _enable_wrapping_label(self, label: QLabel) -> None:
        label.setWordWrap(True)
        label.setMinimumWidth(0)
        policy = label.sizePolicy()
        policy.setHorizontalPolicy(QSizePolicy.Policy.Expanding)
        policy.setVerticalPolicy(QSizePolicy.Policy.Preferred)
        # heightForWidth + stale sizeHints after image→text layout switches clips glyphs.
        policy.setHeightForWidth(False)
        label.setSizePolicy(policy)

    def _card_has_resolved_image(self, card: learning.LearningCard) -> bool:
        if not is_enabled("learning.card_images"):
            return False
        if not card.image_path:
            return False
        return resolve_image_path(card.image_path) is not None

    def _card_expects_image(self, card: learning.LearningCard) -> bool:
        """True when the card already has an image or will fetch one."""
        if not is_enabled("learning.card_images"):
            return False
        if self._card_has_resolved_image(card):
            return True
        return bool((card.image_prompt or "").strip())

    def _reset_card_presentation(self) -> None:
        """Drop layout state left over from the previous deck/card (esp. image cards)."""
        self._front_has_image = None
        self._image_label.clear()
        self._image_label.clearMask()
        self._image_label.setFixedSize(_IMAGE_SIZE, _IMAGE_SIZE)
        self._image_label.setVisible(False)
        self._image_column.setVisible(False)
        self._apply_front_layout(has_image=False, force=True)

    def _tts_enabled(self) -> bool:
        return is_enabled("learning.tts_enabled")

    def _play_example_sentence(self, sentence: str) -> None:
        if not self._tts_enabled():
            return
        self._audio.speak_sentence(sentence)
        self._set_play_button_active(True)

    def _clear_example_rows(self) -> None:
        while self._examples_layout.count():
            item = self._examples_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _populate_example_rows(self, examples: list[str], term: str) -> None:
        self._clear_example_rows()
        self._example_sentences = list(examples)
        tts_enabled = self._tts_enabled()
        for sentence in examples:
            row = QWidget()
            row.setObjectName("reviewExampleRow")
            sentence_layout = QHBoxLayout(row)
            sentence_layout.setContentsMargins(0, 0, 0, 8)
            sentence_layout.setSpacing(8)

            text_label = QLabel()
            text_label.setTextFormat(Qt.TextFormat.RichText)
            text_label.setWordWrap(True)
            text_label.setAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            text_label.setText(highlight_term_in_context(sentence, term))
            text_label.setStyleSheet(
                "color:#334155;font-size:16px;line-height:1.4;"
            )
            text_label.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Preferred,
            )

            quote = QFrame()
            quote.setObjectName("reviewExampleQuote")
            quote_layout = QHBoxLayout(quote)
            quote_layout.setContentsMargins(14, 4, 0, 4)
            quote_layout.setSpacing(0)
            quote_layout.addWidget(text_label)

            # Text/quote expands; speaker docks to the right edge.
            sentence_layout.addWidget(quote, 1)
            if tts_enabled:
                audio_btn = self._make_speaker_button()
                audio_btn.clicked.connect(
                    lambda _checked=False, s=sentence: self._play_example_sentence(s)
                )
                sentence_layout.addWidget(audio_btn)
            self._examples_layout.addWidget(row)

    def retranslate_ui(self) -> None:
        self._mode_flip_btn.setText(tr("learning.mode_flip"))
        self._mode_typing_btn.setText(tr("learning.mode_typing"))
        self._start_btn.setText(tr("learning.start_review"))
        self._show_answer_btn.setText(tr("learning.show_answer"))
        self._again_btn.setText(tr("learning.review_again"))
        self._hard_btn.setText(tr("learning.review_hard"))
        self._good_btn.setText(tr("learning.review_good"))
        self._easy_btn.setText(tr("learning.review_easy"))
        self._idle_label.setText(tr("learning.review_idle_hint"))
        self._done_title.setText(tr("learning.review_done_title"))
        self._done_subtitle.setText(tr("learning.review_done_subtitle"))
        self._cram_hard_btn.setText(tr("learning.review_cram_hard"))
        self._cram_train_btn.setText(tr("learning.review_cram_train"))
        self._update_due_label()
        self._update_streak_label()
        self._update_done_buttons()

    def set_deck(self, deck_id: int | None, *, direction: str = "ua-en") -> None:
        self._cancel_image_fetch()
        self._cancel_image_prefetch()
        self._deck_id = deck_id
        self._direction = direction
        self._controller.reset()
        self._reset_card_presentation()
        self._stack.setCurrentIndex(0)
        self._update_due_label()
        self._show_idle_ui()

    def start_cram_with_cards(
        self,
        deck_id: int,
        cards: list[learning.LearningCard],
        *,
        direction: str,
    ) -> None:
        self._deck_id = deck_id
        self._direction = direction
        if not self._controller.start_cram_session(
            deck_id, cards, direction=direction, mode=self._current_mode()
        ):
            return
        self._stack.setCurrentIndex(0)
        self._progress_widget.setVisible(True)
        self._grade_widget.setVisible(True)
        self._prefetch_session_tts()
        self._prefetch_session_images()
        self._render_current_card()

    def update_streak(self) -> None:
        self._update_streak_label()

    def _set_mode(self, mode: str) -> None:
        self._mode_flip_btn.setChecked(mode == "flip")
        self._mode_typing_btn.setChecked(mode == "typing")

    def _current_mode(self) -> str:
        return "typing" if self._mode_typing_btn.isChecked() else "flip"

    def _due_count(self) -> int:
        if self._deck_id is None:
            return 0
        return count_due_cards(self._deck_id)

    def _update_due_label(self) -> None:
        if self._deck_id is None:
            self._due_label.setText("")
            return
        self._due_label.setText(tr("learning.due_today", count=self._due_count()).upper())
        self._update_done_buttons()

    def _update_done_buttons(self) -> None:
        if self._deck_id is None:
            self._cram_hard_btn.setEnabled(False)
            self._cram_train_btn.setEnabled(False)
            return
        struggled = cram_hard_cards(self._deck_id)
        train_cards = cram_train_cards(
            self._deck_id,
            self._controller.last_normal_session_card_ids,
        )
        self._cram_hard_btn.setEnabled(bool(struggled))
        self._cram_train_btn.setEnabled(bool(train_cards))
        self._cram_hard_btn.setToolTip(
            "" if struggled else tr("learning.review_cram_hard_empty")
        )
        self._cram_train_btn.setToolTip(
            "" if train_cards else tr("learning.review_cram_train_empty")
        )

    def _update_streak_label(self) -> None:
        from quicklingo import settings

        streak, _last = settings.get_learning_streak()
        self._streak_label.setText(tr("learning.streak_label", streak=streak).upper())

    def _show_idle_ui(self) -> None:
        self._card_stack.setCurrentIndex(0)
        self._clear_image()
        for widget in self._card_content:
            widget.setVisible(False)
        self._progress_widget.setVisible(False)
        self._grade_widget.setVisible(False)
        self._progress_label.clear()
        self._bucket_label.clear()
        self._progress_bar.setValue(0)
        due = self._due_count()
        self._start_btn.setEnabled(due > 0)
        if due > 0:
            self._idle_stack.setCurrentIndex(0)
        else:
            self._idle_stack.setCurrentIndex(1)
            self._update_done_buttons()

    def _show_session_ui(self) -> None:
        self._card_stack.setCurrentIndex(1)
        self._progress_widget.setVisible(True)
        self._grade_widget.setVisible(True)
        self._ensure_review_focus()

    def _start_session(self) -> None:
        if self._deck_id is None:
            return
        started = self._controller.start_session(
            self._deck_id,
            direction=self._direction,
            mode=self._current_mode(),
        )
        if not started:
            self._show_idle_ui()
            return
        self._stack.setCurrentIndex(0)
        self._show_session_ui()
        self._prefetch_session_tts()
        self._prefetch_session_images()
        self._render_current_card()

    def _prefetch_session_tts(self) -> None:
        cards = self._controller.session_cards()
        texts = collect_review_tts_texts(cards, direction=self._direction)
        tts_prefetch_service().prefetch_texts(texts)
        for card in cards:
            tts_prefetch_service().prefetch_card_term(card.id, direction=self._direction)

    def _prefetch_card_tts(self, card: learning.LearningCard) -> None:
        tts_prefetch_service().prefetch_texts(
            collect_review_card_tts_texts(card, direction=self._direction),
            priority=True,
        )
        tts_prefetch_service().prefetch_card_term(
            card.id, direction=self._direction, priority=True
        )

    def _start_cram(self, cards: list[learning.LearningCard]) -> None:
        if self._deck_id is None or not cards:
            return
        started = self._controller.start_cram_session(
            self._deck_id,
            cards,
            direction=self._direction,
            mode=self._current_mode(),
        )
        if not started:
            return
        self._stack.setCurrentIndex(0)
        self._show_session_ui()
        self._prefetch_session_tts()
        self._prefetch_session_images()
        self._render_current_card()

    def _start_cram_hard(self) -> None:
        if self._deck_id is None:
            return
        self._start_cram(cram_hard_cards(self._deck_id))

    def _start_cram_train(self) -> None:
        if self._deck_id is None:
            return
        self._start_cram(
            cram_train_cards(
                self._deck_id,
                self._controller.last_normal_session_card_ids,
            )
        )

    def _render_current_card(self) -> None:
        card = self._controller.current_card()
        if card is None:
            self._show_summary()
            return
        self._show_session_ui()
        self._height_sync_token += 1  # invalidate pending height syncs from prior card
        # Reserve image column when a fetch is pending so async load does not
        # rebuild the front row and clip the term label.
        self._apply_front_layout(
            has_image=self._card_expects_image(card),
            force=True,
        )
        self._term_row.setVisible(True)
        self._set_front_term(display_term(card.front))
        self._hint_label.setText(card.hint or "")
        self._hint_label.setVisible(bool(card.hint))
        self._hide_revealed_content()
        self._typing_input.clear()
        self._typing_feedback.clear()
        self._typing_input.setVisible(self._controller.mode == "typing")
        self._typing_feedback.setVisible(False)
        self._set_phonetic_text(card.phonetic or "")
        self._update_phonetic_visibility(card, revealed=self._controller.revealed)
        self._render_image(card)
        self._sync_label_heights()
        total = self._controller.stats.total
        current = min(self._controller.queue_position + 1, total)
        self._progress_label.setText(tr("learning.review_progress", current=current, total=total))
        self._progress_bar.setMaximum(max(1, total))
        self._progress_bar.setValue(self._controller.queue_position)
        buckets = self._controller.bucket_counts()
        self._bucket_label.setText(
            tr(
                "learning.bucket_counts",
                new=buckets["new"],
                learning=buckets["learning"],
                review=buckets["review"],
            )
        )
        self._hide_grades()
        self._show_answer_btn.setVisible(True)
        if self._controller.mode == "typing":
            self._typing_input.setFocus()
        self._prefetch_card_tts(card)
        self._maybe_auto_play_term(card)

    def _render_image(self, card: learning.LearningCard) -> None:
        if not is_enabled("learning.card_images"):
            self._clear_image()
            return
        path = resolve_image_path(card.image_path) if card.image_path else None
        if path is not None:
            self._show_image_path(path)
            return
        if not card.image_prompt.strip():
            self._clear_image()
            return
        # Keep the image column reserved while Pixabay fetch runs — switching
        # no-image → with-image after load was clipping the term ("Tornado").
        self._show_image_placeholder()
        self._request_card_image(card)

    def _clear_image(self) -> None:
        self._image_label.clear()
        self._image_label.clearMask()
        self._image_label.setFixedSize(_IMAGE_SIZE, _IMAGE_SIZE)
        self._image_label.setVisible(False)
        self._image_column.setVisible(False)
        self._apply_front_layout(has_image=False, force=True)

    def _show_image_placeholder(self) -> None:
        self._image_label.clear()
        self._image_label.clearMask()
        self._image_label.setFixedSize(_IMAGE_SIZE, _IMAGE_SIZE)
        self._image_label.setVisible(True)
        self._image_column.setVisible(True)
        self._apply_front_layout(has_image=True, force=True)
        self._sync_label_heights()

    def _show_image_path(self, path) -> None:
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self._clear_image()
            return
        rounded = get_rounded_pixmap(
            pixmap,
            size=_IMAGE_SIZE,
            radius=_IMAGE_RADIUS,
        )
        self._image_label.setPixmap(rounded)
        self._image_label.setFixedSize(rounded.size())
        mask = rounded.mask()
        if not mask.isNull():
            self._image_label.setMask(mask)
        else:
            self._image_label.clearMask()
        self._image_label.setVisible(True)
        self._image_column.setVisible(True)
        if self._front_has_image:
            # Already in image layout (placeholder or previous card) — only
            # refresh heights after pixmap size is applied.
            self._sync_label_heights()
        else:
            self._apply_front_layout(has_image=True, force=True)
            self._sync_label_heights()
        self._schedule_height_sync()

    def _cancel_image_fetch(self) -> None:
        if self._image_worker is not None and self._image_worker.isRunning():
            self._image_worker.requestInterruption()
            self._image_worker.wait(200)
        self._image_worker = None
        self._image_fetch_card_id = None

    def _cancel_image_prefetch(self) -> None:
        if self._image_prefetch is not None and self._image_prefetch.isRunning():
            self._image_prefetch.requestInterruption()
            self._image_prefetch.wait(200)
        self._image_prefetch = None

    def _prefetch_session_images(self) -> None:
        self._cancel_image_prefetch()
        if not is_enabled("learning.card_images") or self._deck_id is None:
            return
        current = self._controller.current_card()
        current_id = current.id if current is not None else None
        pending: list[learning.LearningCard] = []
        for card in self._controller.session_cards():
            if card.id == current_id:
                continue
            if not (card.image_prompt or "").strip():
                continue
            if card.image_path and resolve_image_path(card.image_path):
                continue
            pending.append(card)
        if not pending:
            return
        self._image_prefetch = CardImagePrefetchWorker(
            self._deck_id, pending, parent=self
        )
        # Prefetch only warms the cache — do not touch the current card UI.
        self._image_prefetch.start()

    def _request_card_image(self, card: learning.LearningCard) -> None:
        if self._deck_id is None:
            return
        if (
            self._image_worker is not None
            and self._image_worker.isRunning()
            and self._image_fetch_card_id == card.id
        ):
            return
        self._cancel_image_fetch()
        self._image_fetch_card_id = card.id
        self._image_worker = CardImageFetchWorker(
            self._deck_id,
            card.id,
            prompt=card.image_prompt,
            search_term=card.front,
            parent=self,
        )
        self._image_worker.finished_card.connect(self._on_current_image_fetched)
        self._image_worker.start()

    def _on_current_image_fetched(self, card_id: int, rel: str) -> None:
        if self._image_fetch_card_id == card_id:
            self._image_worker = None
            self._image_fetch_card_id = None
        if not rel:
            return
        current = self._controller.current_card()
        if current is None or current.id != card_id:
            return
        updated = learning.get_card(card_id)
        if updated is not None:
            self._render_image(updated)

    def _on_term_audio_ready(self, card_id: int) -> None:
        current = self._controller.current_card()
        if current is None or current.id != card_id:
            return
        updated = learning.get_card(card_id)
        if updated is None or not updated.phonetic:
            return
        self._set_phonetic_text(updated.phonetic)
        self._update_phonetic_visibility(updated, revealed=self._controller.revealed)

    def _hide_revealed_content(self) -> None:
        self._answer_block.setVisible(False)
        self._answer_label.clear()
        self._definition_label.clear()
        self._definition_label.setVisible(False)
        self._definition_row.setVisible(False)
        self._clear_example_rows()
        self._examples_host.setVisible(False)
        self._back_section.setVisible(False)
        self._example_sentences = []

    def _set_phonetic_text(self, phonetic: str) -> None:
        text = phonetic_display_text(phonetic)
        self._front_phonetic_label.setText(text)
        self._answer_phonetic_label.setText(text)

    def _card_phonetic_text(self, card: learning.LearningCard) -> str:
        return phonetic_display_text(card.phonetic or "")

    def _learning_kind(self) -> str:
        return resolve_learning_direction(self._direction)

    def _maybe_auto_play_term(self, card: learning.LearningCard) -> None:
        if not is_enabled("learning.tts_enabled"):
            return
        if not get_feature("learning.tts_auto_play").get("enabled", False):
            return
        self._play_audio()

    def _notes_highlight_term(self, card: learning.LearningCard) -> str:
        if self._learning_kind() == "en-ua":
            return display_term(card.front)
        return card.back

    def _show_revealed_content(self, card: learning.LearningCard) -> None:
        self._answer_label.setText(card.back)
        self._answer_block.setVisible(True)
        self._sync_label_heights()

        kind = self._learning_kind()
        examples = parse_context(card.context, direction=self._direction)
        term = card.back if kind == "ua-en" else display_term(card.front)
        definition = _definition_body_from_notes(card.notes or "")
        if definition:
            body = highlight_term_styled(definition, self._notes_highlight_term(card))
            self._definition_label.setText(_html_definition_block(body))
            self._definition_label.setVisible(True)
            self._definition_row.setVisible(True)
        else:
            self._definition_label.clear()
            self._definition_label.setVisible(False)
            self._definition_row.setVisible(False)

        if examples:
            self._populate_example_rows(examples, term)
            self._examples_host.setVisible(True)
        else:
            self._clear_example_rows()
            self._examples_host.setVisible(False)

        self._back_section.setVisible(True)
        self._update_phonetic_visibility(card, revealed=True)
        self._sync_label_heights()

    def _has_pronunciation_media(self, card: learning.LearningCard) -> bool:
        from quicklingo.learning.pronunciation import resolve_audio_path

        return bool(self._card_phonetic_text(card)) or resolve_audio_path(card) is not None

    def _update_phonetic_visibility(self, card, *, revealed: bool) -> None:
        enabled = is_enabled("learning.tts_enabled")
        has_media = self._has_pronunciation_media(card)
        phonetic_text = self._card_phonetic_text(card)
        if self._learning_kind() == "ua-en":
            show_answer = enabled and has_media and revealed
            self._front_phonetic_widget.setVisible(False)
            self._answer_phonetic_widget.setVisible(show_answer)
            self._answer_phonetic_label.setVisible(bool(phonetic_text))
            self._answer_play_btn.setVisible(show_answer)
        else:
            show_front = enabled and (has_media or self._tts_enabled())
            self._front_phonetic_widget.setVisible(show_front and bool(phonetic_text))
            self._answer_phonetic_widget.setVisible(False)
            self._front_phonetic_label.setVisible(bool(phonetic_text))
            self._front_play_btn.setVisible(show_front and has_media)

    def _reveal_or_flip(self) -> None:
        if self._controller.mode == "typing":
            self._submit_typing()
            return
        self._reveal_answer()

    def _reveal_answer(self) -> None:
        card = self._controller.current_card()
        if card is None:
            return
        self._controller.reveal()
        self._show_revealed_content(card)
        self._show_grades()

    def _submit_typing(self) -> None:
        if self._controller.revealed:
            return
        result = self._controller.check_typing(self._typing_input.text())
        card = self._controller.current_card()
        if card is None:
            return
        self._show_revealed_content(card)
        color = "#2e7d32" if result == AnswerResult.CORRECT else "#c62822"
        if result == AnswerResult.PARTIAL:
            color = "#ef6c00"
        self._typing_feedback.setText(tr(f"learning.typing_{result.value}"))
        self._typing_feedback.setStyleSheet(f"color: {color}; font-weight: bold;")
        self._typing_feedback.setVisible(True)
        self._show_grades()

    def _show_grades(self) -> None:
        self._show_answer_btn.setVisible(False)
        self._again_btn.setVisible(True)
        uses_fsrs = is_enabled("learning.srs_review")
        self._hard_btn.setVisible(uses_fsrs)
        self._good_btn.setVisible(True)
        self._easy_btn.setVisible(uses_fsrs)
        card = self._controller.current_card()
        if card is not None and uses_fsrs:
            try:
                previews = preview_fsrs_intervals(card)
                self._again_btn.setText(
                    self._grade_button_label(tr("learning.review_again"), previews.get(1))
                )
                self._hard_btn.setText(
                    self._grade_button_label(tr("learning.review_hard"), previews.get(2))
                )
                self._good_btn.setText(
                    self._grade_button_label(tr("learning.review_good"), previews.get(3))
                )
                self._easy_btn.setText(
                    self._grade_button_label(tr("learning.review_easy"), previews.get(4))
                )
            except (ValueError, TypeError):
                self.retranslate_ui()
        else:
            self.retranslate_ui()
        self._ensure_review_focus()

    @staticmethod
    def _grade_button_label(base: str, days: int | None) -> str:
        if days is None:
            return base
        if days < 1:
            interval = tr("learning.interval_lt_day")
        elif days == 1:
            interval = tr("learning.interval_one_day")
        else:
            interval = tr("learning.interval_days", count=days)
        return f"{base}\n· {interval}"

    def _hide_grades(self) -> None:
        self._again_btn.setVisible(False)
        self._hard_btn.setVisible(False)
        self._good_btn.setVisible(False)
        self._easy_btn.setVisible(False)

    def _submit_grade(self, rating: int) -> None:
        if not self._controller.revealed and self._controller.mode == "flip":
            return
        if self._controller.submit_grade(rating):
            self.grade_submitted.emit()
        if self._controller.session_active:
            self._render_current_card()
        else:
            self._show_summary()

    def _show_summary(self) -> None:
        self._cancel_image_fetch()
        self._cancel_image_prefetch()
        stats: SessionStats = self._controller.stats
        answered = stats.answered or stats.total
        if self._controller.is_cram:
            self._stack.setCurrentIndex(0)
            self._show_idle_ui()
            self._progress_widget.setVisible(True)
            self._progress_label.setText(
                tr("learning.cram_session_summary", answered=answered, seconds=stats.elapsed_seconds)
            )
            self._update_due_label()
            self.session_finished.emit()
            return
        self._update_due_label()
        self.session_finished.emit()
        if self._due_count() == 0:
            self._stack.setCurrentIndex(0)
            self._show_idle_ui()
            self._progress_widget.setVisible(False)
            self._grade_widget.setVisible(False)
            return
        self._summary_label.setText(
            tr(
                "learning.session_summary",
                answered=answered,
                accuracy=int(stats.accuracy * 100),
                seconds=stats.elapsed_seconds,
            )
        )
        self._stack.setCurrentIndex(1)
        self._progress_widget.setVisible(False)
        self._grade_widget.setVisible(False)

    def _play_audio(self) -> None:
        card = self._controller.current_card()
        if card is None:
            return
        if self._audio.speak_card_term(card, direction=self._direction):
            if self._card_phonetic_text(card):
                self._set_phonetic_text(card.phonetic or "")
            self._set_play_button_active(True)

    def _set_play_button_active(self, active: bool) -> None:
        _ = active
        self._term_play_btn.setText("🔊")
        self._front_play_btn.setText("🔊")
        self._answer_play_btn.setText("🔊")

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if not self._controller.session_active:
            super().keyPressEvent(event)
            return
        key = event.key()
        if key in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            # Typing field owns Enter via returnPressed; Space should type a space.
            if self._focus_in_typing_input() and not self._controller.revealed:
                super().keyPressEvent(event)
                return
            self._hotkey_space_or_enter()
            event.accept()
            return
        if key == Qt.Key.Key_P and not self._focus_in_typing_input():
            self._play_audio()
            event.accept()
            return
        grade_keys = {
            Qt.Key.Key_1: 1,
            Qt.Key.Key_2: 2,
            Qt.Key.Key_3: 3,
            Qt.Key.Key_4: 4,
            Qt.Key.Key_Keypad1: 1,
            Qt.Key.Key_Keypad2: 2,
            Qt.Key.Key_Keypad3: 3,
            Qt.Key.Key_Keypad4: 4,
        }
        if key in grade_keys and self._controller.revealed:
            self._hotkey_grade(grade_keys[key])
            event.accept()
            return
        super().keyPressEvent(event)
