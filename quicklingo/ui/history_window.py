from __future__ import annotations

import html
import re

from PySide6.QtCore import Qt, Signal, QDate, QTimer
from PySide6.QtGui import QAction, QBrush, QCloseEvent, QColor, QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from quicklingo.config.loader import get_direction_label, get_directions
from quicklingo.db import history
from quicklingo.features import get_feature, is_enabled
from quicklingo.history.corpus_export import export_json, export_markdown
from quicklingo.history.meeting_export import export_transcript_markdown, export_transcript_text
from quicklingo.i18n import tr
from quicklingo.ui.qt_utils import configure_single_line_combo, reload_combo
from quicklingo.ui.tag_wizard_dialog import TagWizardDialog
from quicklingo.ui.window_state import (
    bind_table_columns_persistence,
    restore_table_columns,
    restore_window_geometry,
    save_table_columns,
    save_window_geometry,
)

_HISTORY_TABLE_WIDTHS = [130, 85, 110, 100, 150, 90, 44, 48]
_COL_STAR = 6
_COL_DELETE = 7
_STAR_COL_WIDTH = 44
_DELETE_COL_WIDTH = 48

_PAGE_STYLE = """
HistoryWindow {
    background-color: #f1f5f9;
}
QLabel#summaryLabel {
    color: #475569;
    font-size: 13px;
    font-weight: 500;
}
QFrame#filterCard {
    background-color: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
}
QFrame#filterCard QLabel {
    color: #64748b;
    font-size: 12px;
}
QFrame#filterCard QComboBox,
QFrame#filterCard QLineEdit,
QFrame#filterCard QDateEdit {
    min-height: 30px;
    max-height: 30px;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    padding: 4px 8px;
    background-color: #ffffff;
    color: #1e293b;
    font-size: 13px;
}
QFrame#filterCard QComboBox:hover,
QFrame#filterCard QLineEdit:hover,
QFrame#filterCard QDateEdit:hover {
    border-color: #94a3b8;
}
QFrame#filterCard QComboBox:focus,
QFrame#filterCard QLineEdit:focus,
QFrame#filterCard QDateEdit:focus {
    border-color: #3b82f6;
}
QFrame#filterCard QComboBox::drop-down {
    border: none;
    width: 22px;
}
QPushButton#btnStarredToggle {
    min-height: 30px;
    background-color: #ffffff;
    color: #475569;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    padding: 4px 12px;
    font-size: 13px;
}
QPushButton#btnStarredToggle:hover {
    background-color: #f8fafc;
    border-color: #94a3b8;
}
QPushButton#btnStarredToggle:checked {
    background-color: #eff6ff;
    border-color: #3b82f6;
    color: #1d4ed8;
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
    margin-left: 8px;
}
QPushButton#btnDanger:hover:enabled {
    background-color: #fef2f2;
    border-color: #fca5a5;
    color: #dc2626;
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
    padding: 8px 10px;
    border: none;
    border-bottom: 1px solid #f3f4f6;
    color: #334155;
}
QFrame#tableCard QTableWidget::item:selected {
    background-color: #eff6ff;
    color: #1e293b;
}
QFrame#tableCard QHeaderView::section {
    background-color: #f8fafc;
    color: #64748b;
    font-size: 11px;
    font-weight: 600;
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
    border-radius: 12px;
}
QLabel#previewTitle {
    color: #64748b;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.03em;
    text-transform: uppercase;
}
QFrame#previewCard QTextBrowser {
    background: transparent;
    border: none;
    padding: 8px 12px 8px 16px;
}
"""


