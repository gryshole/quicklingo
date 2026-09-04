from __future__ import annotations

import html

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPalette, QResizeEvent, QShowEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from quicklingo.db import learning
from quicklingo.features import get_feature, is_enabled
from quicklingo.i18n import tr
from quicklingo.learning.quiz.aggregator import get_quiz_pool_stats, list_quiz_eligible_decks
from quicklingo.learning.quiz.choice_lookup import format_wrong_choice_feedback
from quicklingo.learning.quiz.quiz_feedback_content import (
    format_wrong_hint_html,
    is_choice_visible_in_feedback,
    load_quiz_feedback_content,
    should_show_quiz_feedback_enrichment,
)
from quicklingo.learning.tts.audio_service import AudioService
from quicklingo.learning.tts.prefetch import collect_question_tts_texts, collect_quiz_tts_texts
from quicklingo.learning.tts.prefetch_service import tts_prefetch_service
from quicklingo.ui.controllers.quiz_session_controller import QuizSessionController
from quicklingo.ui.widgets.quiz_deck_combo import QuizDeckComboBox
from quicklingo.ui.widgets.quiz_feedback_enrichment import QuizFeedbackEnrichmentWidget
from quicklingo.ui.widgets.quiz_generation_panel import QuizGenerationPanel
from quicklingo.ui.widgets.quiz_ui import (
    PROMPT_SPEAKER_BUTTON_STYLE,
    arrow_right_icon,
    check_icon,
    speaker_icon,
    x_icon,
)

_CARD_MAX_WIDTH = 672
_VICTORY_CARD_MAX_WIDTH = 760
_QUIZ_CARD_MAX_WIDTH = 560
_QUIZ_CARD_MIN_WIDTH = 440
_PROGRESS_BAR_HEIGHT = 6
_SPEAKER_SLOT_HEIGHT = 36

_CARD_STYLE = """
    QWidget#quizCard, QWidget#victoryCard {
        background: #ffffff;
        border: 1px solid #e8edf2;
        border-radius: 16px;
    }
    QWidget#quizActiveHost {
        background: #f1f5f9;
    }
"""
_IDLE_SETUP_STYLE = """
    QWidget#quizIdleHost {
        background: #f8fafc;
    }
    QFrame#quizSetupCard {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
    }
    QLabel#quizSetupTitle {
        font-size: 18pt;
        font-weight: 600;
        color: #0f172a;
    }
    QLabel#quizSetupStats {
        font-size: 11pt;
        color: #64748b;
    }
"""
_CHOICE_STYLE = """
    QPushButton {
        text-align: left;
        padding: 14px 20px 14px 16px;
        font-size: 13pt;
        font-weight: 600;
        color: #0f172a;
        background: #ffffff;
        border: 2px solid #e2e8f0;
        border-radius: 12px;
        min-height: 50px;
    }
    QPushButton:hover:enabled {
        border-color: #9ca3af;
        background: #f9fafb;
    }
    QPushButton:pressed:enabled {
        background: #f1f5f9;
    }
"""
_FEEDBACK_CORRECT = (
    "background: #ecfdf5; border: 2px solid #22c55e; border-radius: 12px;"
)
_FEEDBACK_WRONG = (
    "background: #fef2f2; border: 2px solid #ef4444; border-radius: 12px;"
)
_FEEDBACK_CORRECT_TEXT = "#166534"
_FEEDBACK_WRONG_TEXT = "#991b1b"
_PRIMARY_BTN = """
    QPushButton {
        background: #2563eb;
        color: #ffffff;
        border: none;
        border-radius: 8px;
        padding: 10px 24px;
        font-size: 11pt;
        font-weight: 600;
        min-width: 120px;
    }
    QPushButton:hover {
        background: #1d4ed8;
    }
    QPushButton:pressed {
        background: #1e40af;
    }
"""
_SECONDARY_BTN = """
    QPushButton {
        background: #ffffff;
        color: #475569;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 10px 24px;
        font-size: 11pt;
        min-width: 120px;
    }
    QPushButton:hover {
        background: #f8fafc;
        border-color: #cbd5e1;
    }
"""
_NEXT_BTN = """
    QPushButton {
        background: #2563eb;
        color: #ffffff;
        border: none;
        border-radius: 10px;
        padding: 12px 24px;
        font-size: 11pt;
        font-weight: 600;
        min-height: 48px;
    }
    QPushButton:hover {
        background: #1d4ed8;
    }
    QPushButton:pressed {
        background: #1e40af;
    }
"""
_WRONG_TABLE_STYLE = """
    QTableWidget#wrongAnswersTable {
        background: transparent;
        border: none;
        gridline-color: transparent;
        outline: none;
    }
    QTableWidget#wrongAnswersTable::item {
        padding: 12px 16px;
        border: none;
        border-bottom: 1px solid #e5e7eb;
    }
    QTableWidget#wrongAnswersTable QHeaderView::section {
        background-color: #f8fafc;
        color: #64748b;
        font-size: 10pt;
        font-weight: 600;
        padding: 10px 16px;
        border: none;
        border-bottom: 1px solid #e5e7eb;
    }
    QTableWidget#wrongAnswersTable QScrollBar:vertical {
        width: 8px;
        background: transparent;
        margin: 2px 0;
    }
    QTableWidget#wrongAnswersTable QScrollBar::handle:vertical {
        background: #cbd5e1;
        border-radius: 4px;
        min-height: 24px;
    }
    QTableWidget#wrongAnswersTable QScrollBar::handle:vertical:hover {
        background: #94a3b8;
    }
    QTableWidget#wrongAnswersTable QScrollBar::add-line:vertical,
    QTableWidget#wrongAnswersTable QScrollBar::sub-line:vertical {
        height: 0;
        background: none;
    }
"""

