from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from quicklingo.config.loader import get_direction_label
from quicklingo.db import learning
from quicklingo.i18n import tr
from quicklingo.learning.quiz.distractor_deck import is_quiz_distractor_deck
from quicklingo.learning.quiz.distractor_transfer import transfer_distractor_cards
from quicklingo.ui.dialogs.distractor_transfer_dialog import DistractorTransferDialog
from quicklingo.ui.learning_window import _CardEditDialog
from quicklingo.ui.qt_utils import configure_single_line_combo, reload_combo
from quicklingo.ui.window_state import (
    bind_table_columns_persistence,
    restore_table_columns,
)

_TABLE_WIDTHS = [180, 180, 120, 200, 100]

_PAGE_STYLE = """
DistractorCardsBrowserWidget {
    background-color: #f1f5f9;
}
QFrame#filterCard {
    background-color: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 10px;
}
QFrame#filterCard QLabel {
    color: #64748b;
    font-size: 12px;
}
QLabel#countBadge {
    color: #475569;
    font-size: 12px;
    background-color: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    padding: 4px 10px;
}
QFrame#filterCard QComboBox,
QFrame#filterCard QLineEdit {
    min-height: 30px;
    max-height: 30px;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    padding: 4px 10px;
    background-color: #ffffff;
    color: #1e293b;
    font-size: 13px;
}
QFrame#filterCard QComboBox:hover,
QFrame#filterCard QLineEdit:hover {
    border-color: #94a3b8;
}
QFrame#filterCard QComboBox:focus,
QFrame#filterCard QLineEdit:focus {
    border-color: #3b82f6;
}
QFrame#filterCard QComboBox::drop-down {
    border: none;
    width: 22px;
}
QPushButton#btnPrimary {
    background-color: #3b82f6;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 6px 16px;
    font-size: 13px;
    font-weight: 600;
    min-height: 30px;
}
QPushButton#btnPrimary:hover:enabled {
    background-color: #2563eb;
}
QPushButton#btnPrimary:pressed:enabled {
    background-color: #1d4ed8;
}
QPushButton#btnSecondary {
    background-color: #ffffff;
    color: #1e293b;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    padding: 6px 16px;
    font-size: 13px;
    min-height: 30px;
}
QPushButton#btnSecondary:hover:enabled {
    background-color: #f8fafc;
    border-color: #94a3b8;
}
QPushButton#btnSecondary:pressed:enabled {
    background-color: #f1f5f9;
}
QPushButton#btnDanger {
    background-color: #ffffff;
    color: #dc2626;
    border: 1px solid #fecaca;
    border-radius: 6px;
    padding: 6px 16px;
    font-size: 13px;
    min-height: 30px;
}
QPushButton#btnDanger:hover:enabled {
    background-color: #fef2f2;
    border-color: #f87171;
}
QFrame#tableCard {
    background-color: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
}
QFrame#tableCard QTableWidget {
    background-color: #ffffff;
    border: none;
    outline: none;
    gridline-color: transparent;
    selection-background-color: #eff6ff;
    selection-color: #1e293b;
    alternate-background-color: #ffffff;
}
QFrame#tableCard QTableWidget::item {
    padding: 8px 10px;
    border: none;
    border-bottom: 1px solid #f3f4f6;
    color: #334155;
}
QFrame#tableCard QTableWidget::item:selected {
    background-color: #eff6ff;
    color: #1e293b;
}
QFrame#tableCard QTableWidget::item:focus {
    outline: none;
    border: none;
    background-color: #eff6ff;
}
QFrame#tableCard QHeaderView::section {
    background-color: #f8fafc;
    color: #64748b;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    padding: 10px 10px;
    border: none;
    border-bottom: 1px solid #e5e7eb;
    border-right: 1px solid #f1f5f9;
}
QFrame#tableCard QHeaderView::section:last {
    border-right: none;
}
"""


class DistractorCardsBrowserWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("DistractorCardsBrowserWidget")
        self.setStyleSheet(_PAGE_STYLE)
        self._cards: list[learning.LearningCard] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self._filter_card = QFrame()
        self._filter_card.setObjectName("filterCard")
        filter_layout = QVBoxLayout(self._filter_card)
        filter_layout.setContentsMargins(10, 10, 10, 10)
        filter_layout.setSpacing(10)

        deck_row = QHBoxLayout()
        deck_row.setSpacing(10)
        self._deck_label = QLabel()
        self._deck_combo = QComboBox()
        configure_single_line_combo(self._deck_combo)
        self._deck_combo.currentIndexChanged.connect(self.refresh)
        self._count_label = QLabel()
        self._count_label.setObjectName("countBadge")
        self._count_label.setWordWrap(True)
        deck_row.addWidget(self._deck_label)
        deck_row.addWidget(self._deck_combo, stretch=1)
        deck_row.addWidget(self._count_label)
        filter_layout.addLayout(deck_row)

        search_row = QHBoxLayout()
        search_row.setSpacing(10)
        self._search_label = QLabel()
        self._search_field = QLineEdit()
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(250)
        self._refresh_timer.timeout.connect(self.refresh)
        self._search_field.textChanged.connect(self._schedule_refresh)
        search_row.addWidget(self._search_label)
        search_row.addWidget(self._search_field, stretch=1)
        filter_layout.addLayout(search_row)
        layout.addWidget(self._filter_card)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self._refresh_btn = QPushButton()
        self._refresh_btn.setObjectName("btnSecondary")
        self._refresh_btn.clicked.connect(self.refresh)
        self._edit_btn = QPushButton()
        self._edit_btn.setObjectName("btnSecondary")
        self._edit_btn.clicked.connect(self._edit_selected)
        self._delete_btn = QPushButton()
        self._delete_btn.setObjectName("btnDanger")
        self._delete_btn.clicked.connect(self._delete_selected)
        self._transfer_btn = QPushButton()
        self._transfer_btn.setObjectName("btnPrimary")
        self._transfer_btn.clicked.connect(self._transfer_selected)
        actions.addStretch()
        actions.addWidget(self._refresh_btn)
        actions.addWidget(self._edit_btn)
        actions.addWidget(self._delete_btn)
        actions.addWidget(self._transfer_btn)
        layout.addLayout(actions)

        self._table_card = QFrame()
        self._table_card.setObjectName("tableCard")
        table_layout = QVBoxLayout(self._table_card)
        table_layout.setContentsMargins(0, 0, 0, 0)

        self._table = QTableWidget(0, 5)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.setAlternatingRowColors(False)
        self._table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        header = self._table.horizontalHeader()
        header.setMinimumSectionSize(48)
        header.setStretchLastSection(False)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        for col in range(4):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        restore_table_columns(
            self._table,
            "learning",
            "distractor_cards",
            default_widths=_TABLE_WIDTHS,
        )
        bind_table_columns_persistence(self._table, "learning", "distractor_cards")
        self._table.cellDoubleClicked.connect(lambda _row, _col: self._edit_selected())
        table_layout.addWidget(self._table)
        layout.addWidget(self._table_card, stretch=1)

        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self._deck_label.setText(tr("learning.deck"))
        self._search_label.setText(tr("learning.distractor_decks_search"))
        self._search_field.setPlaceholderText(tr("learning.distractor_decks_search_hint"))
        self._refresh_btn.setText(tr("learning.quiz_refresh"))
        self._edit_btn.setText(tr("learning.quiz_questions_edit"))
        self._delete_btn.setText(tr("learning.delete_card"))
        self._transfer_btn.setText(tr("learning.distractor_decks_transfer_btn"))
        self._table.setHorizontalHeaderLabels(
            [
                tr("learning.card_front").upper(),
                tr("learning.card_back").upper(),
                tr("learning.card_hint").upper(),
                tr("learning.card_notes").upper(),
                tr("learning.distractor_decks_col_review").upper(),
            ]
        )

    def reload_decks(self) -> None:
        current = self._deck_combo.currentData()
        decks = [
            deck
            for deck in learning.list_decks()
            if is_quiz_distractor_deck(deck)
        ]
        reload_combo(
            self._deck_combo,
            [
                (
                    deck.id,
                    f"{deck.name} ({get_direction_label(deck.direction)})",
                )
                for deck in decks
            ],
            current_data=current,
        )
        if self._deck_combo.count() and self._deck_combo.currentIndex() < 0:
            self._deck_combo.setCurrentIndex(0)
        self.refresh()

    def _schedule_refresh(self) -> None:
        self._refresh_timer.start()

    def _current_deck(self) -> learning.LearningDeck | None:
        deck_id = self._deck_combo.currentData()
        if deck_id is None:
            return None
        return learning.get_deck(deck_id)

    def refresh(self) -> None:
        deck = self._current_deck()
        if deck is None:
            self._cards = []
            self._populate_table()
            self._count_label.setText(tr("learning.distractor_decks_count", count=0))
            return

        cards = learning.list_cards(deck.id)
        search = self._search_field.text().strip().lower()
        if search:
            filtered: list[learning.LearningCard] = []
            for card in cards:
                blob = " ".join(
                    [
                        card.front,
                        card.back,
                        card.hint,
                        card.notes,
                    ]
                ).lower()
                if search in blob:
                    filtered.append(card)
            cards = filtered

        self._cards = cards
        self._populate_table()
        self._count_label.setText(tr("learning.distractor_decks_count", count=len(cards)))

    def _populate_table(self) -> None:
        self._table.setRowCount(len(self._cards))
        for row_index, card in enumerate(self._cards):
            front_item = QTableWidgetItem(card.front)
            front_item.setData(Qt.ItemDataRole.UserRole, card.id)
            next_review = card.next_review_date[:10] if card.next_review_date else "-"
            for col, text in enumerate(
                (card.front, card.back, card.hint, card.notes, next_review)
            ):
                item = QTableWidgetItem(text if col > 0 else "")
                if col == 0:
                    item = front_item
                if col < 4 and text:
                    item.setToolTip(text)
                self._table.setItem(row_index, col, item)

    def _selected_card_ids(self) -> list[int]:
        rows = self._table.selectionModel().selectedRows()
        ids: list[int] = []
        for model_index in rows:
            item = self._table.item(model_index.row(), 0)
            if item is None:
                continue
            card_id = item.data(Qt.ItemDataRole.UserRole)
            if card_id is not None:
                ids.append(int(card_id))
        return ids

    def _edit_selected(self) -> None:
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        if row < 0 or row >= len(self._cards):
            return
        card = self._cards[row]
        deck = self._current_deck()
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
        self.refresh()

    def _delete_selected(self) -> None:
        card_ids = self._selected_card_ids()
        if not card_ids:
            return
        if len(card_ids) == 1:
            learning.delete_card(card_ids[0])
        else:
            for card_id in card_ids:
                learning.delete_card(card_id)
        self.refresh()

    def _transfer_selected(self) -> None:
        card_ids = self._selected_card_ids()
        if not card_ids:
            QMessageBox.information(
                self,
                tr("learning.distractor_decks_transfer_title"),
                tr("learning.distractor_decks_transfer_none_selected"),
            )
            return
        deck = self._current_deck()
        if deck is None:
            return
        dialog = DistractorTransferDialog(
            self,
            direction=deck.direction,
            selected_count=len(card_ids),
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        tag = dialog.target_tag()
        if not tag:
            QMessageBox.warning(
                self,
                tr("learning.distractor_decks_transfer_title"),
                tr("learning.distractor_decks_transfer_tag_required"),
            )
            return
        result = transfer_distractor_cards(
            card_ids,
            tag,
            deck.direction,
            deck_name=dialog.deck_name(),
        )
        QMessageBox.information(
            self,
            tr("learning.distractor_decks_transfer_title"),
            tr(
                "learning.distractor_decks_transfer_done",
                moved=result.moved,
                merged=result.merged,
                skipped=result.skipped,
            ),
        )
        self.refresh()
