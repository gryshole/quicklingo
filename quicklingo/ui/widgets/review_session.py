from __future__ import annotations

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
from quicklingo.learning.cram_queue import cram_hard_cards, cram_train_cards
from quicklingo.learning.review_queue import count_due_cards
from quicklingo.ui.controllers.review_session_controller import ReviewSessionController, SessionStats

_ANSWER_STYLE = "color: #1565c0; font-size: 22pt; font-weight: bold;"
_HINT_STYLE = "color: #666; font-size: 11pt;"
_PHONETIC_STYLE = "color: #555; font-size: 12pt; font-style: italic;"
_ANSWER_PHONETIC_STYLE = _PHONETIC_STYLE + " margin-bottom: 10px;"
_CONTEXT_STYLE = "color: #333; font-size: 12pt;"
_NOTES_STYLE = (
    "color: #555; font-size: 10pt; font-style: italic; "
    "background: #f0f0f0; border-radius: 6px; padding: 8px 12px;"
)
_NOTES_MAX_WIDTH = 720
_DIVIDER_STYLE = "color: #ddd; margin-top: 12px; margin-bottom: 12px;"


class ReviewSessionWidget(QWidget):
    grade_submitted = Signal()
    session_finished = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._controller = ReviewSessionController()
        self._deck_id: int | None = None
        self._direction = "ua-en"

        self._audio = AudioService(self)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        info_row = QHBoxLayout()
        self._due_label = QLabel()
        self._streak_label = QLabel()
        info_row.addWidget(self._due_label)
        info_row.addStretch()
        info_row.addWidget(self._streak_label)
        layout.addLayout(info_row)

        controls_row = QHBoxLayout()
        self._mode_flip_btn = QPushButton()
        self._mode_flip_btn.setCheckable(True)
        self._mode_flip_btn.setChecked(True)
        self._mode_flip_btn.clicked.connect(lambda: self._set_mode("flip"))
        self._mode_typing_btn = QPushButton()
        self._mode_typing_btn.setCheckable(True)
        self._mode_typing_btn.clicked.connect(lambda: self._set_mode("typing"))
        self._start_btn = QPushButton()
        self._start_btn.clicked.connect(self._start_session)
        for btn in (self._mode_flip_btn, self._mode_typing_btn, self._start_btn):
            btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self._start_btn.setMinimumWidth(140)
        controls_row.addWidget(self._mode_flip_btn)
        controls_row.addWidget(self._mode_typing_btn)
        controls_row.addStretch()
        controls_row.addWidget(self._start_btn)
        layout.addLayout(controls_row)

        self._stack = QStackedWidget()
        self._card_frame = QFrame()
        self._card_frame.setFrameShape(QFrame.Shape.StyledPanel)
        card_outer = QVBoxLayout(self._card_frame)
        card_outer.setContentsMargins(0, 0, 0, 0)

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

        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setMaximumHeight(180)
        self._image_label.setVisible(False)
        self._term_label = QLabel()
        self._term_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = self._term_label.font()
        font.setPointSize(18)
        font.setBold(True)
        self._term_label.setFont(font)

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

        self._reveal_divider = QFrame()
        self._reveal_divider.setFrameShape(QFrame.Shape.HLine)
        self._reveal_divider.setFrameShadow(QFrame.Shadow.Plain)
        self._reveal_divider.setStyleSheet(_DIVIDER_STYLE)
        self._reveal_divider.setVisible(False)

        self._answer_block = QWidget()
        answer_layout = QVBoxLayout(self._answer_block)
        answer_layout.setContentsMargins(0, 0, 0, 0)
        answer_layout.setSpacing(4)
        self._answer_label = QLabel()
        self._answer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._answer_label.setWordWrap(True)
        self._answer_label.setStyleSheet(_ANSWER_STYLE)
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

        self._context_container = QWidget()
        self._context_layout = QVBoxLayout(self._context_container)
        self._context_layout.setContentsMargins(0, 0, 0, 0)
        self._context_layout.setSpacing(6)
        self._context_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._context_container.setVisible(False)

        self._notes_label = QLabel()
        self._notes_label.setWordWrap(False)
        self._notes_label.setTextFormat(Qt.TextFormat.RichText)
        self._notes_label.setStyleSheet(_NOTES_STYLE)
        self._notes_label.setMaximumWidth(_NOTES_MAX_WIDTH)
        self._notes_label.setSizePolicy(
            QSizePolicy.Policy.Maximum,
            QSizePolicy.Policy.Minimum,
        )
        self._notes_row = QWidget()
        notes_row_layout = QHBoxLayout(self._notes_row)
        notes_row_layout.setContentsMargins(0, 0, 0, 0)
        notes_row_layout.addStretch()
        notes_row_layout.addWidget(self._notes_label)
        notes_row_layout.addStretch()
        self._notes_row.setVisible(False)

        self._card_content: list[QWidget] = [
            self._image_label,
            self._term_label,
            self._front_phonetic_widget,
            self._hint_label,
            self._typing_input,
            self._typing_feedback,
            self._reveal_divider,
            self._answer_block,
            self._notes_row,
            self._context_container,
        ]
        for widget in self._card_content:
            card_layout.addWidget(widget)

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
        self._bucket_label = QLabel()
        progress_layout.addWidget(self._progress_label)
        progress_layout.addWidget(self._progress_bar)
        progress_layout.addWidget(self._bucket_label)
        layout.addWidget(self._progress_widget)

        self._grade_widget = QWidget()
        grade_row = QHBoxLayout(self._grade_widget)
        grade_row.setContentsMargins(0, 0, 0, 0)
        self._show_answer_btn = QPushButton()
        self._show_answer_btn.clicked.connect(self._reveal_or_flip)
        self._again_btn = QPushButton()
        self._again_btn.clicked.connect(lambda: self._submit_grade(1))
        self._hard_btn = QPushButton()
        self._hard_btn.clicked.connect(lambda: self._submit_grade(2))
        self._good_btn = QPushButton()
        self._good_btn.clicked.connect(lambda: self._submit_grade(3))
        self._easy_btn = QPushButton()
        self._easy_btn.clicked.connect(lambda: self._submit_grade(4))
        grade_row.addWidget(self._show_answer_btn)
        grade_row.addWidget(self._again_btn)
        grade_row.addWidget(self._hard_btn)
        grade_row.addWidget(self._good_btn)
        grade_row.addWidget(self._easy_btn)
        grade_row.addStretch()
        layout.addWidget(self._grade_widget)

        self.retranslate_ui()
        self._show_idle_ui()

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
        self._deck_id = deck_id
        self._direction = direction
        self._controller.reset()
        self._stack.setCurrentIndex(0)
        self._update_due_label()
        self._show_idle_ui()

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
        self._due_label.setText(tr("learning.due_today", count=self._due_count()))
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
        if not is_enabled("learning.streak"):
            self._streak_label.setText("")
            return
        from quicklingo import settings

        streak, _last = settings.get_learning_streak()
        self._streak_label.setText(tr("learning.streak_label", streak=streak))

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
        self._term_label.setText(display_term(card.front))
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
        if not is_enabled("learning.card_images") or not card.image_path:
            self._image_label.clear()
            self._image_label.setVisible(False)
            return
        path = resolve_image_path(card.image_path)
        if path is None:
            self._image_label.setVisible(False)
            return
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self._image_label.setVisible(False)
            return
        scaled = pixmap.scaled(
            320,
            180,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._image_label.setPixmap(scaled)
        self._image_label.setVisible(True)

    def _hide_revealed_content(self) -> None:
        self._reveal_divider.setVisible(False)
        self._answer_block.setVisible(False)
        self._answer_label.clear()
        self._clear_context_examples()
        self._context_container.setVisible(False)
        self._notes_label.clear()
        self._notes_row.setVisible(False)

    def _format_notes(self, notes: str) -> str:
        return notes.strip()

    def _set_phonetic_text(self, phonetic: str) -> None:
        text = phonetic_display_text(phonetic)
        self._front_phonetic_label.setText(text)
        self._answer_phonetic_label.setText(text)

    def _card_phonetic_text(self, card: learning.LearningCard) -> str:
        return phonetic_display_text(card.phonetic or "")

    def _learning_kind(self) -> str:
        return resolve_learning_direction(self._direction)

    def _clear_context_examples(self) -> None:
        while self._context_layout.count():
            item = self._context_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _populate_context_examples(self, card: learning.LearningCard) -> None:
        self._clear_context_examples()
        kind = self._learning_kind()
        examples = parse_context(card.context, direction=self._direction)
        term = card.back if kind == "ua-en" else display_term(card.front)
        tts_on = is_enabled("learning.tts_enabled")
        for sentence in examples:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(6)
            label = QLabel()
            label.setWordWrap(True)
            label.setTextFormat(Qt.TextFormat.RichText)
            label.setStyleSheet(_CONTEXT_STYLE)
            label.setText(
                f'<div style="background:#f0f0f0;border-radius:8px;padding:8px 12px;">'
                f"{highlight_term_in_context(sentence, term)}"
                "</div>"
            )
            row_layout.addWidget(label, stretch=1)
            if tts_on:
                play_btn = QPushButton("▶")
                play_btn.setFixedSize(28, 28)
                play_btn.setToolTip(tr("learning.tts_play_example"))
                play_btn.clicked.connect(
                    lambda _checked=False, text=sentence: self._audio.speak_sentence(text)
                )
                row_layout.addWidget(play_btn, alignment=Qt.AlignmentFlag.AlignTop)
            self._context_layout.addWidget(row)

    def _maybe_auto_play_term(self, card: learning.LearningCard) -> None:
        if not is_enabled("learning.tts_enabled"):
            return
        if not get_feature("learning.tts_auto_play").get("enabled", False):
            return
        self._play_audio()

    def _format_notes_html(self, notes: str, highlight: str) -> str:
        plain = self._format_notes(notes)
        if not plain:
            return ""
        body = highlight_term_styled(plain, highlight)
        return f'<div align="center" style="white-space:nowrap;">{body}</div>'

    def _notes_highlight_term(self, card: learning.LearningCard) -> str:
        if self._learning_kind() == "en-ua":
            return display_term(card.front)
        return card.back

    def _show_revealed_content(self, card: learning.LearningCard) -> None:
        self._reveal_divider.setVisible(True)
        self._answer_label.setText(card.back)
        self._answer_block.setVisible(True)
        if card.notes:
            self._notes_label.setText(
                self._format_notes_html(card.notes, self._notes_highlight_term(card))
            )
            self._notes_row.setVisible(True)
        if card.context:
            self._populate_context_examples(card)
            self._context_container.setVisible(True)
        self._update_phonetic_visibility(card, revealed=True)

    def _has_pronunciation_media(self, card: learning.LearningCard) -> bool:
        from quicklingo.learning.pronunciation import resolve_audio_path

        return bool(self._card_phonetic_text(card)) or resolve_audio_path(card) is not None

    def _update_phonetic_visibility(self, card, *, revealed: bool) -> None:
        enabled = is_enabled("learning.card_pronunciation")
        has_media = self._has_pronunciation_media(card)
        phonetic_text = self._card_phonetic_text(card)
        if self._learning_kind() == "ua-en":
            show_answer = enabled and has_media and revealed
            self._front_phonetic_widget.setVisible(False)
            self._answer_phonetic_widget.setVisible(show_answer)
            self._answer_phonetic_label.setVisible(bool(phonetic_text))
            self._answer_play_btn.setVisible(show_answer)
        else:
            show_front = enabled and has_media
            self._front_phonetic_widget.setVisible(show_front)
            self._answer_phonetic_widget.setVisible(False)
            self._front_phonetic_label.setVisible(bool(phonetic_text))
            self._front_play_btn.setVisible(show_front)

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