_QUESTION_STYLE = "padding: 0;"
_QUESTION_FONT_PT = 15
_QUESTION_LINE_HEIGHT = 1.55
_HINT_STYLE = "color: #94a3b8; font-size: 10pt;"
_CHOICE_ICON_SIZE = 24


def _question_label_html(text: str) -> str:
    escaped = html.escape(text)
    return (
        f'<div style="text-align: center; color: #0f172a; font-size: {_QUESTION_FONT_PT}pt; '
        f"font-weight: 600; line-height: {_QUESTION_LINE_HEIGHT}; margin: 0; padding: 0;"
        f'">{escaped}</div>'
    )


class QuizSessionWidget(QWidget):
    session_started = Signal()
    session_finished = Signal()
    results_shown = Signal()
    finish_requested = Signal()
    review_weak_requested = Signal(list, int)
    deck_selection_changed = Signal(object)
    generation_finished = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setStyleSheet(_CARD_STYLE + _IDLE_SETUP_STYLE)
        self._controller = QuizSessionController()
        self._audio = AudioService(self)
        self._current_spoken_text = ""
        self._tts_answer_revealed = False
        self._deck_ids: frozenset[int] | None = None
        self._choice_buttons: list[QPushButton] = []
        self._feedback_active = False
        self._selected_choice: str | None = None

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        self._progress_header = QWidget()
        progress_header_layout = QVBoxLayout(self._progress_header)
        progress_header_layout.setContentsMargins(0, 0, 0, 0)
        progress_header_layout.setSpacing(4)
        self._progress_label = QLabel()
        self._progress_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._progress_label.setStyleSheet(
            "color: #94a3b8; font-size: 9pt; letter-spacing: 0.02em;"
        )
        self._progress = QProgressBar()
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(_PROGRESS_BAR_HEIGHT)
        self._progress.setStyleSheet(
            "QProgressBar { border: none; background: #e2e8f0; border-radius: 3px; }"
            "QProgressBar::chunk { background: #2563eb; border-radius: 3px; }"
        )
        progress_header_layout.addWidget(self._progress_label)
        progress_header_layout.addWidget(self._progress)
        layout.addWidget(self._progress_header)

        self._stack = QStackedWidget()

        idle_page = self._build_quiz_idle_page()
        active_page = self._build_quiz_active_page()
        victory_page = self._build_quiz_victory_page()

        self._stack.addWidget(idle_page)
        self._stack.addWidget(active_page)
        self._stack.addWidget(victory_page)
        layout.addWidget(self._stack, stretch=1)

        self._show_idle()
        self._deck_ids = self._deck_combo.selected_deck_ids()
        self._generation_panel.set_deck_scope(self._deck_ids)

    def _build_quiz_idle_page(self) -> QWidget:
        idle_page = QWidget()
        idle_page.setObjectName("quizIdleHost")
        idle_layout = QVBoxLayout(idle_page)
        idle_layout.setContentsMargins(0, 0, 0, 0)
        idle_layout.addStretch(1)
        idle_center = QHBoxLayout()
        idle_center.addStretch(1)

        self._idle_stack = QWidget()
        self._idle_stack.setMinimumWidth(440)
        self._idle_stack.setMaximumWidth(_CARD_MAX_WIDTH)
        idle_stack_layout = QVBoxLayout(self._idle_stack)
        idle_stack_layout.setContentsMargins(0, 0, 0, 0)
        idle_stack_layout.setSpacing(12)

        self._generation_panel = QuizGenerationPanel()
        self._generation_panel.generation_finished.connect(self._on_generation_finished)
        idle_stack_layout.addWidget(self._generation_panel)

        self._idle_card = QFrame()
        self._idle_card.setObjectName("quizSetupCard")
        self._idle_card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        shadow = QGraphicsDropShadowEffect(self._idle_card)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(15, 23, 42, 28))
        self._idle_card.setGraphicsEffect(shadow)
        idle_card_layout = QVBoxLayout(self._idle_card)
        idle_card_layout.setContentsMargins(32, 36, 32, 36)
        idle_card_layout.setSpacing(18)

        self._idle_title = QLabel()
        self._idle_title.setObjectName("quizSetupTitle")
        self._idle_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._deck_combo = QuizDeckComboBox()
        self._deck_combo.selection_changed.connect(self._on_deck_selection_changed)

        self._idle_stats = QLabel()
        self._idle_stats.setObjectName("quizSetupStats")
        self._idle_stats.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._idle_stats.setWordWrap(True)

        self._start_btn = QPushButton()
        self._start_btn.setMinimumWidth(160)
        self._start_btn.setStyleSheet(_PRIMARY_BTN)
        self._start_btn.clicked.connect(self._start_session)
        self._refresh_btn = QPushButton()
        self._refresh_btn.setStyleSheet(_SECONDARY_BTN)
        self._refresh_btn.clicked.connect(self.refresh_preview)
        idle_btn_row = QHBoxLayout()
        idle_btn_row.setSpacing(12)
        idle_btn_row.addStretch()
        idle_btn_row.addWidget(self._refresh_btn)
        idle_btn_row.addWidget(self._start_btn)
        idle_btn_row.addStretch()

        idle_card_layout.addWidget(self._idle_title)
        idle_card_layout.addWidget(self._deck_combo)
        idle_card_layout.addWidget(self._idle_stats)
        idle_card_layout.addSpacing(4)
        idle_card_layout.addLayout(idle_btn_row)
        idle_stack_layout.addWidget(self._idle_card)
        idle_center.addWidget(self._idle_stack, stretch=0)
        idle_center.addStretch(1)
        idle_layout.addLayout(idle_center)
        idle_layout.addStretch(1)
        return idle_page

    def _build_quiz_active_page(self) -> QWidget:
        active_page = QWidget()
        active_page.setObjectName("quizActiveHost")
        active_layout = QVBoxLayout(active_page)
        active_layout.setContentsMargins(0, 0, 0, 0)
        active_layout.addStretch(1)
        active_center = QHBoxLayout()
        active_center.addStretch(1)
        self._quiz_card = QWidget()
        self._quiz_card.setObjectName("quizCard")
        self._quiz_card.setMinimumWidth(_QUIZ_CARD_MIN_WIDTH)
        self._quiz_card.setMaximumWidth(_QUIZ_CARD_MAX_WIDTH)
        self._quiz_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        card_shadow = QGraphicsDropShadowEffect(self._quiz_card)
        card_shadow.setBlurRadius(30)
        card_shadow.setOffset(0, 4)
        card_shadow.setColor(QColor(0, 0, 0, 20))
        self._quiz_card.setGraphicsEffect(card_shadow)
        quiz_card_layout = QVBoxLayout(self._quiz_card)
        self._quiz_card_layout = quiz_card_layout
        quiz_card_layout.setContentsMargins(16, 20, 16, 12)
        quiz_card_layout.setSpacing(8)

        prompt_center = QHBoxLayout()
        prompt_center.setContentsMargins(0, 0, 0, 0)
        prompt_center.addStretch()
        self._prompt_block = QWidget()
        self._prompt_block.setMaximumWidth(_QUIZ_CARD_MAX_WIDTH)
        prompt_block_layout = QVBoxLayout(self._prompt_block)
        prompt_block_layout.setContentsMargins(0, 0, 0, 0)
        prompt_block_layout.setSpacing(2)
        prompt_block_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self._prompt_play_host = QWidget()
        self._prompt_play_host.setFixedHeight(_SPEAKER_SLOT_HEIGHT)
        prompt_play_host_layout = QHBoxLayout(self._prompt_play_host)
        prompt_play_host_layout.setContentsMargins(0, 0, 0, 0)
        prompt_play_host_layout.setSpacing(0)

        prompt_play_host_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._prompt_play_btn = QPushButton()
        self._prompt_play_btn.setObjectName("quizSpeakerBtn")
        self._prompt_play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._prompt_play_btn.setStyleSheet(PROMPT_SPEAKER_BUTTON_STYLE)
        self._prompt_play_btn.setIcon(speaker_icon(size=18))
        self._prompt_play_btn.setIconSize(QSize(18, 18))
        self._prompt_play_btn.clicked.connect(self._play_prompt_audio)
        self._audio.synthesizing.connect(self._on_tts_synthesizing)
        prompt_play_host_layout.addStretch()
        prompt_play_host_layout.addWidget(self._prompt_play_btn)
        prompt_play_host_layout.addStretch()

        self._question_label = QLabel()
        self._question_label.setTextFormat(Qt.TextFormat.RichText)
        self._question_label.setWordWrap(True)
        self._question_label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self._question_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )
        question_font = QFont(self.font())
        question_font.setPointSize(_QUESTION_FONT_PT)
        question_font.setWeight(QFont.Weight.Bold)
        self._question_label.setFont(question_font)
        self._question_label.setStyleSheet(_QUESTION_STYLE)

        self._hint_label = QLabel()
        self._hint_label.setWordWrap(False)
        self._hint_label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self._hint_label.setSizePolicy(
            QSizePolicy.Policy.Minimum,
            QSizePolicy.Policy.Minimum,
        )
        self._hint_label.setStyleSheet(_HINT_STYLE)

        prompt_block_layout.addWidget(
            self._prompt_play_host,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )
        prompt_block_layout.addWidget(
            self._question_label,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )
        prompt_block_layout.addSpacing(2)
        prompt_block_layout.addWidget(
            self._hint_label,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )
        prompt_center.addWidget(self._prompt_block)
        prompt_center.addStretch()
        quiz_card_layout.addLayout(prompt_center)
        quiz_card_layout.addSpacing(20)
        self._choices_layout = QVBoxLayout()
        self._choices_layout.setSpacing(8)
        for _ in range(4):
            btn = QPushButton()
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(_CHOICE_STYLE)
            btn.clicked.connect(self._on_choice_clicked)
            self._choice_buttons.append(btn)
            self._choices_layout.addWidget(btn)
        quiz_card_layout.addLayout(self._choices_layout)

        self._feedback_host = QWidget()
        self._feedback_host.setObjectName("quizFeedbackHost")
        self._feedback_host.setAutoFillBackground(False)
        self._feedback_host.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._feedback_host.setStyleSheet("background: transparent;")
        self._feedback_host.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Minimum,
        )
        self._feedback_host.setVisible(False)
        feedback_host_layout = QVBoxLayout(self._feedback_host)
        feedback_host_layout.setContentsMargins(0, 0, 0, 0)
        feedback_host_layout.setSpacing(0)

        self._enrichment_widget = QuizFeedbackEnrichmentWidget(self._audio)
        feedback_host_layout.addWidget(self._enrichment_widget)
        quiz_card_layout.addWidget(self._feedback_host, stretch=0)
        self._next_btn = QPushButton()
        self._next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._next_btn.setStyleSheet(_NEXT_BTN)
        self._next_btn.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._next_btn.setIcon(arrow_right_icon(size=_CHOICE_ICON_SIZE))
        self._next_btn.setIconSize(QSize(_CHOICE_ICON_SIZE, _CHOICE_ICON_SIZE))
        self._next_btn.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self._next_btn.clicked.connect(self._advance_after_feedback)
        self._set_next_row_visible(False)
        quiz_card_layout.addWidget(self._next_btn)
        active_center.addWidget(self._quiz_card, stretch=1)
        active_center.addStretch(1)
        active_layout.addLayout(active_center)
        active_layout.addStretch(1)
        return active_page

    def _build_quiz_victory_page(self) -> QWidget:
        victory_page = QWidget()
        victory_layout = QVBoxLayout(victory_page)
        victory_layout.setContentsMargins(8, 4, 8, 8)
        victory_row = QHBoxLayout()
        victory_row.setContentsMargins(0, 0, 0, 0)
        self._victory_card = QWidget()
        self._victory_card.setObjectName("victoryCard")
        self._victory_card.setMaximumWidth(_VICTORY_CARD_MAX_WIDTH)
        self._victory_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        victory_card_layout = QVBoxLayout(self._victory_card)
        victory_card_layout.setContentsMargins(24, 20, 24, 20)
        victory_card_layout.setSpacing(0)

        self._victory_top = QWidget()
        self._victory_top.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        victory_top_layout = QVBoxLayout(self._victory_top)
        victory_top_layout.setContentsMargins(0, 0, 0, 0)
        victory_top_layout.setSpacing(0)
        self._victory_icon = QLabel("🏆")
        self._victory_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._victory_icon.setStyleSheet("font-size: 40pt; padding-bottom: 2px;")
        self._score_label = QLabel()
        self._score_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._score_label.setStyleSheet(
            "font-size: 20pt; font-weight: 700; color: #0f172a; padding: 2px 0 6px;"
        )
        self._wrong_title = QLabel()
        self._wrong_title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._wrong_title.setStyleSheet(
            "font-size: 11pt; font-weight: 600; color: #64748b; padding-top: 6px; padding-bottom: 12px;"
        )
        victory_top_layout.addWidget(self._victory_icon)
        victory_top_layout.addWidget(self._score_label)
        victory_top_layout.addWidget(self._wrong_title)

        self._wrong_table = QTableWidget()
        self._wrong_table.setObjectName("wrongAnswersTable")
        self._wrong_table.setColumnCount(3)
        self._wrong_table.setHorizontalHeaderLabels(
            [
                tr("learning.quiz_wrong_word"),
                tr("learning.quiz_wrong_your_choice"),
                tr("learning.quiz_wrong_correct"),
            ]
        )
        self._wrong_table.verticalHeader().setVisible(False)
        self._wrong_table.setShowGrid(False)
        self._wrong_table.setAlternatingRowColors(False)
        self._wrong_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._wrong_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._wrong_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._wrong_table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._wrong_table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._wrong_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._wrong_table.setMinimumHeight(72)
        self._wrong_table.setStyleSheet(_WRONG_TABLE_STYLE)
        header = self._wrong_table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header.setFixedHeight(42)

        self._victory_footer = QWidget()
        self._victory_footer.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        victory_btn_row = QHBoxLayout(self._victory_footer)
        victory_btn_row.setContentsMargins(0, 24, 0, 0)
        victory_btn_row.addStretch()
        self._review_weak_btn = QPushButton()
        self._review_weak_btn.setStyleSheet(_PRIMARY_BTN)
        self._review_weak_btn.clicked.connect(self._review_weak_words)
        self._review_weak_btn.setVisible(False)
        self._finish_btn = QPushButton()
        self._finish_btn.setStyleSheet(_SECONDARY_BTN)
        self._finish_btn.clicked.connect(self._finish_and_return)
        self._restart_btn = QPushButton()
        self._restart_btn.setStyleSheet(_PRIMARY_BTN)
        self._restart_btn.clicked.connect(self._show_idle)
        victory_btn_row.addWidget(self._review_weak_btn)
        victory_btn_row.addWidget(self._finish_btn)
        victory_btn_row.addWidget(self._restart_btn)
        victory_btn_row.addStretch()

        victory_card_layout.addWidget(self._victory_top)
        victory_card_layout.addWidget(self._wrong_table, stretch=1)
        victory_card_layout.addWidget(self._victory_footer)
        victory_row.addWidget(self._victory_card, stretch=1)
        victory_layout.addLayout(victory_row, stretch=1)
        return victory_page

    @property
    def generation_panel(self) -> QuizGenerationPanel:
        return self._generation_panel

    def _on_generation_finished(self) -> None:
        self._deck_combo.reload_decks()
        self._deck_ids = self._deck_combo.selected_deck_ids()
        self._generation_panel.set_deck_scope(self._deck_ids)
        self.refresh_preview()
        self.generation_finished.emit()

    def selected_deck_ids(self) -> frozenset[int] | None:
        return self._deck_ids

    def reload_decks(self) -> None:
        self._deck_combo.reload_decks()
        self._deck_ids = self._deck_combo.selected_deck_ids()
        self._generation_panel.set_deck_scope(self._deck_ids)
        self._refresh_idle()

    def _on_deck_selection_changed(self, deck_ids: object) -> None:
        if isinstance(deck_ids, frozenset) or deck_ids is None:
            self._deck_ids = deck_ids
            self._generation_panel.set_deck_scope(deck_ids)
            self._refresh_idle()
            self.deck_selection_changed.emit(deck_ids)

    def refresh_preview(self) -> None:
        """Re-count eligible words (idle or victory screen)."""
        if self._stack.currentIndex() in (0, 2):
            self._refresh_idle()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if self._stack.currentIndex() == 0:
            self._refresh_idle()
        self._apply_victory_card_max_height()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._apply_victory_card_max_height()

    def retranslate_ui(self) -> None:
        self._idle_title.setText(tr("learning.quiz_setup_title"))
        self._deck_combo.retranslate_ui()
        self._generation_panel.retranslate_ui()
        self._start_btn.setText(tr("learning.quiz_start"))
        self._refresh_btn.setText(tr("learning.quiz_refresh"))
        self._restart_btn.setText(tr("learning.quiz_restart"))
        self._finish_btn.setText(tr("learning.quiz_finish"))
        self._review_weak_btn.setText(tr("learning.quiz_review_weak"))
        self._next_btn.setText(self._plain_button_text(tr("learning.quiz_next")))
        self._next_btn.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._next_btn.setIcon(arrow_right_icon(size=_CHOICE_ICON_SIZE))
        self._next_btn.setIconSize(QSize(_CHOICE_ICON_SIZE, _CHOICE_ICON_SIZE))
        self._enrichment_widget.retranslate_ui()
        self._wrong_title.setText(tr("learning.quiz_wrong_title"))
        self._wrong_table.setHorizontalHeaderLabels(
            [
                tr("learning.quiz_wrong_word"),
                tr("learning.quiz_wrong_your_choice"),
                tr("learning.quiz_wrong_correct"),
            ]
        )
        self._refresh_idle()
        self._refresh_progress()
        if self._stack.currentIndex() == 2:
            self._show_victory()

    def _set_progress_header_visible(self, visible: bool) -> None:
        self._progress_header.setVisible(visible)

    def _refresh_idle(self) -> None:
        self._deck_combo.setEnabled(True)
        stats = get_quiz_pool_stats(deck_ids=self._deck_ids)
        ready = stats.ready_with_questions
        limit = int(get_feature("learning.quiz").get("question_count", 15))
        self._refresh_btn.setEnabled(True)
        if self._deck_ids is not None and len(self._deck_ids) == 0:
            self._idle_stats.setText(tr("learning.quiz_decks_none"))
            self._start_btn.setEnabled(False)
            return
        if stats.eligible == 0:
            if stats.total_cards > 0 and stats.skipped_no_examples > 0:
                self._idle_stats.setText(
                    tr("learning.quiz_no_words_missing_examples", missing=stats.skipped_no_examples)
                )
            else:
                self._idle_stats.setText(tr("learning.quiz_no_words"))
            self._start_btn.setEnabled(False)
        elif ready < limit:
            lines = [
                tr(
                    "learning.quiz_not_ready",
                    ready=ready,
                    needed=limit,
                    missing=stats.missing_questions,
                )
            ]
            if stats.skipped_no_examples > 0:
                lines.append(
                    tr("learning.quiz_idle_skipped_examples", missing=stats.skipped_no_examples)
                )
            self._idle_stats.setText("\n".join(lines))
            self._start_btn.setEnabled(False)
        else:
            shown = min(ready, limit)
            multi_deck = self._deck_ids is None or len(self._deck_ids) > 1
            if multi_deck:
                deck_count = (
                    len(list_quiz_eligible_decks())
                    if self._deck_ids is None
                    else len(self._deck_ids)
                )
                lines = [
                    tr(
                        "learning.quiz_idle_hint_multi",
                        count=shown,
                        ready=ready,
                        decks=deck_count,
                    )
                ]
            else:
                lines = [tr("learning.quiz_idle_hint", count=shown, available=ready)]
            if stats.missing_questions > 0:
                lines.append(
                    tr("learning.quiz_idle_partial_ready", missing=stats.missing_questions)
                )
            if stats.skipped_no_examples > 0:
                lines.append(
                    tr("learning.quiz_idle_skipped_examples", missing=stats.skipped_no_examples)
                )
            self._idle_stats.setText("\n".join(lines))
            self._start_btn.setEnabled(True)

    def _show_idle(self) -> None:
        self._controller.reset()
        self._set_next_row_visible(False)
        self._stack.setCurrentIndex(0)
        self._set_progress_header_visible(False)
        self._progress.setValue(0)
        self._progress.setMaximum(max(1, int(get_feature("learning.quiz").get("question_count", 15))))
        self._progress_label.setText("")
        self._generation_panel.set_deck_scope(self._deck_ids)
        self._refresh_idle()
        self.session_finished.emit()

    def _finish_and_return(self) -> None:
        self._show_idle()
        self.finish_requested.emit()

    def _review_weak_words(self) -> None:
        result = self._controller.result()
        card_ids = [word.card_id for word in result.wrong_words]
        if not card_ids:
            return
        card = learning.get_card(card_ids[0])
        if card is None:
            return
        self.review_weak_requested.emit(card_ids, card.deck_id)

    def _start_session(self) -> None:
        if not self._controller.start_session(self._deck_ids):
            self._refresh_idle()
            return
        total = self._controller.progress()[1]
        self._progress.setMaximum(total)
        self._set_progress_header_visible(True)
        self._generation_panel.setVisible(False)
        self._stack.setCurrentIndex(1)
        self.session_started.emit()
        self._prefetch_session_tts()
        self._show_current_question()

    def _prefetch_session_tts(self) -> None:
        texts = collect_quiz_tts_texts(self._controller.questions())
        tts_prefetch_service().prefetch_texts(texts)

    def _prefetch_question_tts(self, question) -> None:
        tts_prefetch_service().prefetch_texts(collect_question_tts_texts(question), priority=True)

    def _session_direction(self) -> str:
        words = self._controller.words_by_id()
        if not words:
            return "ua-en"
        first_word = next(iter(words.values()))
        card = learning.get_card(first_word.card_id)
        if card is None:
            return "ua-en"
        deck = learning.get_deck(card.deck_id)
        return deck.direction if deck else "ua-en"

    def _clear_feedback_state(self) -> None:
        self._feedback_active = False
        self._selected_choice = None
        self._enrichment_widget.set_feedback(None)
        self._feedback_host.setVisible(False)

    def _show_current_question(self) -> None:
        self._set_next_row_visible(False)
        self._clear_feedback_state()
        question = self._controller.current_question()
        if question is None:
            self._finish_session()
            return
        self._question_label.setText(_question_label_html(question.prompt_text))
        self._hint_label.setText(question.prompt_hint)
        self._tts_answer_revealed = False
        self._update_tts_ui(question)
        self._prefetch_question_tts(question)
        for index, btn in enumerate(self._choice_buttons):
            if index < len(question.choices):
                btn.setText(self._plain_button_text(question.choices[index]))
                btn.setVisible(True)
                btn.setEnabled(True)
                self._reset_choice_button_style(btn)
                btn.setIcon(QIcon())
                btn.setIconSize(QSize(_CHOICE_ICON_SIZE, _CHOICE_ICON_SIZE))
            else:
                btn.setVisible(False)
        self._refresh_progress()

    @staticmethod
    def _plain_button_text(text: str) -> str:
        return text.strip()

    def _set_next_row_visible(self, visible: bool) -> None:
        self._next_btn.setVisible(visible)

    def _sync_prompt_top_spacing(self, has_speaker: bool) -> None:
        top = 16 if has_speaker else 20
        self._quiz_card_layout.setContentsMargins(16, top, 16, 12)

    @staticmethod
    def _set_button_text_color(btn: QPushButton, color: QColor) -> None:
        palette = btn.palette()
        for group in (
            QPalette.ColorGroup.Active,
            QPalette.ColorGroup.Inactive,
            QPalette.ColorGroup.Disabled,
        ):
            palette.setColor(group, QPalette.ColorRole.ButtonText, color)
        btn.setPalette(palette)

    def _reset_choice_button_style(self, btn: QPushButton) -> None:
        btn.setStyleSheet(_CHOICE_STYLE)
        self._set_button_text_color(btn, QColor("#0f172a"))

    def _apply_choice_feedback_appearance(self, btn: QPushButton, *, correct: bool) -> None:
        btn.setStyleSheet(self._choice_feedback_style(correct=correct))
        text_color = QColor(_FEEDBACK_CORRECT_TEXT if correct else _FEEDBACK_WRONG_TEXT)
        self._set_button_text_color(btn, text_color)

    def _choice_feedback_style(self, *, correct: bool) -> str:
        text_color = _FEEDBACK_CORRECT_TEXT if correct else _FEEDBACK_WRONG_TEXT
        bg = _FEEDBACK_CORRECT if correct else _FEEDBACK_WRONG
        return (
            "QPushButton {"
            f"text-align: left; color: {text_color}; padding: 14px 20px 14px 16px; "
            "font-size: 13pt; font-weight: 600; min-height: 50px; "
            f"border-width: 2px; border-style: solid; {bg}"
            "}"
            "QPushButton:disabled {"
            f"color: {text_color};"
            "}"
        )

    def _finalize_choice_feedback_button(
        self,
        btn: QPushButton,
        *,
        correct_visual: bool,
        show_icon: bool,
        icon_correct: bool,
    ) -> None:
        self._apply_choice_feedback_appearance(btn, correct=correct_visual)
        btn.setEnabled(False)
        text_color = QColor(_FEEDBACK_CORRECT_TEXT if correct_visual else _FEEDBACK_WRONG_TEXT)
        self._set_button_text_color(btn, text_color)
        if show_icon:
            icon = check_icon(size=_CHOICE_ICON_SIZE) if icon_correct else x_icon(size=_CHOICE_ICON_SIZE)
            btn.setIcon(icon)
            btn.setIconSize(QSize(_CHOICE_ICON_SIZE, _CHOICE_ICON_SIZE))
        else:
            btn.setIcon(QIcon())

    def _on_choice_clicked(self) -> None:
        sender = self.sender()
        if not isinstance(sender, QPushButton) or not sender.isEnabled():
            return
        question = self._controller.current_question()
        if question is None:
            return
        choice = self._plain_button_text(sender.text())
        correct_word = question.correct_english
        correct = self._controller.submit_answer(choice)
        self._feedback_active = True
        self._selected_choice = choice
        for btn in self._choice_buttons:
            text = self._plain_button_text(btn.text())
            if not text:
                continue
            visible = is_choice_visible_in_feedback(
                text,
                "feedback",
                last_correct=correct,
                selected_choice=choice,
                correct_english=correct_word,
            )
            btn.setVisible(visible)
            if not visible:
                btn.setEnabled(False)
                continue
            is_selected = text.strip().lower() == choice.strip().lower()
            is_correct_choice = text.strip().lower() == correct_word.strip().lower()
            if is_selected:
                self._finalize_choice_feedback_button(
                    btn,
                    correct_visual=correct,
                    show_icon=True,
                    icon_correct=correct,
                )
            elif is_correct_choice:
                self._finalize_choice_feedback_button(
                    btn,
                    correct_visual=True,
                    show_icon=True,
                    icon_correct=True,
                )
        wrong_hint = ""
        if not correct:
            wrong_hint = format_wrong_choice_feedback(
                choice,
                self._session_direction(),
                correct_english=correct_word,
                question_type=question.type,
            )
        content = load_quiz_feedback_content(question, self._session_direction())
        self._enrichment_widget.set_feedback(
            content,
            wrong_hint_html=format_wrong_hint_html(wrong_hint) if wrong_hint else "",
            is_wrong=not correct,
        )
        has_feedback_body = should_show_quiz_feedback_enrichment(
            wrong_hint=wrong_hint,
            content=content,
        )
        self._feedback_host.setVisible(has_feedback_body)
        self._tts_answer_revealed = True
        self._update_tts_ui(question)
        self._prefetch_question_tts(question)
        self._set_next_row_visible(True)
        self._refresh_progress()

    def _advance_after_feedback(self) -> None:
        if self._controller.is_finished():
            self._finish_session()
        else:
            self._show_current_question()

    def _apply_victory_card_max_height(self) -> None:
        if self._stack.currentIndex() != 2:
            return
        available = max(self._stack.height() - 8, 260)
        self._victory_card.setMaximumHeight(available)

    def _finish_session(self) -> None:
        self._set_next_row_visible(False)
        self._controller.persist_session_logs()
        self._show_victory()

    def _show_victory(self) -> None:
        result = self._controller.result()
        self._set_progress_header_visible(False)
        self._progress_label.setText("")
        self._score_label.setText(tr("learning.quiz_score", score=result.score, total=result.total))
        if result.wrong_words:
            _populate_wrong_table(
                self._wrong_table,
                self._controller,
                direction=self._session_direction(),
            )
            self._wrong_title.setVisible(True)
            self._wrong_table.setVisible(True)
            self._review_weak_btn.setVisible(True)
        else:
            self._wrong_table.setRowCount(0)
            self._wrong_title.setVisible(False)
            self._wrong_table.setVisible(False)
            self._review_weak_btn.setVisible(False)
        self._stack.setCurrentIndex(2)
        self._apply_victory_card_max_height()
        self.results_shown.emit()

    def _refresh_progress(self) -> None:
        if self._stack.currentIndex() != 1:
            return
        current, total = self._controller.progress_for_display(
            in_feedback=self._feedback_active
        )
        if total <= 0:
            self._progress_label.setText("")
            return
        self._progress.setMaximum(total)
        self._progress.setValue(max(0, current - 1) if self._stack.currentIndex() == 1 else current)
        self._progress_label.setText(tr("learning.quiz_progress", current=current, total=total))

    def _update_tts_ui(self, question) -> None:
        if not is_enabled("learning.tts_enabled"):
            self._prompt_play_host.setVisible(False)
            self._sync_prompt_top_spacing(False)
            self._current_spoken_text = ""
            return
        has_tts_slot = bool(
            question.prompt_spoken_text.strip() or question.answer_spoken_text.strip()
        )
        self._prompt_play_host.setVisible(has_tts_slot)
        self._sync_prompt_top_spacing(has_tts_slot)
        if self._tts_answer_revealed:
            spoken = question.answer_spoken_text.strip()
        else:
            spoken = question.prompt_spoken_text.strip()
        show_button = bool(spoken)
        self._prompt_play_btn.setVisible(show_button)
        self._prompt_play_btn.setEnabled(show_button)
        self._current_spoken_text = spoken if show_button else ""

    def _play_prompt_audio(self) -> None:
        if self._current_spoken_text:
            self._audio.speak_sentence(self._current_spoken_text)

    def _on_tts_synthesizing(self, active: bool) -> None:
        self._prompt_play_btn.setEnabled(not active)


