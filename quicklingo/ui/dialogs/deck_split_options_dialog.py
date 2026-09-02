from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from quicklingo.db import learning
from quicklingo.i18n import tr
from quicklingo.learning.deck_split.models import DeckSplitAnalysisResult, DeckSplitOption

_DIALOG_STYLE = """
DeckSplitOptionsDialog {
    background-color: #f8fafc;
}
QFrame#summaryCallout {
    background-color: #eff6ff;
    border: 1px solid #bfdbfe;
    border-radius: 10px;
}
QLabel#summaryCalloutText {
    color: #475569;
    font-size: 13px;
    line-height: 1.45;
}
QLabel#sectionLabel {
    color: #64748b;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.04em;
}
QFrame#optionCard {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
}
QFrame#optionCard:hover {
    border-color: #94a3b8;
    background-color: #f8fafc;
}
QFrame#optionCard[selected="true"] {
    background-color: #eff6ff;
    border: 2px solid #3b82f6;
}
QLabel#optionCardTitle {
    color: #0f172a;
    font-size: 13px;
    font-weight: 600;
}
QLabel#optionCardMeta {
    color: #64748b;
    font-size: 12px;
}
QLabel#optionCardCheck {
    color: #3b82f6;
    font-size: 14px;
    font-weight: 700;
}
QFrame#editCard {
    background-color: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
}
QLabel#fieldLabel {
    color: #64748b;
    font-size: 12px;
    font-weight: 500;
}
QFrame#editCard QLineEdit {
    min-height: 34px;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    padding: 6px 10px;
    background-color: #ffffff;
    color: #1e293b;
    font-size: 13px;
}
QFrame#editCard QLineEdit:hover:enabled {
    border-color: #94a3b8;
}
QFrame#editCard QLineEdit:focus {
    border-color: #3b82f6;
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
}
QFrame#tableCard QTableWidget::item {
    padding: 10px 12px;
    border: none;
    border-bottom: 1px solid #f1f5f9;
    color: #334155;
    font-size: 13px;
}
QFrame#tableCard QTableWidget::item:selected {
    background-color: #eff6ff;
    color: #1e293b;
}
QFrame#tableCard QTableWidget::item:focus {
    outline: none;
    border: none;
}
QFrame#tableCard QHeaderView::section {
    background-color: #f8fafc;
    color: #64748b;
    font-size: 11px;
    font-weight: 600;
    padding: 10px 12px;
    border: none;
    border-bottom: 1px solid #e5e7eb;
}
QFrame#footerBar {
    border-top: 1px solid #e5e7eb;
    background-color: #f8fafc;
}
QPushButton#btnPrimary {
    background-color: #3b82f6;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 8px 18px;
    font-size: 13px;
    font-weight: 600;
    min-height: 36px;
}
QPushButton#btnPrimary:hover:enabled {
    background-color: #2563eb;
}
QPushButton#btnPrimary:pressed:enabled {
    background-color: #1d4ed8;
}
QPushButton#btnPrimary:disabled {
    background-color: #94a3b8;
    color: #e2e8f0;
}
QPushButton#btnSecondary {
    background-color: transparent;
    color: #475569;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    padding: 8px 18px;
    font-size: 13px;
    min-height: 36px;
}
QPushButton#btnSecondary:hover:enabled {
    background-color: #ffffff;
    border-color: #94a3b8;
    color: #1e293b;
}
QPushButton#btnSecondary:pressed:enabled {
    background-color: #f1f5f9;
}
"""


