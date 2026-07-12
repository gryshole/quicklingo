from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent, QShowEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
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

from quicklingo.config.loader import get_direction_label, resolve_learning_direction
from quicklingo.db import learning
from quicklingo.features import is_enabled
from quicklingo.i18n import tr
from quicklingo.learning.anki_export import export_anki_apkg, export_anki_csv
from quicklingo.learning.card_display import parse_context, serialize_context
from quicklingo.learning.review_queue import card_bucket, count_due_cards
from quicklingo.ui.dialogs.ai_deck_generator_dialog import AiDeckGeneratorDialog
from quicklingo.ui.dialogs.learning_onboarding_dialog import LearningOnboardingDialog
from quicklingo.ui.controllers.update_controller import UpdateController
from quicklingo.ui.qt_utils import configure_single_line_combo, open_help
from quicklingo.ui.settings_dialog import SettingsDialog
from quicklingo.ui.widgets.create_deck_tab import CreateDeckTabWidget
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


_TAB_CREATE_DECK = 0
_TAB_CARDS = 1
_TAB_REVIEW = 2
_TAB_QUIZ = 3
_TAB_STATS = 4

_LEARNING_CARDS_TABLE_WIDTHS = [145, 145, 190, 160, 50, 150, 110, 85, 50]
_LEARNING_CARDS_PRIORITY_WIDTH = 52

_LEARNING_TABS_STYLE = """
QTabWidget::pane {
    border: none;
    background: #f1f5f9;
    top: 0px;
    margin: 0px;
    padding: 0px;
}
QTabBar {
    background: transparent;
    border: none;
}
QTabBar::tab {
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    padding: 8px 16px;
    margin-right: 4px;
    color: #64748b;
    font-size: 13px;
}
QTabBar::tab:selected {
    background: #ffffff;
    color: #0f172a;
    font-weight: bold;
    border-bottom: 2px solid #0078D7;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}
QTabBar::tab:hover:!selected {
    color: #334155;
    background: rgba(255, 255, 255, 0.55);
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}
"""

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
QFrame#deckSummaryCard {
    background-color: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
}
QFrame#deckSummaryCard QLabel#deckSummaryLabel {
    color: #475569;
    font-size: 12px;
}
QFrame#deckSummaryCard QLabel#deckSummaryTitle {
    color: #64748b;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.04em;
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
        restore_window_geometry(self, "learning", default_width=1090, default_height=880)
        self._current_deck_id: int | None = None
        self._pending_nav: dict | None = None

        self._tabs = QTabWidget()
        self._tabs.setObjectName("learningTabs")
        self._tabs.setDocumentMode(True)
        self._tabs.setStyleSheet(_LEARNING_TABS_STYLE)
        self._tabs.tabBar().setExpanding(False)
        self._tabs.tabBar().setDrawBase(False)

        self._create_deck_tab = CreateDeckTabWidget(standalone=standalone)
        self._create_deck_tab.deck_created.connect(self._on_deck_created)
        self._create_deck_tab.open_main_window.connect(self._on_create_deck_open_main)
        self._cards_tab = self._build_cards_tab()
        self._review_tab = self._build_review_tab()
        self._quiz_tab = self._build_quiz_tab()
        self._progress_tab = self._build_progress_tab()

        self._tabs.addTab(self._create_deck_tab, "")
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
        top.addStretch()
        top.addWidget(self._delete_card_btn)
        top.addWidget(self._delete_deck_btn)
        layout.addLayout(top)

        self._deck_summary_card = QFrame()
        self._deck_summary_card.setObjectName("deckSummaryCard")
        summary_layout = QVBoxLayout(self._deck_summary_card)
        summary_layout.setContentsMargins(14, 12, 14, 12)
        summary_layout.setSpacing(6)
        self._deck_summary_title = QLabel()
        self._deck_summary_title.setObjectName("deckSummaryTitle")
        self._deck_summary_label = QLabel()
        self._deck_summary_label.setObjectName("deckSummaryLabel")
        self._deck_summary_label.setWordWrap(True)
        summary_layout.addWidget(self._deck_summary_title)
        summary_layout.addWidget(self._deck_summary_label)
        self._deck_summary_card.setVisible(False)
        layout.addWidget(self._deck_summary_card)

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
        self._create_deck_tab.retranslate_ui()
        self._deck_label.setText(tr("learning.deck"))
        self._deck_summary_title.setText(tr("learning.analysis_summary").upper())
        self._export_btn.setText(tr("learning.export_anki"))
        self._export_btn.setVisible(is_enabled("learning.anki_export"))
        self._edit_card_btn.setText(tr("learning.edit_card"))
        self._delete_card_btn.setText(tr("learning.delete_card"))
        self._delete_deck_btn.setText(tr("learning.delete_deck"))
        self._generate_ai_deck_btn.setText(tr("learning.ai_deck.generate_button"))
        self._generate_ai_deck_btn.setVisible(True)
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
        self._create_deck_tab.reload_model_combo()

    def _reload_tags(self) -> None:
        self._create_deck_tab._reload_tags()

    def _on_create_deck_open_main(self) -> None:
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
        self._create_deck_tab.apply_navigation(
            tag=nav.get("tag"),
            direction=nav.get("direction"),
            untagged=bool(nav.get("untagged")),
        )

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if self._pending_nav:
            self._apply_pending_nav()
        LearningOnboardingDialog.maybe_show(self, standalone=self._standalone)

    def _on_tab_changed(self, index: int) -> None:
        if index == _TAB_CREATE_DECK:
            self._create_deck_tab._reload_tags()
        elif index == _TAB_CARDS:
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

    def _on_deck_created(self, deck_id: int, summary: str) -> None:
        self._current_deck_id = deck_id
        self._reload_decks()
        self._load_cards()
        self._create_deck_tab._reload_tags()
        self._tabs.setCurrentIndex(_TAB_CARDS)

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
            self._deck_summary_card.setVisible(False)
            return
        deck = learning.get_deck(deck_id)
        if deck and deck.analysis_summary:
            self._deck_summary_label.setText(deck.analysis_summary)
            self._deck_summary_card.setVisible(True)
        else:
            self._deck_summary_label.clear()
            self._deck_summary_card.setVisible(False)
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
        dialog = AiDeckGeneratorDialog(
            self,
            initial_model_id=self._create_deck_tab.current_model_id(),
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        deck_id, summary = dialog.result_data()
        self._on_ai_deck_finished(deck_id, summary)

    def _on_ai_deck_finished(self, deck_id: int, summary: str) -> None:
        self._current_deck_id = deck_id
        self._create_deck_tab.set_status(tr("learning.ai_deck.done"))
        self._reload_decks()
        index = self._deck_combo.findData(deck_id)
        if index >= 0:
            self._deck_combo.setCurrentIndex(index)
        self._tabs.setCurrentIndex(_TAB_CARDS)
        self._load_cards()

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
        self._create_deck_tab._reload_tags()

    def closeEvent(self, event: QCloseEvent) -> None:
        save_table_columns(self._cards_table, "learning", "cards")
        save_window_geometry(self, "learning")
        self.closed.emit()
        super().closeEvent(event)
