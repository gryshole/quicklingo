from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from quicklingo.db import learning
from quicklingo.db.learning import QuizCoverageStats
from quicklingo.i18n import tr
from quicklingo.learning.quiz.aggregator import list_quiz_eligible_decks
from quicklingo.learning.quiz.card_eligibility_fix import count_ineligible_cards
from quicklingo.learning.quiz.deck_selection_prefs import save_generation_deck_id
from quicklingo.learning.quiz.generation_outcome import QuizGenerationOutcome
from quicklingo.providers.registry import get_model_by_index, get_model_entries
from quicklingo.ui.qt_utils import configure_single_line_combo, reload_combo
from quicklingo.workers.ai_quiz_fix_cards_worker import AiQuizFixCardsWorker, QuizFixOutcome
from quicklingo.workers.ai_quiz_generator_worker import AiQuizGeneratorWorker

_CARD_STYLE = """
    QFrame#quizGenCard {
        background-color: #eff6ff;
        border: 1px solid #ddd6fe;
        border-radius: 12px;
    }
    QLabel#quizGenTitle {
        font-size: 13px;
        font-weight: 600;
        color: #1e293b;
    }
    QLabel#quizGenSubtitle {
        font-size: 12px;
        color: #64748b;
    }
    QComboBox {
        border: 1px solid #d1d5db;
        border-radius: 8px;
        padding: 6px 10px;
        background-color: white;
        color: #1f2937;
        min-height: 18px;
    }
    QComboBox:hover {
        border: 1px solid #3b82f6;
    }
    QComboBox::drop-down {
        border: none;
        width: 24px;
    }
"""
_GENERATE_BTN = """
    QPushButton {
        background: #2563eb;
        color: #ffffff;
        border: none;
        border-radius: 6px;
        padding: 6px 14px;
        font-size: 13px;
        font-weight: 600;
    }
    QPushButton:hover:enabled { background: #1d4ed8; }
    QPushButton:disabled { background: #94a3b8; color: #e2e8f0; }
"""
_CANCEL_BTN = """
    QPushButton {
        background: #ffffff;
        color: #475569;
        border: 1px solid #cbd5e1;
        border-radius: 6px;
        padding: 6px 12px;
        font-size: 13px;
    }
    QPushButton:hover:enabled { background: #f8fafc; }
"""
_FIX_BTN = """
    QPushButton {
        background: transparent;
        color: #b45309;
        border: none;
        padding: 0;
        font-size: 12px;
        font-weight: 600;
        text-align: left;
    }
    QPushButton:hover:enabled { color: #92400e; }
    QPushButton:disabled { color: #94a3b8; }
"""


def _generation_result_message(outcome: QuizGenerationOutcome) -> str:
    stats = outcome.stats
    if outcome.cancelled:
        return tr(
            "learning.quiz_generation_cancelled",
            ready=stats.ready,
            total=stats.eligible,
            missing=stats.missing_any,
        )
    if stats.ready >= stats.eligible:
        return tr("learning.quiz_generation_done")
    return tr(
        "learning.quiz_generation_partial",
        ready=stats.ready,
        total=stats.eligible,
        missing=stats.missing_any,
        failed=outcome.failed_questions,
    )


def _resolve_deck_id(deck_ids: frozenset[int] | None) -> int | None:
    incomplete: list[tuple[int, int, int]] = []
    for deck in list_quiz_eligible_decks():
        if deck_ids is not None and deck.id not in deck_ids:
            continue
        stats = learning.get_quiz_coverage(deck.id)
        ineligible = count_ineligible_cards(deck.id)
        if ineligible > 0:
            return deck.id
        if stats.eligible > 0 and stats.ready < stats.eligible:
            incomplete.append((stats.missing_any, deck.id, stats.eligible - stats.ready))
    if not incomplete:
        return None
    incomplete.sort(key=lambda item: (-item[0], item[1]))
    return incomplete[0][1]