class _OptionCard(QFrame):
    activated = Signal(object)

    def __init__(
        self,
        parent=None,
        *,
        option: DeckSplitOption | None,
        title: str,
        meta: str = "",
        rationale: str = "",
    ) -> None:
        super().__init__(parent)
        self._option = option
        self.setObjectName("optionCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setProperty("selected", False)
        if rationale:
            self.setToolTip(rationale)

        row = QHBoxLayout(self)
        row.setContentsMargins(14, 12, 14, 12)
        row.setSpacing(12)

        self._check = QLabel("○")
        self._check.setObjectName("optionCardCheck")
        self._check.setFixedWidth(20)
        row.addWidget(self._check)

        text_col = QVBoxLayout()
        text_col.setSpacing(4)
        self._title = QLabel(title)
        self._title.setObjectName("optionCardTitle")
        self._title.setWordWrap(True)
        text_col.addWidget(self._title)
        if meta:
            self._meta = QLabel(meta)
            self._meta.setObjectName("optionCardMeta")
            self._meta.setWordWrap(True)
            text_col.addWidget(self._meta)
        row.addLayout(text_col, stretch=1)

    @property
    def option(self) -> DeckSplitOption | None:
        return self._option

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", selected)
        self._check.setText("●" if selected else "○")
        style = self.style()
        style.unpolish(self)
        style.polish(self)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.activated.emit(self._option)
        super().mousePressEvent(event)


class DeckSplitOptionsDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        result: DeckSplitAnalysisResult,
    ) -> None:
        super().__init__(parent)
        self._result = result
        self._selected_option: DeckSplitOption | None = None
        self._option_tiles: list[_OptionCard] = []
        self.setMinimumSize(760, 560)
        self.setStyleSheet(_DIALOG_STYLE)
        self.setWindowTitle(tr("learning.deck_split_options_title"))

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 0)
        root.setSpacing(16)

        if result.summary:
            summary_frame = QFrame()
            summary_frame.setObjectName("summaryCallout")
            summary_layout = QVBoxLayout(summary_frame)
            summary_layout.setContentsMargins(14, 12, 14, 12)
            summary_label = QLabel(result.summary)
            summary_label.setObjectName("summaryCalloutText")
            summary_label.setWordWrap(True)
            summary_layout.addWidget(summary_label)
            root.addWidget(summary_frame)

        options_label = QLabel(tr("learning.deck_split_options_title").upper())
        options_label.setObjectName("sectionLabel")
        root.addWidget(options_label)

        options_scroll = QScrollArea()
        options_scroll.setWidgetResizable(True)
        options_scroll.setFrameShape(QFrame.Shape.NoFrame)
        options_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        options_host = QWidget()
        options_layout = QVBoxLayout(options_host)
        options_layout.setContentsMargins(0, 0, 0, 0)
        options_layout.setSpacing(8)

        none_tile = _OptionCard(
            options_host,
            option=None,
            title=tr("learning.deck_split_option_none"),
        )
        none_tile.activated.connect(self._on_tile_activated)
        options_layout.addWidget(none_tile)
        self._option_tiles.append(none_tile)

        for option in result.options:
            tile = _OptionCard(
                options_host,
                option=option,
                title=tr(
                    "learning.deck_split_option_item",
                    title=option.title,
                    tag=option.tag,
                    count=len(option.card_ids),
                ),
                rationale=option.rationale,
            )
            tile.activated.connect(self._on_tile_activated)
            options_layout.addWidget(tile)
            self._option_tiles.append(tile)

        options_scroll.setWidget(options_host)
        options_scroll.setMaximumHeight(200)
        root.addWidget(options_scroll)

        edit_card = QFrame()
        edit_card.setObjectName("editCard")
        edit_layout = QHBoxLayout(edit_card)
        edit_layout.setContentsMargins(14, 14, 14, 14)
        edit_layout.setSpacing(16)

        tag_col = QVBoxLayout()
        tag_col.setSpacing(6)
        tag_label = QLabel(tr("learning.distractor_decks_target_tag"))
        tag_label.setObjectName("fieldLabel")
        self._tag_field = QLineEdit()
        tag_col.addWidget(tag_label)
        tag_col.addWidget(self._tag_field)
        edit_layout.addLayout(tag_col, stretch=1)

        name_col = QVBoxLayout()
        name_col.setSpacing(6)
        name_label = QLabel(tr("learning.distractor_decks_target_name"))
        name_label.setObjectName("fieldLabel")
        self._name_field = QLineEdit()
        name_col.addWidget(name_label)
        name_col.addWidget(self._name_field)
        edit_layout.addLayout(name_col, stretch=1)
        root.addWidget(edit_card)

        table_card = QFrame()
        table_card.setObjectName("tableCard")
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(0, 0, 0, 0)
        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(
            [
                tr("learning.card_front"),
                tr("learning.card_back"),
            ]
        )
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setShowGrid(False)
        self._table.setAlternatingRowColors(False)
        header = self._table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        table_layout.addWidget(self._table)
        root.addWidget(table_card, stretch=1)

        footer = QFrame()
        footer.setObjectName("footerBar")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(20, 14, 20, 14)
        footer_layout.addStretch()
        self._cancel_btn = QPushButton(tr("main.cancel"))
        self._cancel_btn.setObjectName("btnSecondary")
        self._cancel_btn.clicked.connect(self.reject)
        self._apply_btn = QPushButton(tr("learning.deck_split_apply"))
        self._apply_btn.setObjectName("btnPrimary")
        self._apply_btn.clicked.connect(self._on_accept)
        footer_layout.addWidget(self._cancel_btn)
        footer_layout.addWidget(self._apply_btn)
        root.addWidget(footer)

        self._on_tile_activated(None)

    def _same_option(
        self,
        left: DeckSplitOption | None,
        right: DeckSplitOption | None,
    ) -> bool:
        if left is None and right is None:
            return True
        if left is None or right is None:
            return False
        return left.id == right.id

    def _on_tile_activated(self, option: DeckSplitOption | None) -> None:
        self._selected_option = option
        for tile in self._option_tiles:
            tile.set_selected(self._same_option(tile.option, option))
        enabled = option is not None
        self._tag_field.setEnabled(enabled)
        self._name_field.setEnabled(enabled)
        self._apply_btn.setEnabled(enabled)
        if option is None:
            self._tag_field.clear()
            self._name_field.clear()
            self._populate_table([])
            return
        self._tag_field.setText(option.tag)
        self._name_field.setText(option.deck_name)
        self._populate_table(option.card_ids)

    def _populate_table(self, card_ids: list[int]) -> None:
        cards = learning.list_cards_by_ids(card_ids)
        by_id = {card.id: card for card in cards}
        self._table.setRowCount(len(card_ids))
        for row, card_id in enumerate(card_ids):
            card = by_id.get(card_id)
            front = card.front if card else ""
            back = card.back if card else ""
            self._table.setItem(row, 0, QTableWidgetItem(front))
            self._table.setItem(row, 1, QTableWidgetItem(back))

    def _on_accept(self) -> None:
        if self._selected_option is None:
            self.reject()
            return
        self.accept()

    def selected_option(self) -> DeckSplitOption | None:
        if self._selected_option is None:
            return None
        tag = self._tag_field.text().strip()
        name = self._name_field.text().strip() or tag
        return DeckSplitOption(
            id=self._selected_option.id,
            title=self._selected_option.title,
            tag=tag,
            deck_name=name,
            rationale=self._selected_option.rationale,
            fronts=list(self._selected_option.fronts),
            card_ids=list(self._selected_option.card_ids),
        )
