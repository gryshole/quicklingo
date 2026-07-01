from PySide6.QtCore import Qt, Signal, QDate, QTimer
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QFileDialog,
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
    QTextEdit,
    QVBoxLayout,
)

from quicklingo.config.loader import get_direction_label, get_directions
from quicklingo.db import history
from quicklingo.features import get_feature, is_enabled
from quicklingo.history.corpus_export import export_json, export_markdown
from quicklingo.history.meeting_export import export_transcript_markdown, export_transcript_text
from quicklingo.i18n import tr
from quicklingo.ui.qt_utils import reload_combo
from quicklingo.ui.table_styles import apply_data_table_style, style_cell_action_button
from quicklingo.ui.tag_wizard_dialog import TagWizardDialog
from quicklingo.ui.window_state import (
    bind_table_columns_persistence,
    restore_table_columns,
    restore_window_geometry,
    save_table_columns,
    save_window_geometry,
)


_HISTORY_TABLE_WIDTHS = [130, 85, 110, 100, 150, 90, 36, 36]


class HistoryWindow(QDialog):
    reopen_requested = Signal(str, str, str)
    add_to_deck_requested = Signal(str, str, str, str, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        restore_window_geometry(self, "history", default_width=820, default_height=580)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        self._summary_label = QLabel()
        self._summary_label.setWordWrap(True)

        self._search_label = QLabel()
        self._search_field = QLineEdit()
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(250)
        self._refresh_timer.timeout.connect(self.refresh)
        self._search_field.textChanged.connect(self._schedule_refresh)

        self._direction_filter = QComboBox()
        self._direction_filter.currentIndexChanged.connect(self.refresh)

        self._model_filter = QComboBox()
        self._model_filter.currentIndexChanged.connect(self.refresh)

        self._tag_filter = QComboBox()
        self._tag_filter.currentIndexChanged.connect(self.refresh)

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
        self._starred_only.setCheckable(True)
        self._starred_only.toggled.connect(self.refresh)

        self._export_btn = QPushButton()
        self._export_btn.clicked.connect(self._export_history)
        self._transcript_btn = QPushButton()
        self._transcript_btn.clicked.connect(self._export_transcript)
        self._edit_tags_btn = QPushButton()
        self._edit_tags_btn.clicked.connect(self._edit_selected_tags)
        self._tag_wizard_btn = QPushButton()
        self._tag_wizard_btn.clicked.connect(self._open_tag_wizard)
        self._refresh_btn = QPushButton()
        self._refresh_btn.clicked.connect(self.refresh)
        self._clear_btn = QPushButton()
        self._clear_btn.clicked.connect(self._clear_history)

        filter_row = QHBoxLayout()
        filter_row.addWidget(self._search_label)
        filter_row.addWidget(self._search_field, stretch=1)
        filter_row.addWidget(self._direction_filter)
        filter_row.addWidget(self._model_filter)
        filter_row.addWidget(self._tag_filter)

        date_row = QHBoxLayout()
        self._date_from_label = QLabel()
        self._date_to_label = QLabel()
        date_row.addWidget(self._date_from_label)
        date_row.addWidget(self._date_from)
        date_row.addWidget(self._date_to_label)
        date_row.addWidget(self._date_to)
        date_row.addWidget(self._starred_only)
        date_row.addStretch()

        top_row = QHBoxLayout()
        top_row.addWidget(self._summary_label, stretch=1)
        top_row.addWidget(self._transcript_btn)
        top_row.addWidget(self._export_btn)
        top_row.addWidget(self._edit_tags_btn)
        top_row.addWidget(self._tag_wizard_btn)
        top_row.addWidget(self._refresh_btn)
        top_row.addWidget(self._clear_btn)

        self._table = QTableWidget(0, 8)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        apply_data_table_style(self._table)

        header = self._table.horizontalHeader()
        header.setMinimumSectionSize(48)
        header.setStretchLastSection(False)
        for col in range(7):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)
        restore_table_columns(
            self._table,
            "history",
            "main",
            default_widths=_HISTORY_TABLE_WIDTHS,
        )
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)
        bind_table_columns_persistence(self._table, "history", "main")

        self._table.itemSelectionChanged.connect(self._on_row_selected)

        action_row = QHBoxLayout()
        self._reopen_btn = QPushButton()
        self._reopen_btn.clicked.connect(self._reopen_selected)
        action_row.addWidget(self._reopen_btn)
        action_row.addStretch()

        self._detail_label = QLabel()
        self._detail_field = QTextEdit()
        self._detail_field.setReadOnly(True)
        self._detail_field.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._detail_field.customContextMenuRequested.connect(self._detail_context_menu)

        layout.addLayout(top_row)
        layout.addLayout(filter_row)
        layout.addLayout(date_row)
        layout.addWidget(self._table, stretch=2)
        layout.addLayout(action_row)
        layout.addWidget(self._detail_label)
        layout.addWidget(self._detail_field, stretch=1)

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
                tr("history.col_date"),
                tr("history.col_direction"),
                tr("history.col_query"),
                tr("history.col_model"),
                tr("history.col_result"),
                tr("history.col_tags"),
                tr("history.col_star"),
                "",
            ]
        )
        self._detail_label.setText(tr("history.detail_label"))
        self._detail_field.setPlaceholderText(tr("history.detail_placeholder"))
        self._reload_direction_filter()
        self._reload_model_filter()
        self._reload_tag_filter()
        self.refresh()

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
        self._table.setColumnHidden(6, not show_phrasebook)

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
                        item.setTextAlignment(Qt.AlignmentFlag.AlignTop)
                    self._table.setItem(row_idx, col, item)

                if is_enabled("learning.phrasebook"):
                    star_btn = QPushButton("★" if record.is_starred else "☆")
                    star_btn.setFixedWidth(32)
                    star_btn.setToolTip(tr("history.star_tooltip"))
                    style_cell_action_button(star_btn)
                    star_btn.clicked.connect(
                        lambda _checked=False, rid=record.id, starred=record.is_starred: self._toggle_star(
                            rid, starred
                        )
                    )
                    self._table.setCellWidget(row_idx, 6, star_btn)

                delete_btn = QPushButton("✕")
                delete_btn.setToolTip(tr("history.delete_tooltip"))
                delete_btn.setFixedWidth(32)
                style_cell_action_button(delete_btn)
                delete_btn.clicked.connect(
                    lambda _checked=False, rid=record.id: self._delete_record(rid)
                )
                self._table.setCellWidget(row_idx, 7, delete_btn)

            if self._records:
                self._table.selectRow(0)
        finally:
            self._table.blockSignals(False)

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
        self._detail_field.setPlainText(record.result_text)

    def closeEvent(self, event: QCloseEvent) -> None:
        save_table_columns(self._table, "history", "main")
        save_window_geometry(self, "history")
        super().closeEvent(event)


def _preview(text: str, max_len: int = 120) -> str:
    one_line = " ".join(text.split())
    if len(one_line) <= max_len:
        return one_line
    return one_line[: max_len - 1] + "…"
