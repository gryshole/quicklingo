from __future__ import annotations

import html

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from quicklingo.config.loader import get_direction_label
from quicklingo.db import learning
from quicklingo.db.learning import QuizQuestionRow
from quicklingo.i18n import tr
from quicklingo.ui.dialogs.quiz_question_edit_dialog import QuizQuestionEditDialog
from quicklingo.ui.dialogs.quiz_question_regen_dialog import QuizQuestionRegenDialog
from quicklingo.ui.qt_utils import configure_single_line_combo, reload_combo
from quicklingo.ui.window_state import (
    bind_table_columns_persistence,
    restore_table_columns,
)

_TABLE_WIDTHS = [150, 125, 75, 440, 50, 130]

_PAGE_STYLE = """
QuizQuestionsBrowserWidget {
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
QLabel#coverageBadge {
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
QFrame#previewCard {
    background-color: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 12px;
}
QFrame#previewCard QTextBrowser {
    background: transparent;
    border: none;
    padding: 8px 12px 8px 16px;
}
QComboBox#filterTypeCombo {
    min-width: 160px;
}
QComboBox#filterStatusCombo {
    min-width: 140px;
}
"""

def _question_type_label(qtype: str) -> str:
    mapping = {
        "fill_blank": tr("learning.quiz_type_fill_blank"),
        "definition_match": tr("learning.quiz_type_definition"),
        "translation_recall": tr("learning.quiz_type_translation"),
    }
    return mapping.get(qtype, qtype)


def _status_label(status: str) -> str:
    if status == "active":
        return tr("learning.quiz_questions_status_active")
    if status == "failed":
        return tr("learning.quiz_questions_status_failed")
    return status


def _truncate(text: str, limit: int = 80) -> str:
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1] + "…"


def _build_detail_html(row: QuizQuestionRow) -> str:
    prompt = html.escape(row.prompt_text.strip())
    correct_raw = row.correct_english.strip()
    correct = html.escape(correct_raw)
    correct_key = correct_raw.lower()
    parts = [
        '<div style="font-family: Segoe UI, sans-serif; color: #334155; line-height: 1.5; '
        'padding: 4px 8px 4px 4px;">',
        f'<p style="margin: 0 0 4px 0; font-size: 11px; font-weight: 600; '
        f'letter-spacing: 0.04em; color: #64748b; text-transform: uppercase;">'
        f'{html.escape(tr("learning.quiz_question_edit_prompt"))}</p>',
        f'<h3 style="margin: 0 0 14px 0; font-size: 16px; font-weight: 600; color: #1e293b;">'
        f"{prompt or '—'}</h3>",
    ]
    if row.example_sentence.strip():
        example = html.escape(row.example_sentence.strip())
        parts.append(
            f'<p style="margin: 0 0 4px 0; font-size: 11px; font-weight: 600; '
            f'letter-spacing: 0.04em; color: #64748b; text-transform: uppercase;">'
            f'{html.escape(tr("learning.quiz_question_edit_example"))}</p>'
            f'<p style="margin: 0 0 14px 0; font-size: 13px; color: #475569;">{example}</p>'
        )
    if row.choices_pool:
        parts.append(
            f'<p style="margin: 0 0 6px 0; font-size: 11px; font-weight: 600; '
            f'letter-spacing: 0.04em; color: #64748b; text-transform: uppercase;">'
            f'{html.escape(tr("learning.quiz_question_edit_choices"))}</p>'
            f'<ul style="margin: 0 0 14px 0; padding-left: 28px; margin-left: 4px; '
            f'font-size: 13px; color: #475569; line-height: 1.6;">'
        )
        for choice in row.choices_pool:
            choice_esc = html.escape(choice)
            if choice.strip().lower() == correct_key:
                parts.append(
                    f'<li><b style="color: #059669;">{choice_esc}</b></li>'
                )
            else:
                parts.append(f"<li>{choice_esc}</li>")
        parts.append("</ul>")
    correct_label = html.escape(tr("learning.quiz_question_edit_correct"))
    parts.append(
        f'<p style="margin: 0 0 14px 0; font-size: 14px; line-height: 1.5;">'
        f'<b style="color: #059669;">{correct_label}: {correct or "—"}</b></p>'
    )
    meta: list[str] = []
    if row.model_id:
        meta.append(f"{html.escape(tr('learning.model'))}: {html.escape(row.model_id)}")
    meta.append(
        f"{html.escape(tr('learning.quiz_questions_col_updated'))}: {html.escape(row.updated_at)}"
    )
    parts.append(
        f'<p style="margin: 0; font-size: 11px; color: #94a3b8;">{" · ".join(meta)}</p>'
    )
    parts.append("</div>")
    return "".join(parts)


class QuizQuestionsBrowserWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("QuizQuestionsBrowserWidget")
        self.setStyleSheet(_PAGE_STYLE)
        self._rows: list[QuizQuestionRow] = []

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
        self._coverage_label = QLabel()
        self._coverage_label.setObjectName("coverageBadge")
        self._coverage_label.setWordWrap(True)
        deck_row.addWidget(self._deck_label)
        deck_row.addWidget(self._deck_combo, stretch=1)
        deck_row.addWidget(self._coverage_label)
        filter_layout.addLayout(deck_row)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(10)
        self._type_label = QLabel()
        self._type_filter = QComboBox()
        self._type_filter.setObjectName("filterTypeCombo")
        configure_single_line_combo(self._type_filter)
        self._type_filter.setMinimumWidth(160)
        self._type_filter.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._type_filter.currentIndexChanged.connect(self.refresh)
        self._status_label = QLabel()
        self._status_filter = QComboBox()
        self._status_filter.setObjectName("filterStatusCombo")
        configure_single_line_combo(self._status_filter)
        self._status_filter.setMinimumWidth(140)
        self._status_filter.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._status_filter.currentIndexChanged.connect(self.refresh)
        self._search_label = QLabel()
        self._search_field = QLineEdit()
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(250)
        self._refresh_timer.timeout.connect(self.refresh)
        self._search_field.textChanged.connect(self._schedule_refresh)
        filter_row.addWidget(self._type_label)
        filter_row.addWidget(self._type_filter)
        filter_row.addWidget(self._status_label)
        filter_row.addWidget(self._status_filter)
        filter_row.addWidget(self._search_label)
        filter_row.addWidget(self._search_field, stretch=1)
        filter_layout.addLayout(filter_row)
        layout.addWidget(self._filter_card)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self._refresh_btn = QPushButton()
        self._refresh_btn.setObjectName("btnSecondary")
        self._refresh_btn.clicked.connect(self.refresh)
        self._edit_btn = QPushButton()
        self._edit_btn.setObjectName("btnSecondary")
        self._edit_btn.clicked.connect(self._edit_selected)
        self._regen_btn = QPushButton()
        self._regen_btn.setObjectName("btnPrimary")
        self._regen_btn.clicked.connect(self._regen_selected)
        actions.addStretch()
        actions.addWidget(self._refresh_btn)
        actions.addWidget(self._edit_btn)
        actions.addWidget(self._regen_btn)
        layout.addLayout(actions)

        self._table_card = QFrame()
        self._table_card.setObjectName("tableCard")
        table_layout = QVBoxLayout(self._table_card)
        table_layout.setContentsMargins(0, 0, 0, 0)

        self._table = QTableWidget(0, 6)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.setAlternatingRowColors(False)
        self._table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        header = self._table.horizontalHeader()
        header.setMinimumSectionSize(48)
        header.setStretchLastSection(False)
        header.setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        for col in range(5):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        restore_table_columns(
            self._table,
            "learning",
            "quiz_questions",
            default_widths=_TABLE_WIDTHS,
        )
        bind_table_columns_persistence(self._table, "learning", "quiz_questions")
        self._table.itemSelectionChanged.connect(self._update_detail)
        self._table.cellDoubleClicked.connect(lambda _row, _col: self._edit_selected())
        table_layout.addWidget(self._table)
        layout.addWidget(self._table_card, stretch=1)

        self._preview_card = QFrame()
        self._preview_card.setObjectName("previewCard")
        preview_layout = QVBoxLayout(self._preview_card)
        preview_layout.setContentsMargins(12, 12, 12, 12)
        self._detail = QTextBrowser()
        self._detail.setOpenExternalLinks(False)
        self._detail.setMinimumHeight(140)
        self._detail.setMaximumHeight(220)
        preview_layout.addWidget(self._detail)
        layout.addWidget(self._preview_card)

        self.retranslate_ui()
        self._reload_filter_combos()

    def retranslate_ui(self) -> None:
        self._deck_label.setText(tr("learning.deck"))
        self._type_label.setText(tr("learning.quiz_questions_filter_type"))
        self._status_label.setText(tr("learning.quiz_questions_filter_status"))
        self._search_label.setText(tr("learning.quiz_questions_search"))
        self._search_field.setPlaceholderText(tr("learning.quiz_questions_search_hint"))
        self._refresh_btn.setText(tr("learning.quiz_refresh"))
        self._edit_btn.setText(tr("learning.quiz_questions_edit"))
        self._regen_btn.setText(tr("learning.quiz_questions_regenerate"))
        self._table.setHorizontalHeaderLabels(
            [
                tr("learning.quiz_questions_col_word").upper(),
                tr("learning.quiz_questions_col_type").upper(),
                tr("learning.quiz_questions_col_status").upper(),
                tr("learning.quiz_questions_col_prompt").upper(),
                tr("learning.quiz_questions_col_choices").upper(),
                tr("learning.quiz_questions_col_updated").upper(),
            ]
        )
        self._reload_filter_combos(preserve=True)

    def _reload_filter_combos(self, *, preserve: bool = False) -> None:
        type_current = self._type_filter.currentData() if preserve else None
        status_current = self._status_filter.currentData() if preserve else "all"

        self._type_filter.blockSignals(True)
        self._type_filter.clear()
        self._type_filter.addItem(tr("learning.quiz_questions_filter_all"), "")
        for qtype in learning.QUIZ_QUESTION_TYPES:
            self._type_filter.addItem(_question_type_label(qtype), qtype)
        if type_current is not None:
            index = self._type_filter.findData(type_current)
            if index >= 0:
                self._type_filter.setCurrentIndex(index)
        self._type_filter.blockSignals(False)

        self._status_filter.blockSignals(True)
        self._status_filter.clear()
        self._status_filter.addItem(tr("learning.quiz_questions_filter_all"), "all")
        self._status_filter.addItem(tr("learning.quiz_questions_status_active"), "active")
        self._status_filter.addItem(tr("learning.quiz_questions_status_failed"), "failed")
        index = self._status_filter.findData(status_current)
        if index >= 0:
            self._status_filter.setCurrentIndex(index)
        self._status_filter.blockSignals(False)

    def reload_decks(self) -> None:
        current = self._deck_combo.currentData()
        decks = learning.list_decks()
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

    def refresh(self) -> None:
        deck_id = self._deck_combo.currentData()
        if deck_id is None:
            self._rows = []
            self._populate_table()
            self._coverage_label.clear()
            return

        stats = learning.get_quiz_coverage(deck_id)
        failed = learning.count_failed_quiz_questions_for_deck(deck_id)
        self._coverage_label.setText(
            tr(
                "learning.quiz_questions_coverage",
                ready=stats.ready,
                eligible=stats.eligible,
                failed=failed,
            )
        )

        question_type = self._type_filter.currentData() or None
        status = self._status_filter.currentData() or "all"
        search = self._search_field.text().strip() or None
        self._rows = learning.list_quiz_questions(
            deck_id,
            question_type=question_type,
            status=status if status != "all" else None,
            search=search,
        )
        self._populate_table()

    def _populate_table(self) -> None:
        selected_id = self._selected_row_id()
        self._table.setRowCount(len(self._rows))
        for row_index, row in enumerate(self._rows):
            word_item = QTableWidgetItem(row.card_front)
            word_item.setData(Qt.ItemDataRole.UserRole, row.id)
            self._table.setItem(row_index, 0, word_item)
            self._table.setItem(row_index, 1, QTableWidgetItem(_question_type_label(row.question_type)))
            self._table.setItem(row_index, 2, QTableWidgetItem(_status_label(row.status)))
            self._table.setItem(row_index, 3, QTableWidgetItem(_truncate(row.prompt_text)))
            self._table.setItem(
                row_index,
                4,
                QTableWidgetItem(str(len(row.choices_pool))),
            )
            self._table.setItem(row_index, 5, QTableWidgetItem(row.updated_at))

        if selected_id is not None:
            for row_index in range(self._table.rowCount()):
                item = self._table.item(row_index, 0)
                if item and item.data(Qt.ItemDataRole.UserRole) == selected_id:
                    self._table.selectRow(row_index)
                    break
        self._update_detail()

    def _selected_row(self) -> QuizQuestionRow | None:
        row_index = self._table.currentRow()
        if row_index < 0 or row_index >= len(self._rows):
            return None
        return self._rows[row_index]

    def _selected_row_id(self) -> int | None:
        row = self._selected_row()
        return row.id if row else None

    def _update_detail(self) -> None:
        row = self._selected_row()
        if row is None:
            self._detail.clear()
            return
        self._detail.setHtml(_build_detail_html(row))

    def _edit_selected(self) -> None:
        row = self._selected_row()
        if row is None:
            return
        deck = learning.get_deck(row.deck_id)
        direction = deck.direction if deck else "ua-en"
        dialog = QuizQuestionEditDialog(row, direction=direction, parent=self)
        if dialog.exec():
            self.refresh()

    def _regen_selected(self) -> None:
        row = self._selected_row()
        if row is None:
            return
        dialog = QuizQuestionRegenDialog(row, parent=self)
        if dialog.exec() and dialog.result_row is not None:
            self.refresh()
