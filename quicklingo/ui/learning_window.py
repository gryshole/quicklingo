from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent, QShowEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QHeaderView,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from quicklingo import settings
from quicklingo.config.loader import get_direction_label, get_directions, resolve_learning_direction
from quicklingo.db import history, learning
from quicklingo.features import get_feature, is_enabled
from quicklingo.i18n import tr
from quicklingo.learning.anki_export import export_anki_apkg, export_anki_csv
from quicklingo.learning.card_display import parse_context, serialize_context
from quicklingo.learning.corpus_analysis import select_candidates
from quicklingo.learning.corpus_tags import UNTAGGED_SENTINEL
from quicklingo.learning.difficult_words import compute_difficult_words
from quicklingo.learning.review_queue import card_bucket, count_due_cards
from quicklingo.providers.registry import get_model_by_index, get_model_entries
from quicklingo.ui.dialogs.ai_deck_generator_dialog import AiDeckGeneratorDialog
from quicklingo.ui.dialogs.learning_onboarding_dialog import LearningOnboardingDialog
from quicklingo.ui.controllers.update_controller import UpdateController
from quicklingo.ui.qt_utils import configure_single_line_combo, open_help, reload_combo
from quicklingo.ui.settings_dialog import SettingsDialog
from quicklingo.ui.widgets.learning_empty_state import LearningEmptyStateWidget
from quicklingo.ui.widgets.learning_progress import LearningProgressWidget
from quicklingo.ui.widgets.quiz_session import QuizSessionWidget
from quicklingo.ui.widgets.review_session import ReviewSessionWidget
from quicklingo.ui.window_state import (
    bind_table_columns_persistence,
    restore_table_columns,
    restore_window_geometry,
    save_table_columns,
    save_window_geometry,
)
from quicklingo.workers.card_media_worker import CardMediaWorker
from quicklingo.workers.corpus_analysis_worker import CorpusAnalysisWorker


_TAB_CREATE_DECK = 0
_TAB_CARDS = 1
_TAB_REVIEW = 2
_TAB_QUIZ = 3
_TAB_STATS = 4

_LEARNING_CARDS_TABLE_WIDTHS = [120, 120, 80, 120, 72, 88, 72, 56, 52]
_LEARNING_CARDS_PRIORITY_WIDTH = 52

_CARDS_TAB_STYLE = """
CardsTabWidget {
    background-color: transparent;
}
CardsTabWidget QLabel#cardsDeckLabel {
    color: #64748b;
    font-size: 13px;
    font-weight: 500;
}
CardsTabWidget QComboBox#cardsDeckCombo {
    min-height: 32px;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    padding: 4px 10px;
    background-color: #ffffff;
    color: #1e293b;
    font-size: 13px;
}
CardsTabWidget QComboBox#cardsDeckCombo:hover {
    border-color: #94a3b8;
}
CardsTabWidget QComboBox#cardsDeckCombo:focus {
    border-color: #3b82f6;
}
CardsTabWidget QComboBox#cardsDeckCombo::drop-down {
    border: none;
    width: 24px;
}
QPushButton#btnPrimary {
    background-color: #3b82f6;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 6px 16px;
    font-size: 13px;
    font-weight: 600;
    min-height: 32px;
}
QPushButton#btnPrimary:hover:enabled {
    background-color: #2563eb;
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
    padding: 6px 14px;
    font-size: 13px;
    min-height: 32px;
}
QPushButton#btnSecondary:hover:enabled {
    background-color: #f8fafc;
    border-color: #94a3b8;
}
QPushButton#btnDanger {
    background-color: #ffffff;
    color: #64748b;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    padding: 6px 14px;
    font-size: 13px;
    min-height: 32px;
}
QPushButton#btnDanger:hover:enabled {
    background-color: #fef2f2;
    border-color: #ef4444;
    color: #ef4444;
}
QFrame#cardsTableCard {
    background-color: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
}
QFrame#cardsTableCard QTableWidget {
    background-color: #ffffff;
    border: none;
    outline: none;
    gridline-color: transparent;
    selection-background-color: #eff6ff;
    selection-color: #1e293b;
}
QFrame#cardsTableCard QTableWidget::item {
    padding: 6px 8px;
    border: none;
    border-bottom: 1px solid #f1f5f9;
    color: #334155;
}
QFrame#cardsTableCard QTableWidget::item:selected {
    background-color: #eff6ff;
    color: #1e293b;
}
QFrame#cardsTableCard QTableWidget::item:focus {
    outline: none;
    border: none;
    background-color: #eff6ff;
}
QFrame#cardsTableCard QHeaderView::section {
    background-color: #f8fafc;
    color: #64748b;
    font-size: 11px;
    font-weight: 600;
    padding: 10px 8px;
    border: none;
    border-bottom: 1px solid #e5e7eb;
    border-right: 1px solid #f1f5f9;
}
QFrame#cardsTableCard QHeaderView::section:last {
    border-right: none;
}
"""