class HistoryWindow(QDialog):
    reopen_requested = Signal(str, str, str)
    add_to_deck_requested = Signal(str, str, str, str, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("HistoryWindow")
        self.setStyleSheet(_PAGE_STYLE)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        restore_window_geometry(self, "history", default_width=860, default_height=620)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        toolbar_row = QHBoxLayout()
        toolbar_row.setSpacing(8)
        self._summary_label = QLabel()
        self._summary_label.setObjectName("summaryLabel")
        self._summary_label.setWordWrap(True)
        toolbar_row.addWidget(self._summary_label, stretch=1)

        self._refresh_btn = QPushButton()
        self._refresh_btn.setObjectName("btnPrimary")
        self._refresh_btn.clicked.connect(self.refresh)
        self._export_btn = QPushButton()
        self._export_btn.setObjectName("btnSecondary")
        self._export_btn.clicked.connect(self._export_history)
        self._transcript_btn = QPushButton()
        self._transcript_btn.setObjectName("btnSecondary")
        self._transcript_btn.clicked.connect(self._export_transcript)
        self._edit_tags_btn = QPushButton()
        self._edit_tags_btn.setObjectName("btnSecondary")
        self._edit_tags_btn.clicked.connect(self._edit_selected_tags)
        self._tag_wizard_btn = QPushButton()
        self._tag_wizard_btn.setObjectName("btnSecondary")
        self._tag_wizard_btn.clicked.connect(self._open_tag_wizard)
        self._clear_btn = QPushButton()
        self._clear_btn.setObjectName("btnDanger")
        self._clear_btn.clicked.connect(self._clear_history)

        for btn in (
            self._refresh_btn,
            self._export_btn,
            self._transcript_btn,
            self._edit_tags_btn,
            self._tag_wizard_btn,
        ):
            toolbar_row.addWidget(btn)
        toolbar_row.addWidget(self._clear_btn)
        layout.addLayout(toolbar_row)

        self._filter_card = QFrame()
        self._filter_card.setObjectName("filterCard")
        filter_layout = QVBoxLayout(self._filter_card)
        filter_layout.setContentsMargins(12, 12, 12, 12)
        filter_layout.setSpacing(10)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(10)
        self._search_label = QLabel()
        self._search_field = QLineEdit()
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(250)
        self._refresh_timer.timeout.connect(self.refresh)
        self._search_field.textChanged.connect(self._schedule_refresh)
        self._direction_filter = QComboBox()
        configure_single_line_combo(self._direction_filter)
        self._direction_filter.setMinimumWidth(130)
        self._direction_filter.currentIndexChanged.connect(self.refresh)
        self._model_filter = QComboBox()
        configure_single_line_combo(self._model_filter)
        self._model_filter.setMinimumWidth(130)
        self._model_filter.currentIndexChanged.connect(self.refresh)
        self._tag_filter = QComboBox()
        configure_single_line_combo(self._tag_filter)
        self._tag_filter.setMinimumWidth(110)
        self._tag_filter.currentIndexChanged.connect(self.refresh)
        filter_row.addWidget(self._search_label)
        filter_row.addWidget(self._search_field, stretch=1)
        filter_row.addWidget(self._direction_filter)
        filter_row.addWidget(self._model_filter)
        filter_row.addWidget(self._tag_filter)
        filter_layout.addLayout(filter_row)

        date_row = QHBoxLayout()
        date_row.setSpacing(10)
        self._date_from_label = QLabel()
        self._date_to_label = QLabel()
        self._date_from = QDateEdit()
        self._date_from.setCalendarPopup(True)
        self._date_from.setSpecialValueText(tr("history.date_any"))
        self._date_from.setMinimumDate(QDate(2000, 1, 1))
        self._date_from.setDate(self._date_from.minimumDate())
        self._date_from.dateChanged.connect(self.refresh)
        self._date_to = QDateEdit()
        self._date_to.setCalendarPopup(True)
        self._date_to.setSpecialValueText(tr("history.date_any"))
        self._date_to.setMinimumDate(QDate(2000, 1, 1))
        self._date_to.setDate(self._date_to.minimumDate())
        self._date_to.dateChanged.connect(self.refresh)
        self._starred_only = QPushButton()
        self._starred_only.setObjectName("btnStarredToggle")
        self._starred_only.setCheckable(True)
        self._starred_only.toggled.connect(self.refresh)
        date_row.addWidget(self._date_from_label)
        date_row.addWidget(self._date_from)
        date_row.addWidget(self._date_to_label)
        date_row.addWidget(self._date_to)
        date_row.addWidget(self._starred_only)
        date_row.addStretch()
        filter_layout.addLayout(date_row)
        layout.addWidget(self._filter_card)

        self._table_card = QFrame()
        self._table_card.setObjectName("tableCard")
        table_layout = QVBoxLayout(self._table_card)
        table_layout.setContentsMargins(0, 0, 0, 0)

        self._table = QTableWidget(0, 8)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.setAlternatingRowColors(False)
        header = self._table.horizontalHeader()
        header.setMinimumSectionSize(32)
        header.setStretchLastSection(False)
        header.setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        for col in range(_COL_STAR):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
        restore_table_columns(
            self._table,
            "history",
            "main",
            default_widths=_HISTORY_TABLE_WIDTHS,
        )
        self._apply_action_column_widths()
        bind_table_columns_persistence(self._table, "history", "main")
        header.sectionResized.connect(self._on_header_section_resized)
        self._table.cellClicked.connect(self._on_action_cell_clicked)
        self._table.itemSelectionChanged.connect(self._on_row_selected)
        table_layout.addWidget(self._table)
        layout.addWidget(self._table_card, stretch=2)

        self._preview_card = QFrame()
        self._preview_card.setObjectName("previewCard")
        preview_layout = QVBoxLayout(self._preview_card)
        preview_layout.setContentsMargins(14, 14, 14, 14)
        preview_layout.setSpacing(10)

        preview_header = QHBoxLayout()
        preview_header.setSpacing(8)
        self._detail_label = QLabel()
        self._detail_label.setObjectName("previewTitle")
        self._reopen_btn = QPushButton()
        self._reopen_btn.setObjectName("btnSecondary")
        self._reopen_btn.clicked.connect(self._reopen_selected)
        preview_header.addWidget(self._detail_label)
        preview_header.addStretch()
        preview_header.addWidget(self._reopen_btn)
        preview_layout.addLayout(preview_header)

        self._detail_field = QTextBrowser()
        self._detail_field.setOpenExternalLinks(False)
        self._detail_field.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._detail_field.customContextMenuRequested.connect(self._detail_context_menu)
        preview_layout.addWidget(self._detail_field, stretch=1)
        layout.addWidget(self._preview_card, stretch=1)

        self._records: list[history.TranslationRecord] = []
        self.retranslate_ui()
        self.refresh()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(tr("history.title"))
        self._refresh_btn.setText(tr("history.refresh"))
        self._clear_btn.setText(tr("history.clear"))
        self._export_btn.setText(tr("history.export"))
        self._transcript_btn.setText(tr("history.export_transcript"))
        self._edit_tags_btn.setText(tr("history.edit_tags"))
        self._tag_wizard_btn.setText(tr("history.tag_wizard"))
        self._search_label.setText(tr("history.search_label"))
        self._search_field.setPlaceholderText(tr("history.search_placeholder"))
        self._starred_only.setText(tr("history.starred_only"))
        self._date_from_label.setText(tr("history.date_from"))
        self._date_to_label.setText(tr("history.date_to"))
        self._reopen_btn.setText(tr("history.reopen"))
        self._table.setHorizontalHeaderLabels(
            [
                tr("history.col_date").upper(),
                tr("history.col_direction").upper(),
                tr("history.col_query").upper(),
                tr("history.col_model").upper(),
                tr("history.col_result").upper(),
                tr("history.col_tags").upper(),
                tr("history.col_star").upper(),
                "",
            ]
        )
        self._detail_label.setText(tr("history.detail_label"))
        self._reload_direction_filter()
        self._reload_model_filter()
        self._reload_tag_filter()
        self.refresh()

    def _apply_action_column_widths(self) -> None:
        header = self._table.horizontalHeader()
        header.blockSignals(True)
        header.setSectionResizeMode(_COL_STAR, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(_COL_DELETE, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(_COL_STAR, _STAR_COL_WIDTH)
        self._table.setColumnWidth(_COL_DELETE, _DELETE_COL_WIDTH)
        header.blockSignals(False)

    def _on_header_section_resized(self, logical_index: int, _old: int, _new: int) -> None:
        if logical_index in (_COL_STAR, _COL_DELETE):
            QTimer.singleShot(0, self._apply_action_column_widths)

    def _on_action_cell_clicked(self, row: int, column: int) -> None:
        if row < 0 or row >= len(self._records):
            return
        record = self._records[row]
        if column == _COL_STAR and is_enabled("learning.phrasebook"):
            self._toggle_star(record.id, record.is_starred)
        elif column == _COL_DELETE:
            self._delete_record(record.id)

    def _reload_direction_filter(self) -> None:
        reload_combo(
            self._direction_filter,
            [("", tr("history.filter_all_directions"))]
            + [(d.id, d.label) for d in get_directions()],
            current_data=self._direction_filter.currentData(),
        )

    def _reload_model_filter(self) -> None:
        reload_combo(
            self._model_filter,
            [("", tr("history.filter_all_models"))]
            + [(model, model) for model in history.get_distinct_models()],
            current_data=self._model_filter.currentData(),
        )

    def _reload_tag_filter(self) -> None:
        tag_items: list[tuple[str, str]] = [("", tr("history.filter_all_tags"))]
        if is_enabled("history.tags"):
            tag_items.extend((tag, tag) for tag in history.get_distinct_tags())
        reload_combo(
            self._tag_filter,
            tag_items,
            current_data=self._tag_filter.currentData(),
        )

    def _apply_feature_visibility(self) -> None:
        show_search = is_enabled("history.search")
        show_filters = is_enabled("history.filters")
        show_tags = is_enabled("history.tags")
        show_export = is_enabled("history.export")
        show_phrasebook = is_enabled("learning.phrasebook")
        show_transcript = is_enabled("history.meeting_transcript")
        self._filter_card.setVisible(show_search or show_filters)
        self._search_label.setVisible(show_search)
        self._search_field.setVisible(show_search)
        self._direction_filter.setVisible(show_filters)
        self._model_filter.setVisible(show_filters)
        self._tag_filter.setVisible(show_filters and show_tags)
        self._date_from_label.setVisible(show_filters)
        self._date_from.setVisible(show_filters)
        self._date_to_label.setVisible(show_filters)
        self._date_to.setVisible(show_filters)
        self._starred_only.setVisible(show_filters and show_phrasebook)
        self._export_btn.setVisible(show_export)
        self._transcript_btn.setVisible(show_transcript)
        self._edit_tags_btn.setVisible(show_tags)
        self._tag_wizard_btn.setVisible(show_tags)
        self._table.setColumnHidden(5, not show_tags)
        self._table.setColumnHidden(_COL_STAR, not show_phrasebook)
        self._apply_action_column_widths()

    def _filter_dates(self) -> tuple[str | None, str | None]:
        date_from = None
        date_to = None
        if self._date_from.date() != self._date_from.minimumDate():
            date_from = self._date_from.date().toString("yyyy-MM-dd")
        if self._date_to.date() != self._date_to.minimumDate():
            date_to = self._date_to.date().toString("yyyy-MM-dd")
        return date_from, date_to

    def _schedule_refresh(self) -> None:
        self._refresh_timer.start()

    def refresh(self) -> None:
        self._apply_feature_visibility()
        stats = history.get_translation_stats()
        query = self._search_field.text().strip() if is_enabled("history.search") else ""
        direction = None
        model = None
        tag = None
        date_from = None
        date_to = None
        if is_enabled("history.filters"):
            direction = self._direction_filter.currentData() or None
            model = self._model_filter.currentData() or None
            if is_enabled("history.tags"):
                tag = self._tag_filter.currentData() or None
            date_from, date_to = self._filter_dates()
        starred_only = (
            is_enabled("learning.phrasebook")
            and is_enabled("history.filters")
            and self._starred_only.isChecked()
        )
        self._records = history.search_records(
            query=query,
            direction=direction,
            model=model,
            tag=tag,
            date_from=date_from,
            date_to=date_to,
            starred_only=starred_only,
        )
        shown = len(self._records)

        summary = tr(
            "history.summary",
            total=stats["total"],
            ua_en=stats["ua_en"],
            en_ua=stats["en_ua"],
        )
        if shown < stats["total"]:
            summary += tr("history.summary_shown", shown=shown)
        self._summary_label.setText(summary)
        self._detail_field.clear()

        self._table.blockSignals(True)
        try:
            self._table.setRowCount(0)
            for row_idx, record in enumerate(self._records):
                self._table.insertRow(row_idx)
                values = [
                    record.created_at,
                    get_direction_label(record.direction),
                    record.source_text,
                    record.model,
                    _preview(record.result_text),
                    record.tags,
                ]
                for col, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    item.setToolTip(value if col != 4 else record.result_text)
                    if col in (0, 1, 3, 5):
                        item.setTextAlignment(
                            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                        )
                    self._table.setItem(row_idx, col, item)

                if is_enabled("learning.phrasebook"):
                    self._table.setItem(row_idx, _COL_STAR, _make_star_item(record.is_starred))

                self._table.setItem(row_idx, _COL_DELETE, _make_delete_item())

            if self._records:
                self._table.selectRow(0)
        finally:
            self._table.blockSignals(False)

        self._apply_action_column_widths()
        self._on_row_selected()

    def _edit_selected_tags(self) -> None:
        if not is_enabled("history.tags"):
            return
        record = self._selected_record()
        if record is None:
            return
        text, ok = QInputDialog.getText(
            self,
            tr("history.edit_tags_title"),
            tr("history.edit_tags_prompt"),
            text=record.tags,
        )
        if not ok:
            return
        tags = [part.strip() for part in text.split(",") if part.strip()]
        history.set_tags(record.id, tags)
        self._reload_tag_filter()
        self.refresh()

    def _selected_record_ids(self) -> list[int]:
        rows = self._table.selectionModel().selectedRows()
        ids: list[int] = []
        for index in rows:
            row = index.row()
            if 0 <= row < len(self._records):
                ids.append(self._records[row].id)
        return ids

    def _open_tag_wizard(self) -> None:
        if not is_enabled("history.tags"):
            return
        if not self._records:
            return
        selected_ids = self._selected_record_ids()
        dialog = TagWizardDialog(
            self,
            visible_count=len(self._records),
            selected_count=len(selected_ids),
            known_tags=history.get_distinct_tags(),
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        tags = dialog.parsed_tags()
        action = dialog.action_key()
        if action in ("add", "replace") and not tags:
            return
        if action == "remove" and not tags:
            return
        target_ids = selected_ids if dialog.use_selected_scope() else [r.id for r in self._records]
        if not target_ids:
            return
        if action == "add":
            updated = history.bulk_apply_tags(target_ids, add=tags)
        elif action == "replace":
            updated = history.bulk_apply_tags(target_ids, replace=tags)
        else:
            updated = history.bulk_apply_tags(target_ids, remove=tags)
        QMessageBox.information(
            self,
            tr("history.tag_wizard_title"),
            tr("history.bulk_tags_done", count=updated),
        )
        self._reload_tag_filter()
        self.refresh()

    def _detail_context_menu(self, pos) -> None:
        if not is_enabled("learning.extract_vocab"):
            return
        cursor = self._detail_field.textCursor()
        selected = cursor.selectedText().strip()
        if not selected:
            return
        menu = QMenu(self)
        action = menu.addAction(tr("history.add_to_deck"))
        chosen = menu.exec(self._detail_field.mapToGlobal(pos))
        if chosen != action:
            return
        record = self._selected_record()
        if record is None:
            return
        tag = history.parse_tags(record.tags)[0] if record.tags else ""
        self.add_to_deck_requested.emit(
            selected,
            record.source_text,
            record.direction,
            tag,
            record.result_text,
        )

    def _toggle_star(self, record_id: int, starred: bool) -> None:
        if not is_enabled("learning.phrasebook"):
            return
        history.set_starred(record_id, not starred)
        self.refresh()

    def _export_history(self) -> None:
        if not is_enabled("history.export"):
            return
        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            tr("history.export_title"),
            "quicklingo-history.csv",
            tr("history.export_formats"),
        )
        if not path:
            return
        records = self._records
        lower = path.lower()
        if selected_filter.startswith("JSON") or lower.endswith(".json"):
            content = export_json(records)
            newline = "\n"
        elif selected_filter.startswith("Markdown") or lower.endswith(".md"):
            content = export_markdown(records)
            newline = "\n"
        else:
            content = history.export_csv(records)
            newline = ""
        with open(path, "w", encoding="utf-8", newline=newline) as handle:
            handle.write(content)

    def _export_transcript(self) -> None:
        if not is_enabled("history.meeting_transcript"):
            return
        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            tr("history.export_transcript_title"),
            "quicklingo-transcript.md",
            "Markdown (*.md);;Text (*.txt)",
        )
        if not path:
            return
        gap = int(get_feature("history.meeting_transcript").get("session_gap_min", 15))
        if selected_filter.startswith("Text") or path.endswith(".txt"):
            content = export_transcript_text(self._records, gap_minutes=gap)
        else:
            content = export_transcript_markdown(self._records, gap_minutes=gap)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)

    def _reopen_selected(self) -> None:
        record = self._selected_record()
        if record is None:
            return
        profile_id = record.profile_id or "detailed"
        self.reopen_requested.emit(record.source_text, record.direction, profile_id)
        self.accept()

    def _selected_record(self) -> history.TranslationRecord | None:
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            return None
        row = rows[0].row()
        if row < 0 or row >= len(self._records):
            return None
        return self._records[row]

    def _delete_record(self, record_id: int) -> None:
        if not history.delete_by_id(record_id):
            return
        self.refresh()

    def _clear_history(self) -> None:
        stats = history.get_translation_stats()
        if stats["total"] == 0:
            return
        answer = QMessageBox.question(
            self,
            tr("history.clear_title"),
            tr("history.clear_message"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        history.clear_all()
        self.refresh()

    def _on_row_selected(self) -> None:
        record = self._selected_record()
        if record is None:
            self._detail_field.clear()
            return
        self._detail_field.setHtml(_format_result_html(record.result_text))

    def closeEvent(self, event: QCloseEvent) -> None:
        self._apply_action_column_widths()
        save_table_columns(self._table, "history", "main")
        save_window_geometry(self, "history")
        super().closeEvent(event)


def _action_cell_font() -> QFont:
    font = QFont()
    font.setPointSize(13)
    font.setBold(True)
    return font


def _make_star_item(starred: bool) -> QTableWidgetItem:
    item = QTableWidgetItem("★" if starred else "☆")
    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
    item.setToolTip(tr("history.star_tooltip"))
    item.setFont(_action_cell_font())
    item.setForeground(QBrush(QColor("#f59e0b" if starred else "#94a3b8")))
    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
    return item


def _make_delete_item() -> QTableWidgetItem:
    item = QTableWidgetItem("\u2715")
    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
    item.setToolTip(tr("history.delete_tooltip"))
    item.setFont(_action_cell_font())
    item.setForeground(QBrush(QColor("#64748b")))
    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
    return item


def _format_result_html(text: str) -> str:
    if not (text or "").strip():
        return ""
    parts = [
        '<div style="font-family: Segoe UI, sans-serif; color: #334155; line-height: 1.55; '
        'padding: 4px 8px 4px 4px;">'
    ]
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            parts.append("<br>")
            continue
        if re.match(r"^[-─—]{3,}$", stripped):
            parts.append(
                '<hr style="border: 0; border-top: 1px solid #e2e8f0; margin: 12px 0;">'
            )
            continue
        numbered = re.match(r"^\[(\d+)\]\s*(.+)$", stripped)
        if numbered:
            idx, title = numbered.group(1), html.escape(numbered.group(2))
            parts.append(
                f'<h3 style="margin: 14px 0 4px 0; font-size: 15px; font-weight: 600; '
                f'color: #1e40af;">[{idx}] {title}</h3>'
            )
            continue
        if stripped.startswith("—") or stripped.startswith("-"):
            body = stripped.lstrip("—- ").strip()
            parts.append(
                f'<p style="margin: 0 0 10px 14px; color: #64748b; font-size: 13px;">'
                f"— {html.escape(body)}</p>"
            )
            continue
        if stripped.lower().startswith("example:"):
            example_text = html.escape(stripped.split(":", 1)[1].strip())
            parts.append(
                f'<p style="margin: 12px 0 4px 0; font-size: 13px; color: #475569;">'
                f'<b style="color: #334155;">Example:</b> {example_text}</p>'
            )
            continue
        parts.append(
            f'<p style="margin: 4px 0; font-size: 13px; color: #475569;">'
            f"{html.escape(stripped)}</p>"
        )
    parts.append("</div>")
    return "".join(parts)


def _preview(text: str, max_len: int = 120) -> str:
    one_line = " ".join(text.split())
    if len(one_line) <= max_len:
        return one_line
    return one_line[: max_len - 1] + "…"
