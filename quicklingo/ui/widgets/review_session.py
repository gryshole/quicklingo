from __future__ import annotations

import html

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent, QPixmap
from PySide6.QtWidgets import (
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
from quicklingo.learning.image_resolver import resolve_image_path
from quicklingo.learning.tts.audio_service import AudioService
from quicklingo.learning.tts.prefetch import collect_review_card_tts_texts, collect_review_tts_texts
from quicklingo.learning.tts.prefetch_service import tts_prefetch_service
from quicklingo.workers.card_image_worker import CardImageFetchWorker
from quicklingo.learning.cram_queue import cram_hard_cards, cram_train_cards
from quicklingo.learning.fsrs_review import preview_fsrs_intervals
from quicklingo.learning.review_queue import count_due_cards
from quicklingo.ui.controllers.review_session_controller import ReviewSessionController, SessionStats

_HINT_STYLE = "color: #64748b; font-size: 11pt; margin-top: 4px;"
_PHONETIC_STYLE = "color: #64748b; font-size: 12pt; font-style: italic;"
_ANSWER_PHONETIC_STYLE = _PHONETIC_STYLE + " margin-bottom: 10px;"

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


def _html_speaker_link(target: str) -> str:
    return (
        f'<a href="qlspeak:{target}" '
        'style="text-decoration:none;color:#64748b;font-size:16pt;'
        'line-height:1;">&#128266;</a>'
    )


def _html_full_width(inner: str, *, align: str = "left", top_padding: str = "0") -> str:
    return (
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" '
        'style="margin:0;border:none;">'
        f'<tr><td align="{align}" style="text-align:{align};padding-top:{top_padding};">'
        f"{inner}</td></tr></table>"
    )


def _html_center_block(inner: str) -> str:
    return _html_full_width(inner, align="center")


def _html_front_term(text: str, *, tts_enabled: bool) -> str:
    escaped = html.escape(text)
    speaker = f" {_html_speaker_link('term')}" if tts_enabled else ""
    inner = (
        f'<span style="font-size:24pt;font-weight:bold;color:#1e293b;">{escaped}</span>'
        f"{speaker}"
    )
    return _html_center_block(
        f'<div style="padding:8px 12px 4px 12px;">{inner}</div>'
    )


def _html_back_term(text: str) -> str:
    escaped = html.escape(text)
    inner = (
        f'<span style="font-size:20pt;font-weight:bold;color:#2563eb;">{escaped}</span>'
    )
    return _html_center_block(
        f'<div style="padding:12px 12px 4px 12px;">{inner}</div>'
    )


def _html_definition_block(body_html: str) -> str:
    inner = (
        '<div style="background-color:#f8fafc;border:1px solid #e2e8f0;'
        'border-radius:8px;padding:12px 14px;text-align:left;margin-bottom:25px;">'
        '<span style="color:#64748b;font-size:13pt;font-weight:600;">'
        "Definition: </span>"
        f'<span style="color:#64748b;font-size:13pt;font-style:italic;line-height:1.6;">'
        f"{body_html}</span>"
        "</div>"
    )
    return _html_full_width(inner, align="left")


def _html_example_item(
    highlighted_html: str,
    *,
    index: int,
    tts_enabled: bool,
    is_first: bool,
    is_last: bool,
) -> str:
    margin_top = "25px" if is_first else "0"
    margin_bottom = "0" if is_last else "15px"
    audio_cell = (
        f'<td valign="middle" align="right" width="30">'
        f"{_html_speaker_link(f'example/{index}')}</td>"
        if tts_enabled
        else '<td valign="middle" align="right" width="30"></td>'
    )
    return (
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="margin-top:{margin_top};margin-bottom:{margin_bottom};border:none;">'
        "<tr>"
        '<td width="4" style="background-color:#cbd5e1;">&nbsp;</td>'
        '<td width="12">&nbsp;</td>'
        f'<td valign="middle" style="text-align:left;font-size:14pt;color:#334155;'
        f'line-height:1.6;">{highlighted_html}</td>'
        f"{audio_cell}"
        "</tr></table>"
    )


def _build_revealed_details_html(
    *,
    notes: str,
    examples: list[str],
    term: str,
    highlight: str,
    tts_enabled: bool,
) -> str:
    parts: list[str] = []
    plain = notes.strip()
    if plain.lower().startswith("definition:"):
        plain = plain.split(":", 1)[1].strip()
    has_definition = False
    if plain:
        body = highlight_term_styled(plain, highlight)
        parts.append(_html_definition_block(body))
        has_definition = True
    if examples:
        for index, sentence in enumerate(examples):
            highlighted = highlight_term_in_context(sentence, term)
            parts.append(
                _html_example_item(
                    highlighted,
                    index=index,
                    tts_enabled=tts_enabled,
                    is_first=index == 0 and has_definition,
                    is_last=index == len(examples) - 1,
                )
            )
    if not parts:
        return ""
    return _html_full_width("".join(parts), align="left", top_padding="24px")


class ReviewSessionWidget(QWidget):
    grade_submitted = Signal()
    session_finished = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("ReviewSessionWidget")
        self.setStyleSheet(_REVIEW_STYLE)
        self._controller = ReviewSessionController()
        self._deck_id: int | None = None
        self._direction = "ua-en"
        self._example_sentences: list[str] = []
        self._image_worker: CardImageFetchWorker | None = None
        self._image_fetch_card_id: int | None = None

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
        card_outer = QVBoxLayout(self._card_frame)
        card_outer.setContentsMargins(20, 20, 20, 20)

        self._card_stack = QStackedWidget()

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

        active_page = QWidget()
        card_layout = QVBoxLayout(active_page)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        card_layout.setSpacing(14)

        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setMaximumHeight(180)
        self._image_label.setVisible(False)
        self._term_label = QLabel()
        self._term_label.setAlignment(
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop
        )
        self._term_label.setTextFormat(Qt.TextFormat.RichText)
        self._term_label.setWordWrap(True)
        self._term_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        self._configure_rich_label_links(self._term_label)

        self._front_phonetic_widget = QWidget()
        front_phonetic_layout = QHBoxLayout(self._front_phonetic_widget)
        front_phonetic_layout.setContentsMargins(0, 0, 0, 0)
        self._front_phonetic_label = QLabel()
        self._front_phonetic_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._front_phonetic_label.setStyleSheet(_PHONETIC_STYLE)
        self._front_play_btn = QPushButton("▶")
        self._front_play_btn.setFixedSize(28, 28)
        self._front_play_btn.clicked.connect(self._play_audio)
        front_phonetic_layout.addStretch()
        front_phonetic_layout.addWidget(self._front_phonetic_label)
        front_phonetic_layout.addWidget(self._front_play_btn, alignment=Qt.AlignmentFlag.AlignVCenter)
        front_phonetic_layout.addStretch()
        front_phonetic_layout.setAlignment(
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
        )
        self._front_phonetic_widget.setVisible(False)

        self._hint_label = QLabel()
        self._hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint_label.setWordWrap(True)
        self._hint_label.setStyleSheet(_HINT_STYLE)

        self._typing_input = QLineEdit()
        self._typing_input.returnPressed.connect(self._submit_typing)
        self._typing_feedback = QLabel()
        self._typing_feedback.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._answer_block = QWidget()
        answer_layout = QVBoxLayout(self._answer_block)
        answer_layout.setContentsMargins(0, 8, 0, 0)
        answer_layout.setSpacing(8)
        self._answer_label = QLabel()
        self._answer_label.setAlignment(
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop
        )
        self._answer_label.setWordWrap(True)
        self._answer_label.setTextFormat(Qt.TextFormat.RichText)
        self._answer_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        self._answer_phonetic_widget = QWidget()
        answer_phonetic_layout = QHBoxLayout(self._answer_phonetic_widget)
        answer_phonetic_layout.setContentsMargins(0, 0, 0, 0)
        self._answer_phonetic_label = QLabel()
        self._answer_phonetic_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._answer_phonetic_label.setStyleSheet(_ANSWER_PHONETIC_STYLE)
        self._answer_play_btn = QPushButton("▶")
        self._answer_play_btn.setFixedSize(28, 28)
        self._answer_play_btn.clicked.connect(self._play_audio)
        answer_phonetic_layout.addStretch()
        answer_phonetic_layout.addWidget(self._answer_phonetic_label)
        answer_phonetic_layout.addWidget(self._answer_play_btn, alignment=Qt.AlignmentFlag.AlignVCenter)
        answer_phonetic_layout.addStretch()
        answer_phonetic_layout.setAlignment(
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
        )
        answer_layout.addWidget(self._answer_label)
        answer_layout.addWidget(self._answer_phonetic_widget)
        self._answer_block.setVisible(False)

        self._details_label = QLabel()
        self._details_label.setWordWrap(True)
        self._details_label.setTextFormat(Qt.TextFormat.RichText)
        self._details_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        self._details_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        self._details_label.setVisible(False)
        self._configure_rich_label_links(self._details_label)

        self._card_content: list[QWidget] = [
            self._image_label,
            self._term_label,
            self._front_phonetic_widget,
            self._hint_label,
            self._typing_input,
            self._typing_feedback,
            self._answer_block,
            self._details_label,
        ]
        for widget in self._card_content:
            card_layout.addWidget(widget, alignment=Qt.AlignmentFlag.AlignTop)

        self._card_stack.addWidget(idle_page)
        self._card_stack.addWidget(active_page)
        card_outer.addWidget(self._card_stack)

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

        self.retranslate_ui()
        self._show_idle_ui()

    def _configure_rich_label_links(self, label: QLabel) -> None:
        label.setOpenExternalLinks(False)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse)
        label.linkActivated.connect(self._on_review_link)

    def _tts_enabled(self) -> bool:
        return is_enabled("learning.tts_enabled")

    def _on_review_link(self, url: str) -> None:
        if url == "qlspeak:term":
            self._play_audio()
            return
        prefix = "qlspeak:example/"
        if url.startswith(prefix):
            try:
                index = int(url[len(prefix) :])
                self._play_example_sentence(self._example_sentences[index])
            except (ValueError, IndexError):
                return

    def _play_example_sentence(self, sentence: str) -> None:
        if not self._tts_enabled():
            return
        self._audio.speak_sentence(sentence)
        self._set_play_button_active(True)

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
        self._deck_id = deck_id
        self._direction = direction
        self._controller.reset()
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
        self._term_label.setVisible(True)
        self._term_label.setText(
            _html_front_term(
                display_term(card.front),
                tts_enabled=self._tts_enabled(),
            )
        )
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
        self._clear_image()
        self._request_card_image(card)

    def _clear_image(self) -> None:
        self._image_label.clear()
        self._image_label.setVisible(False)

    def _show_image_path(self, path) -> None:
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self._clear_image()
            return
        scaled = pixmap.scaled(
            320,
            180,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._image_label.setPixmap(scaled)
        self._image_label.setVisible(True)

    def _cancel_image_fetch(self) -> None:
        if self._image_worker is not None and self._image_worker.isRunning():
            self._image_worker.requestInterruption()
            self._image_worker.wait(200)
        self._image_worker = None
        self._image_fetch_card_id = None

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
        self._image_worker.finished_card.connect(self._on_image_fetched)
        self._image_worker.start()

    def _on_image_fetched(self, card_id: int, rel: str) -> None:
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
        self._details_label.clear()
        self._details_label.setVisible(False)
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

    def _revealed_details_html(self, card: learning.LearningCard) -> str:
        kind = self._learning_kind()
        examples = parse_context(card.context, direction=self._direction)
        self._example_sentences = list(examples)
        term = card.back if kind == "ua-en" else display_term(card.front)
        return _build_revealed_details_html(
            notes=card.notes or "",
            examples=examples,
            term=term,
            highlight=self._notes_highlight_term(card),
            tts_enabled=self._tts_enabled(),
        )

    def _show_revealed_content(self, card: learning.LearningCard) -> None:
        self._answer_label.setText(_html_back_term(card.back))
        self._answer_block.setVisible(True)
        details_html = self._revealed_details_html(card)
        if details_html:
            self._details_label.setText(details_html)
            self._details_label.setVisible(True)
        self._update_phonetic_visibility(card, revealed=True)

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
        icon = "🔊" if active and self._audio.is_speaking() else "▶"
        self._front_play_btn.setText(icon)
        self._answer_play_btn.setText(icon)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if not self._controller.session_active:
            super().keyPressEvent(event)
            return
        key = event.key()
        if key == Qt.Key.Key_Space and self._controller.mode == "flip":
            if not self._controller.revealed:
                self._reveal_answer()
            event.accept()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self._controller.mode == "typing" and not self._controller.revealed:
                self._submit_typing()
                event.accept()
                return
        if key == Qt.Key.Key_P:
            self._play_audio()
            event.accept()
            return
        if self._controller.revealed:
            if key == Qt.Key.Key_1:
                self._submit_grade(1)
                event.accept()
                return
            if key == Qt.Key.Key_2 and is_enabled("learning.srs_review"):
                self._submit_grade(2)
                event.accept()
                return
            if key == Qt.Key.Key_3:
                self._submit_grade(3)
                event.accept()
                return
            if key == Qt.Key.Key_4 and is_enabled("learning.srs_review"):
                self._submit_grade(4)
                event.accept()
                return
        super().keyPressEvent(event)