class _CardEditDialog(QDialog):
    def __init__(self, card: learning.LearningCard, *, direction: str = "ua-en", parent=None) -> None:
        super().__init__(parent)
        self._direction = direction
        self._learning_kind = resolve_learning_direction(direction)
        self.setWindowTitle(tr("learning.edit_card_title"))
        layout = QFormLayout(self)
        self._front = QLineEdit(card.front)
        self._back = QLineEdit(card.back)
        if self._learning_kind == "ua-en" or self._learning_kind == "en-ua":
            examples = parse_context(card.context, direction=direction)
            self._context = QPlainTextEdit("\n".join(examples))
            self._context.setMaximumHeight(90)
            self._context.setPlaceholderText(tr("learning.card_context_placeholder"))
        else:
            self._context = QLineEdit(card.context)
        self._hint = QLineEdit(card.hint)
        self._notes = QTextEdit(card.notes)
        self._notes.setMaximumHeight(80)
        layout.addRow(tr("learning.card_front"), self._front)
        layout.addRow(tr("learning.card_back"), self._back)
        layout.addRow(tr("learning.card_context"), self._context)
        layout.addRow(tr("learning.card_hint"), self._hint)
        layout.addRow(tr("learning.card_notes"), self._notes)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def values(self) -> dict[str, str]:
        if self._learning_kind in ("ua-en", "en-ua"):
            lines = [
                line.strip()
                for line in self._context.toPlainText().splitlines()
                if line.strip()
            ]
            context = serialize_context(lines, direction=self._direction)
        else:
            context = self._context.text().strip()
        return {
            "front": self._front.text().strip(),
            "back": self._back.text().strip(),
            "context": context,
            "hint": self._hint.text().strip(),
            "notes": self._notes.toPlainText().strip(),
        }