class QuizGenerationPanel(QFrame):
    generation_finished = Signal()
    generation_started = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("quizGenCard")
        self.setStyleSheet(_CARD_STYLE)
        self._deck_id: int | None = None
        self._scope_deck_ids: frozenset[int] | None = None
        self._result_message: str = ""
        self._quiz_worker: AiQuizGeneratorWorker | None = None
        self._fix_worker: AiQuizFixCardsWorker | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        self._title = QLabel()
        self._title.setObjectName("quizGenTitle")
        self._title.setWordWrap(True)
        layout.addWidget(self._title)

        self._subtitle = QLabel()
        self._subtitle.setObjectName("quizGenSubtitle")
        self._subtitle.setWordWrap(True)
        layout.addWidget(self._subtitle)

        self._fix_btn = QPushButton()
        self._fix_btn.setStyleSheet(_FIX_BTN)
        self._fix_btn.clicked.connect(self._start_fix)
        self._fix_btn.setVisible(False)
        layout.addWidget(self._fix_btn)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self._model_combo = QComboBox()
        configure_single_line_combo(self._model_combo)
        self._reload_model_combo()
        self._generate_btn = QPushButton()
        self._generate_btn.setStyleSheet(_GENERATE_BTN)
        self._generate_btn.clicked.connect(self._start_generation)
        self._cancel_btn = QPushButton()
        self._cancel_btn.setStyleSheet(_CANCEL_BTN)
        self._cancel_btn.clicked.connect(self._cancel_work)
        self._cancel_btn.setVisible(False)
        actions.addWidget(self._model_combo, stretch=1)
        actions.addWidget(self._generate_btn)
        actions.addWidget(self._cancel_btn)
        layout.addLayout(actions)

        self.setVisible(False)
        self.retranslate_ui()

    def set_deck_scope(self, deck_ids: frozenset[int] | None) -> None:
        self._scope_deck_ids = deck_ids
        target = _resolve_deck_id(deck_ids)
        if target != self._deck_id:
            self._result_message = ""
        self._deck_id = target
        if self._deck_id is not None:
            save_generation_deck_id(self._deck_id)
        if not self.is_busy():
            self.refresh()

    def set_deck_id(self, deck_id: int | None) -> None:
        if deck_id is None:
            return
        if deck_id != self._deck_id:
            self._result_message = ""
        self._deck_id = deck_id
        save_generation_deck_id(deck_id)
        if not self.is_busy():
            self.refresh()

    def _reload_model_combo(self) -> None:
        current = self._model_combo.currentData() if self._model_combo.count() else None
        reload_combo(
            self._model_combo,
            [(entry.model_id, entry.display_name) for entry in get_model_entries()],
            current_data=current,
        )
        if self._model_combo.count() and self._model_combo.currentIndex() < 0:
            self._model_combo.setCurrentIndex(0)

    def refresh(self, *, keep_progress: bool = False) -> None:
        if self.is_busy():
            return

        if self._deck_id is None:
            self.setVisible(bool(self._result_message))
            if self._result_message:
                self._subtitle.setText(self._result_message)
            return

        deck = learning.get_deck(self._deck_id)
        deck_name = deck.name if deck is not None else "?"
        stats = learning.get_quiz_coverage(self._deck_id)
        ineligible = count_ineligible_cards(self._deck_id)
        needs_generation = stats.eligible > 0 and stats.ready < stats.eligible
        needs_fix = ineligible > 0

        self._fix_btn.setVisible(needs_fix)
        if needs_fix:
            self._fix_btn.setText(tr("learning.quiz_fix_ineligible", count=ineligible))
            self._fix_btn.setEnabled(True)

        if self._result_message and not keep_progress:
            self._subtitle.setText(self._result_message)
        elif needs_fix:
            self._subtitle.setText(
                tr("learning.quiz_generation_card_fix_hint", count=ineligible, deck=deck_name)
            )
        elif needs_generation:
            self._subtitle.setText(
                tr(
                    "learning.quiz_generation_card_hint",
                    missing=stats.missing_any,
                    deck=deck_name,
                )
            )
        elif self._result_message:
            self._subtitle.setText(self._result_message)
        else:
            self._subtitle.clear()

        show = needs_fix or needs_generation or bool(self._result_message)
        self.setVisible(show)
        self._generate_btn.setEnabled(show and needs_generation and not needs_fix)
        self._generate_btn.setVisible(not self._cancel_btn.isVisible())

    def retranslate_ui(self) -> None:
        self._title.setText(tr("learning.quiz_generation_card_title"))
        self._generate_btn.setText(tr("learning.quiz_generate_short"))
        self._cancel_btn.setText(tr("main.cancel"))
        self.refresh()

    def _start_generation(self) -> None:
        if self._deck_id is None or self.is_busy():
            return
        if self._model_combo.currentIndex() < 0:
            return
        model_entry = get_model_by_index(self._model_combo.currentIndex())
        self._result_message = ""
        self._quiz_worker = AiQuizGeneratorWorker(self._deck_id, model_entry=model_entry, parent=self)
        self._quiz_worker.progress.connect(self._on_progress)
        self._quiz_worker.error.connect(self._on_error)
        self._quiz_worker.finished.connect(self._on_quiz_finished)
        self._set_busy(True, tr("learning.quiz_generating"))
        self.generation_started.emit()
        self._quiz_worker.start()

    def _start_fix(self) -> None:
        if self._deck_id is None or self.is_busy():
            return
        if self._model_combo.currentIndex() < 0:
            return
        model_entry = get_model_by_index(self._model_combo.currentIndex())
        self._result_message = ""
        self._fix_worker = AiQuizFixCardsWorker(self._deck_id, model_entry=model_entry, parent=self)
        self._fix_worker.progress.connect(self._on_progress)
        self._fix_worker.error.connect(self._on_error)
        self._fix_worker.finished.connect(self._on_fix_finished)
        self._set_busy(True, tr("learning.quiz_fixing_cards"))
        self.generation_started.emit()
        self._fix_worker.start()

    def _set_busy(self, busy: bool, progress_text: str = "") -> None:
        self._generate_btn.setVisible(not busy)
        self._cancel_btn.setVisible(busy)
        self._fix_btn.setEnabled(not busy and self._fix_btn.isVisible())
        self._model_combo.setEnabled(not busy)
        if progress_text:
            self._subtitle.setText(progress_text)
        self.setVisible(True)

    def _cancel_work(self) -> None:
        if self._quiz_worker is not None:
            self._quiz_worker.cancel()
        if self._fix_worker is not None:
            self._fix_worker.cancel()

    def _on_progress(self, message: str) -> None:
        self._subtitle.setText(message)

    def _on_error(self, message: str) -> None:
        self._result_message = message
        self._cleanup_workers()
        self.refresh()
        self.generation_finished.emit()

    def _on_quiz_finished(self, outcome: object) -> None:
        if isinstance(outcome, QuizGenerationOutcome):
            parsed = outcome
        else:
            parsed = QuizGenerationOutcome(
                stats=outcome if isinstance(outcome, QuizCoverageStats) else learning.get_quiz_coverage(self._deck_id or 0),
                cancelled=False,
                failed_questions=learning.count_failed_quiz_questions_for_deck(self._deck_id or 0),
            )
        self._result_message = _generation_result_message(parsed)
        self._cleanup_workers()
        self.set_deck_scope(self._scope_deck_ids)
        self.generation_finished.emit()

    def _on_fix_finished(self, outcome: object) -> None:
        if isinstance(outcome, QuizFixOutcome):
            result = outcome.result
            cancelled = outcome.cancelled
        else:
            result = outcome
            cancelled = False
        fixed = int(getattr(result, "fixed", 0))
        total = int(getattr(result, "total", 0))
        failed = int(getattr(result, "failed", 0))
        if cancelled:
            self._result_message = tr("learning.quiz_fix_cancelled", fixed=fixed, total=total)
        elif failed > 0:
            self._result_message = tr(
                "learning.quiz_fix_partial", fixed=fixed, total=total, failed=failed
            )
        else:
            self._result_message = tr("learning.quiz_fix_done", fixed=fixed, total=total)
        self._cleanup_workers()
        self.set_deck_scope(self._scope_deck_ids)
        self.generation_finished.emit()

    def _cleanup_workers(self) -> None:
        if self._quiz_worker is not None:
            self._quiz_worker.deleteLater()
            self._quiz_worker = None
        if self._fix_worker is not None:
            self._fix_worker.deleteLater()
            self._fix_worker = None
        self._cancel_btn.setVisible(False)
        self._generate_btn.setVisible(True)
        self._model_combo.setEnabled(True)

    def is_busy(self) -> bool:
        return self._quiz_worker is not None or self._fix_worker is not None