def _populate_wrong_table(
    table: QTableWidget,
    controller: QuizSessionController,
    *,
    direction: str,
) -> None:
    rows: list[tuple[str, str, str]] = []
    seen: set[int] = set()
    for answer in controller.answers():
        if answer.correct:
            continue
        question = controller.question_for_answer(answer)
        if question is None or question.source_card_id in seen:
            continue
        seen.add(question.source_card_id)
        word = controller.words_by_id().get(question.source_card_id)
        if word is None:
            continue
        selected_label = answer.selected
        feedback = format_wrong_choice_feedback(
            answer.selected,
            direction,
            correct_english=question.correct_english,
            question_type=question.type,
        )
        if feedback:
            selected_label = feedback
        rows.append((word.english, selected_label, question.correct_english))

    table.setRowCount(len(rows))
    table.clearContents()
    word_color = QColor("#0f172a")
    wrong_color = QColor("#dc2626")
    correct_color = QColor("#16a34a")
    for row_index, (word, selected, correct) in enumerate(rows):
        word_item = QTableWidgetItem(word)
        word_item.setForeground(word_color)
        font = word_item.font()
        font.setBold(True)
        word_item.setFont(font)
        selected_item = QTableWidgetItem(selected)
        selected_item.setForeground(wrong_color)
        correct_item = QTableWidgetItem(correct)
        correct_item.setForeground(correct_color)
        correct_font = correct_item.font()
        correct_font.setBold(True)
        correct_item.setFont(correct_font)
        table.setItem(row_index, 0, word_item)
        table.setItem(row_index, 1, selected_item)
        table.setItem(row_index, 2, correct_item)
    table.resizeRowsToContents()