class LearningWindow(QMainWindow):
    closed = Signal()

    def __init__(self, parent=None, *, standalone: bool = False) -> None:
        super().__init__(parent)
        self._standalone = standalone
        self._updates: UpdateController | None = None
        self._settings_action = None
        self._tools_menu = None
        self._help_menu = None
        self._help_about_action = None
        self._help_check_updates_action = None
        self._help_onboarding_action = None
        self._help_learning_action = None
        self._quit_action = None
        restore_window_geometry(self, "learning", default_width=860, default_height=640)
        self._worker: CorpusAnalysisWorker | None = None
        self._media_worker: CardMediaWorker | None = None
        self._current_deck_id: int | None = None
        self._pending_nav: dict | None = None

        self._tabs = QTabWidget()

        self._analyze_tab = self._build_analyze_tab()
        self._cards_tab = self._build_cards_tab()
        self._review_tab = self._build_review_tab()
        self._quiz_tab = self._build_quiz_tab()
        self._progress_tab = self._build_progress_tab()

        self._tabs.addTab(self._analyze_tab, "")
        self._tabs.addTab(self._cards_tab, "")
        self._tabs.addTab(self._review_tab, "")
        self._tabs.addTab(self._quiz_tab, "")
        self._tabs.addTab(self._progress_tab, "")
        self._tabs.currentChanged.connect(self._on_tab_changed)

        self._review_session.session_finished.connect(self._quiz_session.refresh_preview)
        self._review_session.session_finished.connect(self._progress_widget.refresh)
        self._review_session.session_finished.connect(self._refresh_deck_combo_due_counts)
        self._quiz_session.session_finished.connect(self._progress_widget.refresh)
        self._quiz_session.results_shown.connect(self._progress_widget.refresh)
        self._quiz_session.review_weak_requested.connect(self._on_quiz_review_weak)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._tabs)
        self.setCentralWidget(central)

        if standalone:
            self._build_standalone_menu()
            self._updates = UpdateController(self)
        else:
            self._build_embedded_menu()

        restore_table_columns(
            self._cards_table,
            "learning",
            "cards",
            default_widths=_LEARNING_CARDS_TABLE_WIDTHS,
        )
        self._configure_cards_table_columns()
        bind_table_columns_persistence(self._cards_table, "learning", "cards")
        self.retranslate_ui()
        self._reload_tags()
        self._reload_decks()

    def _build_help_menu(self, menu_bar) -> None:
        self._help_menu = menu_bar.addMenu("")
        self._help_onboarding_action = self._help_menu.addAction("")
        self._help_onboarding_action.triggered.connect(self._show_onboarding_guide)
        self._help_learning_action = self._help_menu.addAction("")
        self._help_learning_action.triggered.connect(lambda: self._open_help_topic("learning"))

    def _build_embedded_menu(self) -> None:
        menu_bar = self.menuBar()
        self._build_help_menu(menu_bar)

    def _build_standalone_menu(self) -> None:
        menu_bar = self.menuBar()
        self._tools_menu = menu_bar.addMenu("")
        self._settings_action = self._tools_menu.addAction("")
        self._settings_action.triggered.connect(self._open_settings)

        self._help_menu = menu_bar.addMenu("")
        self._help_about_action = self._help_menu.addAction("")
        self._help_about_action.triggered.connect(lambda: self._open_help_topic("about"))
        self._help_check_updates_action = self._help_menu.addAction("")
        self._help_check_updates_action.triggered.connect(self._check_for_updates)
        self._help_menu.addSeparator()
        self._help_onboarding_action = self._help_menu.addAction("")
        self._help_onboarding_action.triggered.connect(self._show_onboarding_guide)
        self._help_learning_action = self._help_menu.addAction("")
        self._help_learning_action.triggered.connect(lambda: self._open_help_topic("learning"))

        self._quit_action = menu_bar.addAction("")
        self._quit_action.triggered.connect(self.close)

    def _show_onboarding_guide(self) -> None:
        LearningOnboardingDialog.show_guide(self, standalone=self._standalone)

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self)
        dialog.exec()
        self._reload_model_combo()
        self._reload_decks()
        self.retranslate_ui()

    def _open_help_topic(self, topic: str) -> None:
        open_help(topic, self)

    def _check_for_updates(self) -> None:
        if self._updates is not None:
            self._updates.check_for_updates()

    def _build_analyze_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        self._analyze_empty = LearningEmptyStateWidget()
        self._analyze_empty.action_requested.connect(self._on_analyze_empty_action)
        layout.addWidget(self._analyze_empty)

        self._analyze_form_host = QWidget()
        form_layout = QVBoxLayout(self._analyze_form_host)
        form_layout.setContentsMargins(0, 0, 0, 0)

        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        self._tag_combo = QComboBox()
        configure_single_line_combo(self._tag_combo)
        self._direction_combo = QComboBox()
        seen_kinds: set[str] = set()
        for direction in get_directions():
            kind = resolve_learning_direction(direction.id)
            if kind in seen_kinds:
                continue
            seen_kinds.add(kind)
            if kind == "ua-en":
                label = tr("learning.direction_learn_english")
            elif kind == "en-ua":
                label = tr("learning.direction_from_content")
            else:
                label = direction.label
            self._direction_combo.addItem(label, kind)
        default_index = 0
        best_count = -1
        for index in range(self._direction_combo.count()):
            kind = self._direction_combo.itemData(index)
            count = history.count_corpus_records(direction=kind, learning_kind=True)
            if count > best_count:
                best_count = count
                default_index = index
        if self._direction_combo.count():
            self._direction_combo.setCurrentIndex(default_index)
        self._direction_combo.currentIndexChanged.connect(self._reload_tags)
        self._starred_only = QCheckBox()
        self._model_combo = QComboBox()
        configure_single_line_combo(self._model_combo)
        self._reload_model_combo()
        self._tag_label = QLabel()
        self._direction_label = QLabel()
        self._model_label = QLabel()
        form.addRow(self._tag_label, self._tag_combo)
        form.addRow(self._direction_label, self._direction_combo)
        form.addRow(self._model_label, self._model_combo)
        form.addRow("", self._starred_only)
        form_layout.addLayout(form)

        btn_row = QHBoxLayout()
        self._preview_btn = QPushButton()
        self._preview_btn.clicked.connect(self._preview_local)
        self._analyze_btn = QPushButton()
        self._analyze_btn.setObjectName("btnPrimary")
        self._analyze_btn.clicked.connect(self._run_analysis)
        self._cancel_btn = QPushButton()
        self._cancel_btn.clicked.connect(self._cancel_analysis)
        self._cancel_btn.setVisible(False)
        btn_row.addWidget(self._preview_btn)
        btn_row.addWidget(self._analyze_btn)
        btn_row.addWidget(self._cancel_btn)
        btn_row.addStretch()
        form_layout.addLayout(btn_row)

        self._status_label = QLabel()
        self._status_label.setWordWrap(True)
        self._preview_field = QTextEdit()
        self._preview_field.setReadOnly(True)
        self._summary_field = QTextEdit()
        self._summary_field.setReadOnly(True)
        self._preview_title = QLabel()
        self._summary_title = QLabel()
        form_layout.addWidget(self._status_label)
        form_layout.addWidget(self._preview_title)
        form_layout.addWidget(self._preview_field, stretch=1)
        form_layout.addWidget(self._summary_title)
        form_layout.addWidget(self._summary_field, stretch=1)
        layout.addWidget(self._analyze_form_host, stretch=1)
        self._tag_combo.currentIndexChanged.connect(self._update_analyze_empty_state)
        return widget

    def _build_cards_tab(self) -> QWidget:
        widget = QWidget()
        widget.setObjectName("CardsTabWidget")
        widget.setStyleSheet(_CARDS_TAB_STYLE)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(12)

        top = QHBoxLayout()
        top.setSpacing(8)
        self._deck_label = QLabel()
        self._deck_label.setObjectName("cardsDeckLabel")
        self._deck_combo = QComboBox()
        self._deck_combo.setObjectName("cardsDeckCombo")
        configure_single_line_combo(self._deck_combo)
        self._deck_combo.currentIndexChanged.connect(self._load_cards)
        self._generate_ai_deck_btn = QPushButton()
        self._generate_ai_deck_btn.setObjectName("btnPrimary")
        self._generate_ai_deck_btn.clicked.connect(self._open_ai_deck_dialog)
        self._export_btn = QPushButton()
        self._export_btn.setObjectName("btnSecondary")
        self._export_btn.clicked.connect(self._export_anki)
        self._edit_card_btn = QPushButton()
        self._edit_card_btn.setObjectName("btnSecondary")
        self._edit_card_btn.clicked.connect(self._edit_selected_card)
        self._media_btn = QPushButton()
        self._media_btn.setObjectName("btnSecondary")
        self._media_btn.clicked.connect(self._generate_media_for_deck)
        self._delete_card_btn = QPushButton()
        self._delete_card_btn.setObjectName("btnDanger")
        self._delete_card_btn.clicked.connect(self._delete_selected_card)
        self._delete_deck_btn = QPushButton()
        self._delete_deck_btn.setObjectName("btnDanger")
        self._delete_deck_btn.clicked.connect(self._delete_selected_deck)

        top.addWidget(self._deck_label)
        top.addWidget(self._deck_combo, stretch=1)
        top.addWidget(self._generate_ai_deck_btn)
        top.addWidget(self._export_btn)
        top.addWidget(self._edit_card_btn)
        top.addWidget(self._media_btn)
        top.addStretch()
        top.addWidget(self._delete_card_btn)
        top.addWidget(self._delete_deck_btn)
        layout.addLayout(top)

        self._cards_table_card = QFrame()
        self._cards_table_card.setObjectName("cardsTableCard")
        table_layout = QVBoxLayout(self._cards_table_card)
        table_layout.setContentsMargins(0, 0, 0, 0)

        self._cards_table = QTableWidget(0, 9)
        self._cards_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._cards_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._cards_table.verticalHeader().setVisible(False)
        self._cards_table.setShowGrid(False)
        self._cards_table.setAlternatingRowColors(False)
        self._cards_table.doubleClicked.connect(self._edit_selected_card)
        self._cards_table.horizontalHeader().setStretchLastSection(False)
        table_layout.addWidget(self._cards_table)
        layout.addWidget(self._cards_table_card, stretch=1)
        return widget

    def _build_review_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        top = QHBoxLayout()
        self._review_deck_combo = QComboBox()
        self._review_deck_combo.currentIndexChanged.connect(self._on_review_deck_changed)
        self._review_deck_label = QLabel()
        self._learn_context_label = QLabel()
        self._learn_context_label.setStyleSheet("color: #64748b; font-size: 12px; font-weight: 600;")
        top.addWidget(self._learn_context_label)
        top.addWidget(self._review_deck_label)
        top.addWidget(self._review_deck_combo, stretch=1)
        layout.addLayout(top)
        self._review_session = ReviewSessionWidget()
        self._review_session.grade_submitted.connect(self._review_session.update_streak)
        self._review_session.session_finished.connect(self._review_session.update_streak)
        self._review_session.session_finished.connect(self._refresh_deck_combo_due_counts)
        layout.addWidget(self._review_session, stretch=1)
        return widget

    def _build_quiz_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        self._quiz_session = QuizSessionWidget()
        self._quiz_session.generation_finished.connect(self._on_quiz_generation_finished)
        self._quiz_session.session_finished.connect(self._on_quiz_session_finished)
        self._quiz_session.finish_requested.connect(
            lambda: self._tabs.setCurrentIndex(_TAB_REVIEW)
        )
        layout.addWidget(self._quiz_session, stretch=1)
        return widget

    def _on_quiz_session_finished(self) -> None:
        if hasattr(self, "_progress_widget"):
            self._progress_widget.refresh()

    def _on_quiz_generation_finished(self) -> None:
        self._quiz_session.refresh_preview()
        if hasattr(self, "_progress_widget"):
            self._progress_widget.refresh()

    def _build_progress_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        self._progress_widget = LearningProgressWidget()
        layout.addWidget(self._progress_widget, stretch=1)
        return widget

    def retranslate_ui(self) -> None:
        title = tr("learning.app_title") if self._standalone else tr("learning.window_title")
        self.setWindowTitle(title)
        if self._help_menu is not None:
            self._help_menu.setTitle(tr("main.menu_help"))
        if self._help_onboarding_action is not None:
            self._help_onboarding_action.setText(tr("learning.onboarding.show_again"))
        if self._standalone:
            if self._tools_menu is not None:
                self._tools_menu.setTitle(tr("main.menu_tools"))
            if self._settings_action is not None:
                self._settings_action.setText(tr("main.menu_settings"))
            if self._help_about_action is not None:
                self._help_about_action.setText(tr("main.menu_help_about"))
            if self._help_check_updates_action is not None:
                self._help_check_updates_action.setText(tr("main.menu_help_check_updates"))
            if self._help_learning_action is not None:
                self._help_learning_action.setText(tr("main.menu_help_learning"))
            if self._quit_action is not None:
                self._quit_action.setText(tr("tray.quit"))
        elif self._help_learning_action is not None:
            self._help_learning_action.setText(tr("main.menu_help_learning"))
        self._tabs.setTabText(_TAB_CREATE_DECK, tr("learning.tab_create_deck"))
        self._tabs.setTabText(_TAB_CARDS, tr("learning.tab_cards"))
        self._tabs.setTabText(_TAB_REVIEW, tr("learning.tab_review"))
        self._tabs.setTabText(_TAB_QUIZ, tr("learning.tab_quiz"))
        self._tabs.setTabText(_TAB_STATS, tr("learning.section_stats"))
        self._tag_label.setText(tr("learning.corpus_tag"))
        self._direction_label.setText(tr("learning.direction"))
        self._model_label.setText(tr("learning.model"))
        self._starred_only.setText(tr("learning.starred_only"))
        self._preview_btn.setText(tr("learning.preview_local"))
        self._analyze_btn.setText(tr("learning.run_analysis"))
        self._cancel_btn.setText(tr("main.cancel"))
        self._preview_title.setText(tr("learning.local_preview"))
        self._summary_title.setText(tr("learning.analysis_summary"))
        self._deck_label.setText(tr("learning.deck"))
        self._export_btn.setText(tr("learning.export_anki"))
        self._edit_card_btn.setText(tr("learning.edit_card"))
        self._media_btn.setText(tr("learning.generate_media"))
        self._delete_card_btn.setText(tr("learning.delete_card"))
        self._delete_deck_btn.setText(tr("learning.delete_deck"))
        self._generate_ai_deck_btn.setText(tr("learning.ai_deck.generate_button"))
        self._generate_ai_deck_btn.setVisible(is_enabled("learning.ai_deck_generator"))
        self._cards_table.setHorizontalHeaderLabels(
            [
                tr("learning.card_front").upper(),
                tr("learning.card_back").upper(),
                tr("learning.card_hint").upper(),
                tr("learning.card_notes").upper(),
                tr("learning.card_status").upper(),
                tr("learning.card_next_review").upper(),
                tr("learning.card_last_grade").upper(),
                tr("learning.card_review_count").upper(),
                tr("learning.card_priority").upper(),
            ]
        )
        self._review_deck_label.setText(tr("learning.deck"))
        self._update_learn_context_label()
        self._update_analyze_empty_state()
        self._review_session.retranslate_ui()
        self._quiz_session.retranslate_ui()
        if hasattr(self, "_progress_widget"):
            self._progress_widget.retranslate_ui()

    def _configure_cards_table_columns(self) -> None:
        header = self._cards_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(40)
        header.setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.resizeSection(8, min(header.sectionSize(8), _LEARNING_CARDS_PRIORITY_WIDTH))

    def _reload_model_combo(self) -> None:
        current = self._model_combo.currentData() if self._model_combo.count() else None
        if current is None:
            stored_model, _ = settings.get_ui_preferences()
            current = stored_model
        reload_combo(
            self._model_combo,
            [(entry.model_id, entry.display_name) for entry in get_model_entries()],
            current_data=current,
        )
        if self._model_combo.count() and self._model_combo.currentIndex() < 0:
            self._model_combo.setCurrentIndex(0)

    def _reload_tags(self) -> None:
        direction = self._direction_combo.currentData()
        current = self._tag_combo.currentData()
        self._tag_combo.blockSignals(True)
        self._tag_combo.clear()
        untagged = history.count_untagged(direction=direction, learning_kind=True)
        self._tag_combo.addItem(tr("learning.tag_untagged", count=untagged), UNTAGGED_SENTINEL)
        if is_enabled("history.tags"):
            for tag, count in history.get_tag_counts(direction=direction, learning_kind=True):
                self._tag_combo.addItem(f"{tag} ({count})", tag)
        if current is not None:
            index = self._tag_combo.findData(current)
            if index >= 0:
                self._tag_combo.setCurrentIndex(index)
        elif untagged > 0:
            self._tag_combo.setCurrentIndex(0)
        elif self._tag_combo.count() > 1:
            self._tag_combo.setCurrentIndex(1)
        elif self._tag_combo.count():
            self._tag_combo.setCurrentIndex(0)
        self._tag_combo.blockSignals(False)
        self._update_analyze_empty_state()

    def _corpus_tag_selection(self) -> tuple[str, bool, str]:
        data = self._tag_combo.currentData()
        if data == UNTAGGED_SENTINEL:
            return "", True, tr("learning.untagged_deck_name")
        tag = str(data or "").strip()
        return tag, False, tag or tr("learning.untagged_deck_name")

    def _corpus_records(self) -> list[history.TranslationRecord]:
        tag, untagged, _label = self._corpus_tag_selection()
        direction = self._direction_combo.currentData()
        if untagged:
            return history.search_records(
                direction=direction, untagged_only=True, limit=5000, learning_kind=True
            )
        if not tag:
            return []
        return history.search_records(
            direction=direction, tag=tag, limit=5000, learning_kind=True
        )

    def _update_analyze_empty_state(self) -> None:
        if not hasattr(self, "_analyze_empty"):
            return
        records = self._corpus_records()
        has_records = bool(records)
        self._analyze_form_host.setVisible(True)
        self._preview_btn.setEnabled(has_records)
        self._analyze_btn.setEnabled(has_records)
        if has_records:
            self._analyze_empty.hide_state()
            return
        _tag, untagged, label = self._corpus_tag_selection()
        if untagged:
            title = tr("learning.empty_untagged_title")
            body = tr("learning.empty_untagged_body")
        else:
            title = tr("learning.empty_tag_title", tag=label)
            body = tr("learning.empty_tag_body", tag=label)
        action = "" if self._standalone else tr("learning.empty_open_main")
        self._analyze_empty.set_content(title, body, action=action)

    def _on_analyze_empty_action(self) -> None:
        if not self._standalone and self.parent() is not None:
            from quicklingo.ui.qt_utils import raise_window

            raise_window(self.parent())

    def navigate_to(
        self,
        tab: str = "create_deck",
        *,
        tag: str | None = None,
        direction: str | None = None,
        untagged: bool = False,
    ) -> None:
        tab_indices = {
            "create_deck": _TAB_CREATE_DECK,
            "cards": _TAB_CARDS,
            "review": _TAB_REVIEW,
            "quiz": _TAB_QUIZ,
            "stats": _TAB_STATS,
        }
        if tag is not None or untagged:
            self._pending_nav = {"tag": tag, "direction": direction, "untagged": untagged}
            self._apply_pending_nav()
        self._tabs.setCurrentIndex(tab_indices.get(tab, _TAB_CREATE_DECK))

    def _apply_pending_nav(self) -> None:
        if not self._pending_nav:
            return
        nav = self._pending_nav
        self._pending_nav = None
        if nav.get("direction"):
            index = self._direction_combo.findData(nav["direction"])
            if index >= 0:
                self._direction_combo.setCurrentIndex(index)
        self._reload_tags()
        if nav.get("untagged"):
            index = self._tag_combo.findData(UNTAGGED_SENTINEL)
        else:
            tag = nav.get("tag") or ""
            index = self._tag_combo.findData(tag)
        if index >= 0:
            self._tag_combo.setCurrentIndex(index)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if self._pending_nav:
            self._apply_pending_nav()
        LearningOnboardingDialog.maybe_show(self, standalone=self._standalone)

    def _on_tab_changed(self, index: int) -> None:
        if index == _TAB_CARDS:
            self._load_cards()
        elif index == _TAB_REVIEW:
            self._on_review_deck_changed()
            self._update_learn_context_label()
        elif index == _TAB_QUIZ:
            self._quiz_session.refresh_preview()
            self._quiz_session.generation_panel.refresh()
        elif index == _TAB_STATS:
            self._progress_widget.refresh()

    def _update_learn_context_label(self) -> None:
        deck_id = self._review_deck_combo.currentData()
        deck = learning.get_deck(deck_id) if deck_id else None
        if deck is None:
            self._learn_context_label.setText("")
            return
        due = count_due_cards(deck.id)
        self._learn_context_label.setText(
            tr("learning.learn_deck_context", name=deck.name, due=due)
        )

    def _on_quiz_review_weak(self, card_ids: list[int], deck_id: int) -> None:
        deck = learning.get_deck(deck_id)
        if deck is None or not card_ids:
            return
        cards = learning.list_cards_by_ids(card_ids)
        self._tabs.setCurrentIndex(_TAB_REVIEW)
        self._review_session.start_cram_with_cards(deck.id, cards, direction=deck.direction)

    def _reload_decks(self) -> None:
        decks = learning.list_decks()
        for combo in (self._deck_combo, self._review_deck_combo):
            current = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            for deck in decks:
                due = count_due_cards(deck.id)
                label = f"{deck.name} ({get_direction_label(deck.direction)}) · {due}"
                combo.addItem(label, deck.id)
            if current is not None:
                index = combo.findData(current)
                if index >= 0:
                    combo.setCurrentIndex(index)
            combo.blockSignals(False)
        if self._current_deck_id is not None:
            index = self._deck_combo.findData(self._current_deck_id)
            if index >= 0:
                self._deck_combo.setCurrentIndex(index)
        self._load_cards()
        self._on_review_deck_changed()
        if hasattr(self, "_quiz_session"):
            self._quiz_session.reload_decks()

    def _refresh_deck_combo_due_counts(self) -> None:
        for combo in (self._deck_combo, self._review_deck_combo):
            for index in range(combo.count()):
                deck_id = combo.itemData(index)
                deck = learning.get_deck(deck_id)
                if deck is None:
                    continue
                due = count_due_cards(deck.id)
                label = f"{deck.name} ({get_direction_label(deck.direction)}) · {due}"
                combo.setItemText(index, label)
        if hasattr(self, "_quiz_session"):
            self._quiz_session.reload_decks()
        self._update_learn_context_label()

    def _on_review_deck_changed(self) -> None:
        deck_id = self._review_deck_combo.currentData()
        deck = learning.get_deck(deck_id) if deck_id else None
        direction = deck.direction if deck else "ua-en"
        self._review_session.set_deck(deck_id, direction=direction)
        self._update_learn_context_label()

    def _preview_local(self) -> None:
        records = self._corpus_records()
        difficult = compute_difficult_words(records)
        max_candidates = int(get_feature("learning.ai_corpus_analysis").get("max_candidates", 120))
        candidates = select_candidates(
            records,
            max_candidates=max_candidates,
            starred_only=self._starred_only.isChecked(),
            difficult_items=difficult,
        )
        lines = [
            tr("learning.preview_stats", records=len(records), candidates=len(candidates)),
            "",
        ]
        for item in difficult[:25]:
            lines.append(f"- {item.term} ({item.count}) [{item.kind}]")
        self._preview_field.setPlainText("\n".join(lines))
        self._status_label.setText(tr("learning.preview_ready"))

    def _run_analysis(self) -> None:
        if not is_enabled("learning.ai_corpus_analysis"):
            QMessageBox.information(
                self,
                tr("learning.window_title"),
                tr("learning.analysis_disabled"),
            )
            return
        if self._worker is not None and self._worker.isRunning():
            return
        records = self._corpus_records()
        if not records:
            self._status_label.setText(tr("learning.no_corpus"))
            return
        tag, _untagged, deck_label = self._corpus_tag_selection()
        direction = self._direction_combo.currentData()
        max_candidates = int(get_feature("learning.ai_corpus_analysis").get("max_candidates", 120))
        candidates = select_candidates(
            records,
            max_candidates=max_candidates,
            starred_only=self._starred_only.isChecked(),
            difficult_items=compute_difficult_words(records),
        )
        direction_label = self._direction_combo.currentText()
        confirm = QMessageBox.question(
            self,
            tr("learning.analysis_confirm_title"),
            tr(
                "learning.analysis_confirm_body",
                records=len(records),
                candidates=len(candidates),
                deck=deck_label,
                direction=direction_label,
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        model_entry = get_model_by_index(self._model_combo.currentIndex())
        feature = get_feature("learning.ai_corpus_analysis")
        self._worker = CorpusAnalysisWorker(
            records,
            tag=tag,
            direction=direction,
            model_entry=model_entry,
            deck_display_name=deck_label,
            max_candidates=int(feature.get("max_candidates", 120)),
            batch_size=int(feature.get("batch_size", 40)),
            starred_only=self._starred_only.isChecked(),
            parent=self,
        )
        self._worker.progress.connect(self._status_label.setText)
        self._worker.finished.connect(self._on_analysis_finished)
        self._worker.error.connect(self._on_analysis_error)
        self._analyze_btn.setEnabled(False)
        self._cancel_btn.setVisible(True)
        self._status_label.setText(tr("learning.analysis_running"))
        self._worker.start()

    def _cancel_analysis(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()

    def _on_analysis_finished(self, deck_id: int, summary: str, media_meta: dict) -> None:
        self._worker = None
        self._current_deck_id = deck_id
        self._analyze_btn.setEnabled(True)
        self._cancel_btn.setVisible(False)
        self._summary_field.setPlainText(summary)
        self._status_label.setText(tr("learning.analysis_done"))
        self._reload_decks()
        self._load_cards()
        self._tabs.setCurrentIndex(_TAB_CARDS)
        self._start_media_worker(deck_id, media_meta)

    def _on_analysis_error(self, message: str) -> None:
        self._worker = None
        self._analyze_btn.setEnabled(True)
        self._cancel_btn.setVisible(False)
        self._status_label.setText(tr("main.status_error", message=message))

    def _start_media_worker(self, deck_id: int, media_meta: dict) -> None:
        card_ids = media_meta.get("card_ids", [])
        if not card_ids:
            return
        if self._media_worker is not None and self._media_worker.isRunning():
            self._media_worker.cancel()
        deck = learning.get_deck(deck_id)
        if deck is None:
            return
        self._media_worker = CardMediaWorker(
            deck_id,
            card_ids,
            direction=deck.direction,
            image_prompts=media_meta.get("image_prompts", {}),
            imageable=media_meta.get("imageable", {}),
            parent=self,
        )
        self._media_worker.progress.connect(
            lambda msg: self._status_label.setText(tr("learning.media_progress", msg=msg))
        )
        self._media_worker.finished.connect(self._on_media_finished)
        self._media_worker.start()

    def _on_media_finished(self, _deck_id: int) -> None:
        self._media_worker = None
        self._load_cards()
        self._status_label.setText(tr("learning.media_done"))

    def _generate_media_for_deck(self) -> None:
        deck_id = self._deck_combo.currentData()
        deck = learning.get_deck(deck_id) if deck_id else None
        if deck is None:
            return
        cards = learning.list_cards(deck.id)
        imageable = {card.id: bool(card.image_prompt) for card in cards}
        image_prompts = {card.id: card.image_prompt for card in cards if card.image_prompt}
        self._start_media_worker(
            deck.id,
            {"card_ids": [card.id for card in cards], "imageable": imageable, "image_prompts": image_prompts},
        )

    def _status_label_for_card(self, card: learning.LearningCard) -> str:
        bucket = card_bucket(card)
        return tr(f"learning.status_{bucket}")

    def _grade_label(self, rating: int) -> str:
        labels = {
            1: tr("learning.review_again"),
            2: tr("learning.review_hard"),
            3: tr("learning.review_good"),
            4: tr("learning.review_easy"),
        }
        return labels.get(rating, "—")

    def _load_cards(self) -> None:
        deck_id = self._deck_combo.currentData()
        if deck_id is None:
            self._cards_table.setRowCount(0)
            return
        deck = learning.get_deck(deck_id)
        if deck and deck.analysis_summary:
            self._summary_field.setPlainText(deck.analysis_summary)
        cards = learning.list_cards(deck_id)
        learning.backfill_card_fields(deck_id)
        cards = learning.list_cards(deck_id)
        stats = learning.get_card_review_stats([card.id for card in cards])
        self._cards_table.setRowCount(len(cards))
        for row, card in enumerate(cards):
            card_stats = stats.get(card.id, {})
            next_review = card.next_review_date[:10] if card.next_review_date else "—"
            last_rating = int(card_stats.get("last_rating") or 0)
            review_count = int(card_stats.get("review_count") or 0)
            for col, text in enumerate(
                (
                    card.front,
                    card.back,
                    card.hint,
                    card.notes,
                    self._status_label_for_card(card),
                    next_review,
                    self._grade_label(last_rating) if last_rating else "—",
                    str(review_count),
                    str(card.priority),
                )
            ):
                item = QTableWidgetItem(text)
                if col < 4 and text:
                    item.setToolTip(text)
                self._cards_table.setItem(row, col, item)

    def _edit_selected_card(self) -> None:
        rows = self._cards_table.selectionModel().selectedRows()
        if not rows:
            return
        deck_id = self._deck_combo.currentData()
        if deck_id is None:
            return
        cards = learning.list_cards(deck_id)
        row = rows[0].row()
        if row < 0 or row >= len(cards):
            return
        card = cards[row]
        deck = learning.get_deck(deck_id)
        direction = deck.direction if deck else "ua-en"
        dialog = _CardEditDialog(card, direction=direction, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        if not values["front"] or not values["back"]:
            return
        learning.update_card(
            card.id,
            front=values["front"],
            back=values["back"],
            context=values["context"],
            hint=values["hint"],
            notes=values["notes"],
        )
        self._load_cards()

    def _export_anki(self) -> None:
        if not is_enabled("learning.anki_export"):
            return
        deck_id = self._deck_combo.currentData()
        deck = learning.get_deck(deck_id) if deck_id else None
        if deck is None:
            return
        cards = learning.list_cards(deck.id)
        if not cards:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("learning.export_anki_title"),
            f"{deck.tag or deck.name}-anki.apkg",
            "Anki package (*.apkg);;CSV (*.csv)",
        )
        if not path:
            return
        if path.lower().endswith(".csv"):
            with open(path, "w", encoding="utf-8", newline="") as handle:
                handle.write(export_anki_csv(cards, deck))
        else:
            apkg_path = Path(path)
            if apkg_path.suffix.lower() != ".apkg":
                apkg_path = apkg_path.with_suffix(".apkg")
            export_anki_apkg(cards, deck, apkg_path)

    def _delete_selected_card(self) -> None:
        rows = self._cards_table.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        deck_id = self._deck_combo.currentData()
        if deck_id is None:
            return
        cards = learning.list_cards(deck_id)
        if row < 0 or row >= len(cards):
            return
        learning.delete_card(cards[row].id)
        self._load_cards()

    def _open_ai_deck_dialog(self) -> None:
        if not is_enabled("learning.ai_deck_generator"):
            return
        dialog = AiDeckGeneratorDialog(
            self,
            initial_model_id=self._model_combo.currentData(),
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        deck_id, summary, media_meta = dialog.result_data()
        self._on_ai_deck_finished(deck_id, summary, media_meta)

    def _on_ai_deck_finished(self, deck_id: int, summary: str, media_meta: dict) -> None:
        self._current_deck_id = deck_id
        self._summary_field.setPlainText(summary)
        self._status_label.setText(tr("learning.ai_deck.done"))
        self._reload_decks()
        index = self._deck_combo.findData(deck_id)
        if index >= 0:
            self._deck_combo.setCurrentIndex(index)
        self._tabs.setCurrentIndex(_TAB_CARDS)
        self._load_cards()
        self._start_media_worker(deck_id, media_meta)

    def _delete_selected_deck(self) -> None:
        deck_id = self._deck_combo.currentData()
        deck = learning.get_deck(deck_id) if deck_id is not None else None
        if deck is None:
            return
        card_count = learning.count_cards(deck.id)
        deck_name = deck.name or deck.tag or str(deck.id)
        reply = QMessageBox.question(
            self,
            tr("learning.delete_deck_title"),
            tr("learning.delete_deck_confirm", name=deck_name, count=card_count),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        learning.delete_deck(deck.id)
        if self._current_deck_id == deck.id:
            self._current_deck_id = None
        self._reload_decks()
        self._load_cards()

    def add_vocab_card(self, front: str, back: str, *, context: str = "", tag: str = "", direction: str = "") -> None:
        if not front.strip() or not back.strip():
            return
        deck = learning.get_or_create_deck(
            name=tag or tr("learning.manual_deck"),
            tag=tag,
            direction=direction or "ua-en",
        )
        learning.upsert_card(
            deck.id,
            front=front.strip(),
            back=back.strip(),
            context=context,
            priority=4,
        )
        self._current_deck_id = deck.id
        self._reload_decks()
        self._load_cards()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._media_worker is not None and self._media_worker.isRunning():
            self._media_worker.cancel()
        save_table_columns(self._cards_table, "learning", "cards")
        save_window_geometry(self, "learning")
        self.closed.emit()
        super().closeEvent(event)
