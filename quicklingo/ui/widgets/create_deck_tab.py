from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from quicklingo.config.loader import get_directions, resolve_learning_direction
from quicklingo.db import history
from quicklingo.features import get_feature, is_enabled
from quicklingo.i18n import tr
from quicklingo.learning.corpus_analysis import select_candidates
from quicklingo.learning.corpus_tags import UNTAGGED_SENTINEL
from quicklingo.learning.deck_corpus import pending_corpus_records
from quicklingo.learning.difficult_words import compute_difficult_words
from quicklingo.providers.registry import get_model_by_index, get_model_entries
from quicklingo.ui.app_theme import SETTINGS_FONT_PT
from quicklingo.ui.qt_utils import configure_single_line_combo, reload_combo
from quicklingo.ui.widgets.learning_empty_state import LearningEmptyStateWidget
from quicklingo.workers.corpus_analysis_worker import CorpusAnalysisWorker

_PREVIEW_ROW_LIMIT = 20
_FORM_ACTION_INSET = 12
_PREVIEW_BODY_INSET = 6

_CREATE_DECK_TAB_STYLE = f"""
CreateDeckTabWidget {{
    background-color: transparent;
}}
QFrame#createDeckSourceCard,
QFrame#createDeckPreviewCard {{
    background-color: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
}}
QFrame#createDeckSourceCard,
QFrame#createDeckPreviewCard {{
    padding: 4px;
}}
CreateDeckTabWidget QLabel#sectionTitle {{
    color: #1e293b;
    font-size: 13px;
    font-weight: 600;
}}
CreateDeckTabWidget QLabel#fieldLabel {{
    color: #64748b;
    font-size: 12px;
}}
CreateDeckTabWidget QLabel#statsBadge {{
    color: #475569;
    font-size: 12px;
    background-color: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    padding: 6px 12px;
}}
CreateDeckTabWidget QLabel#sourceHint,
CreateDeckTabWidget QLabel#createDeckHint {{
    color: #64748b;
    font-size: 11px;
}}
CreateDeckTabWidget QLabel#statusLabel {{
    color: #64748b;
    font-size: 12px;
}}
CreateDeckTabWidget QComboBox {{
    min-height: 32px;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    padding: 4px 10px;
    background-color: #ffffff;
    color: #1e293b;
    font-size: {SETTINGS_FONT_PT}pt;
}}
CreateDeckTabWidget QComboBox:hover {{
    border-color: #94a3b8;
}}
CreateDeckTabWidget QComboBox:focus {{
    border-color: #3b82f6;
}}
CreateDeckTabWidget QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
CreateDeckTabWidget QComboBox QAbstractItemView {{
    border: 1px solid #d1d5db;
    border-radius: 6px;
    background-color: #ffffff;
    font-size: {SETTINGS_FONT_PT}pt;
    selection-background-color: #eff6ff;
    selection-color: #1e293b;
}}
CreateDeckTabWidget QComboBox QLineEdit {{
    border: none;
    background: transparent;
    padding: 0;
    font-size: {SETTINGS_FONT_PT}pt;
}}
QPushButton#btnPrimary {{
    background-color: #3b82f6;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 8px 20px;
    font-size: 13px;
    font-weight: 600;
    min-height: 36px;
}}
QPushButton#btnPrimary:hover:enabled {{
    background-color: #2563eb;
}}
QPushButton#btnPrimary:disabled {{
    background-color: #94a3b8;
    color: #e2e8f0;
}}
QPushButton#btnSecondary {{
    background-color: #ffffff;
    color: #1e293b;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    padding: 6px 14px;
    font-size: 13px;
    min-height: 32px;
}}
QPushButton#btnSecondary:hover:enabled {{
    background-color: #f8fafc;
    border-color: #94a3b8;
}}
QFrame#createDeckPreviewCard QTableWidget {{
    background-color: #ffffff;
    border: none;
    outline: none;
    gridline-color: transparent;
    selection-background-color: #eff6ff;
    selection-color: #1e293b;
}}
QFrame#createDeckPreviewCard QTableWidget::item {{
    padding: 6px 8px;
    border: none;
    border-bottom: 1px solid #f1f5f9;
    color: #334155;
}}
QFrame#createDeckPreviewCard QHeaderView::section {{
    background-color: #f8fafc;
    color: #64748b;
    font-size: 11px;
    font-weight: 600;
    padding: 10px 8px;
    border: none;
    border-bottom: 1px solid #e5e7eb;
    border-right: 1px solid #f1f5f9;
}}
QFrame#createDeckPreviewCard QHeaderView::section:last {{
    border-right: none;
}}
QProgressBar#createDeckProgress {{
    border: none;
    background-color: #e2e8f0;
    border-radius: 3px;
    max-height: 4px;
    min-height: 4px;
}}
QProgressBar#createDeckProgress::chunk {{
    background-color: #3b82f6;
    border-radius: 3px;
}}
"""


def _reason_label(reason: str) -> str:
    key = f"learning.candidate_reason_{reason}"
    translated = tr(key)
    return translated if translated != key else reason


class CreateDeckTabWidget(QWidget):
    deck_created = Signal(int, str)
    open_main_window = Signal()

    def __init__(self, parent=None, *, standalone: bool = False) -> None:
        super().__init__(parent)
        self.setObjectName("CreateDeckTabWidget")
        self.setStyleSheet(_CREATE_DECK_TAB_STYLE)
        self._standalone = standalone
        self._worker: CorpusAnalysisWorker | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 4, 0, 0)
        root.setSpacing(12)

        self._empty = LearningEmptyStateWidget()
        self._empty.action_requested.connect(self.open_main_window.emit)
        root.addWidget(self._empty)

        self._form_host = QWidget()
        form_layout = QVBoxLayout(self._form_host)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(12)

        source_card = QFrame()
        source_card.setObjectName("createDeckSourceCard")
        source_layout = QVBoxLayout(source_card)
        source_layout.setContentsMargins(12, 12, 12, 12)
        source_layout.setSpacing(10)

        self._source_title = QLabel()
        self._source_title.setObjectName("sectionTitle")
        self._source_hint = QLabel()
        self._source_hint.setObjectName("sourceHint")
        self._source_hint.setWordWrap(True)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)
        self._tag_label = QLabel()
        self._tag_label.setObjectName("fieldLabel")
        self._tag_combo = QComboBox()
        configure_single_line_combo(self._tag_combo)
        self._direction_label = QLabel()
        self._direction_label.setObjectName("fieldLabel")
        self._direction_combo = QComboBox()
        configure_single_line_combo(self._direction_combo)
        self._init_direction_combo()
        self._model_label = QLabel()
        self._model_label.setObjectName("fieldLabel")
        self._model_combo = QComboBox()
        configure_single_line_combo(self._model_combo)
        grid.addWidget(self._tag_label, 0, 0)
        grid.addWidget(self._tag_combo, 0, 1)
        grid.addWidget(self._direction_label, 1, 0)
        grid.addWidget(self._direction_combo, 1, 1)
        grid.addWidget(self._model_label, 2, 0)
        grid.addWidget(self._model_combo, 2, 1)
        grid.setColumnStretch(1, 1)

        source_layout.addWidget(self._source_title)
        source_layout.addWidget(self._source_hint)
        source_layout.addLayout(grid)
        form_layout.addWidget(source_card)

        preview_card = QFrame()
        preview_card.setObjectName("createDeckPreviewCard")
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(12, 12, 12, 12)
        preview_layout.setSpacing(8)

        preview_header = QHBoxLayout()
        self._preview_title = QLabel()
        self._preview_title.setObjectName("sectionTitle")
        preview_header.addWidget(self._preview_title)
        preview_header.addStretch()
        self._stats_badge = QLabel()
        self._stats_badge.setObjectName("statsBadge")
        preview_header.addWidget(self._stats_badge)
        preview_layout.addLayout(preview_header)

        preview_body = QVBoxLayout()
        preview_body.setContentsMargins(_PREVIEW_BODY_INSET, 0, 0, 0)
        preview_body.setSpacing(8)
        self._starred_only = QCheckBox()
        preview_body.addWidget(self._starred_only)

        self._preview_table = QTableWidget(0, 3)
        self._preview_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._preview_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._preview_table.verticalHeader().setVisible(False)
        self._preview_table.setShowGrid(False)
        self._preview_table.setAlternatingRowColors(False)
        header = self._preview_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        preview_body.addWidget(self._preview_table, stretch=1)
        preview_layout.addLayout(preview_body, stretch=1)
        form_layout.addWidget(preview_card, stretch=1)

        action_row = QHBoxLayout()
        action_row.setContentsMargins(_FORM_ACTION_INSET, 0, 0, 0)
        action_row.setSpacing(8)
        self._create_btn = QPushButton()
        self._create_btn.setObjectName("btnPrimary")
        self._create_btn.clicked.connect(self._run_create_deck)
        self._cancel_btn = QPushButton()
        self._cancel_btn.setObjectName("btnSecondary")
        self._cancel_btn.clicked.connect(self._cancel_analysis)
        self._cancel_btn.setVisible(False)
        action_row.addWidget(self._create_btn)
        action_row.addWidget(self._cancel_btn)
        action_row.addStretch()
        form_layout.addLayout(action_row)

        hint_row = QHBoxLayout()
        hint_row.setContentsMargins(_FORM_ACTION_INSET, 0, 0, 0)
        self._create_hint = QLabel()
        self._create_hint.setObjectName("createDeckHint")
        self._create_hint.setWordWrap(True)
        hint_row.addWidget(self._create_hint)
        form_layout.addLayout(hint_row)

        progress_row = QHBoxLayout()
        progress_row.setContentsMargins(_FORM_ACTION_INSET, 0, 0, 0)
        self._progress_bar = QProgressBar()
        self._progress_bar.setObjectName("createDeckProgress")
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setVisible(False)
        progress_row.addWidget(self._progress_bar, stretch=1)
        form_layout.addLayout(progress_row)

        status_row = QHBoxLayout()
        status_row.setContentsMargins(_FORM_ACTION_INSET, 0, 0, 0)
        self._status_label = QLabel()
        self._status_label.setObjectName("statusLabel")
        self._status_label.setWordWrap(True)
        status_row.addWidget(self._status_label)
        form_layout.addLayout(status_row)

        root.addWidget(self._form_host, stretch=1)

        self._direction_combo.currentIndexChanged.connect(self._on_direction_changed)
        self._tag_combo.currentIndexChanged.connect(self._refresh_state)
        self._starred_only.toggled.connect(self._refresh_preview)
        self.reload_model_combo()
        self.retranslate_ui()
        self._reload_tags()

    def _init_direction_combo(self) -> None:
        self._direction_combo.clear()
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
        best_pending = -1
        max_candidates = int(get_feature("learning.ai_corpus_analysis").get("max_candidates", 120))
        for index in range(self._direction_combo.count()):
            kind = self._direction_combo.itemData(index)
            pending = self._total_new_for_direction(kind, max_candidates=max_candidates)
            if pending > best_pending:
                best_pending = pending
                default_index = index
        if self._direction_combo.count():
            self._direction_combo.setCurrentIndex(default_index)

    def _max_candidates(self) -> int:
        return int(get_feature("learning.ai_corpus_analysis").get("max_candidates", 120))

    def _on_direction_changed(self) -> None:
        self._reload_tags(allow_direction_switch=False)

    def _total_new_for_direction(self, direction: str, *, max_candidates: int) -> int:
        total = 0
        untagged_records = history.search_records(
            direction=direction,
            untagged_only=True,
            limit=5000,
            learning_kind=True,
        )
        untagged_pending = pending_corpus_records(
            untagged_records,
            tag="",
            direction=direction,
        )
        if untagged_pending:
            total += len(
                select_candidates(untagged_pending, max_candidates=max_candidates)
            )
        if is_enabled("history.tags"):
            for tag, _count in history.get_tag_counts(direction=direction, learning_kind=True):
                tagged_records = history.search_records(
                    direction=direction,
                    tag=tag,
                    limit=5000,
                    learning_kind=True,
                )
                tagged_pending = pending_corpus_records(
                    tagged_records,
                    tag=tag,
                    direction=direction,
                )
                if tagged_pending:
                    total += len(
                        select_candidates(tagged_pending, max_candidates=max_candidates)
                    )
        return total

    def _any_direction_has_pending(self) -> bool:
        max_candidates = self._max_candidates()
        for index in range(self._direction_combo.count()):
            kind = self._direction_combo.itemData(index)
            if self._total_new_for_direction(kind, max_candidates=max_candidates) > 0:
                return True
        return False

    def _first_direction_label_with_pending(self, *, exclude_kind: str | None = None) -> str:
        max_candidates = self._max_candidates()
        for index in range(self._direction_combo.count()):
            kind = self._direction_combo.itemData(index)
            if exclude_kind is not None and kind == exclude_kind:
                continue
            if self._total_new_for_direction(kind, max_candidates=max_candidates) > 0:
                return self._direction_combo.itemText(index)
        return ""

    def _try_switch_direction_with_pending(self) -> bool:
        current = self._direction_combo.currentData()
        max_candidates = self._max_candidates()
        for index in range(self._direction_combo.count()):
            kind = self._direction_combo.itemData(index)
            if kind == current:
                continue
            if self._total_new_for_direction(kind, max_candidates=max_candidates) <= 0:
                continue
            self._direction_combo.blockSignals(True)
            self._direction_combo.setCurrentIndex(index)
            self._direction_combo.blockSignals(False)
            self._reload_tags(allow_direction_switch=True)
            return True
        return False

    def retranslate_ui(self) -> None:
        self._source_title.setText(tr("learning.create_deck_source_title"))
        self._source_hint.setText(tr("learning.create_deck_source_hint"))
        self._tag_label.setText(tr("learning.category_label"))
        self._direction_label.setText(tr("learning.direction"))
        self._preview_title.setText(tr("learning.create_deck_preview_title"))
        self._starred_only.setText(tr("learning.starred_only"))
        self._model_label.setText(tr("learning.model"))
        self._create_btn.setText(tr("learning.run_analysis"))
        self._cancel_btn.setText(tr("main.cancel"))
        self._create_hint.setText(tr("learning.create_deck_hint"))
        self._preview_table.setHorizontalHeaderLabels(
            [
                tr("learning.create_deck_col_word").upper(),
                tr("learning.create_deck_col_translation").upper(),
                tr("learning.create_deck_col_why").upper(),
            ]
        )
        self._refresh_state()

    def reload_model_combo(self) -> None:
        from quicklingo import settings

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

    def apply_navigation(
        self,
        *,
        tag: str | None = None,
        direction: str | None = None,
        untagged: bool = False,
    ) -> None:
        if direction:
            kind = resolve_learning_direction(direction)
            index = self._direction_combo.findData(kind)
            if index >= 0:
                self._direction_combo.setCurrentIndex(index)
        self._reload_tags()
        if untagged:
            index = self._tag_combo.findData(UNTAGGED_SENTINEL)
        else:
            index = self._tag_combo.findData(tag or "")
        if index >= 0:
            self._tag_combo.setCurrentIndex(index)

    def _reload_tags(self, *, allow_direction_switch: bool = True) -> None:
        direction = self._direction_combo.currentData()
        current = self._tag_combo.currentData()
        max_candidates = self._max_candidates()
        self._tag_combo.blockSignals(True)
        self._tag_combo.clear()
        untagged_new = self._count_new_candidates(
            untagged=True,
            max_candidates=max_candidates,
        )
        if untagged_new > 0:
            self._tag_combo.addItem(
                tr("learning.tag_untagged", count=untagged_new),
                UNTAGGED_SENTINEL,
            )
        if is_enabled("history.tags"):
            for tag, _count in history.get_tag_counts(direction=direction, learning_kind=True):
                new_count = self._count_new_candidates(
                    tag=tag,
                    max_candidates=max_candidates,
                )
                if new_count <= 0:
                    continue
                self._tag_combo.addItem(f"{tag} ({new_count})", tag)
        if current is not None:
            index = self._tag_combo.findData(current)
            if index >= 0:
                self._tag_combo.setCurrentIndex(index)
        elif self._tag_combo.count():
            self._tag_combo.setCurrentIndex(0)
        self._tag_combo.blockSignals(False)
        if allow_direction_switch and self._tag_combo.count() == 0:
            if self._try_switch_direction_with_pending():
                return
        self._refresh_state()

    def _count_new_candidates(
        self,
        *,
        tag: str = "",
        untagged: bool = False,
        max_candidates: int,
        starred_only: bool = False,
    ) -> int:
        direction = self._direction_combo.currentData()
        if untagged:
            records = history.search_records(
                direction=direction,
                untagged_only=True,
                limit=5000,
                learning_kind=True,
            )
            deck_tag = ""
        else:
            records = history.search_records(
                direction=direction,
                tag=tag,
                limit=5000,
                learning_kind=True,
            )
            deck_tag = tag
        pending = pending_corpus_records(records, tag=deck_tag, direction=direction)
        if not pending:
            return 0
        return len(
            select_candidates(
                pending,
                max_candidates=max_candidates,
                starred_only=starred_only,
            )
        )

    def _pending_corpus_records(self) -> list[history.TranslationRecord]:
        tag, untagged, _label = self._corpus_tag_selection()
        direction = self._direction_combo.currentData()
        records = self._corpus_records()
        return pending_corpus_records(
            records,
            tag="" if untagged else tag,
            direction=direction,
        )

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

    def _refresh_state(self) -> None:
        records = self._corpus_records()
        pending = self._pending_corpus_records()
        has_new = bool(pending)
        any_pending = self._any_direction_has_pending()
        self._form_host.setVisible(has_new or any_pending)
        self._create_btn.setEnabled(has_new and not self._analysis_running())
        if has_new:
            self._empty.hide_state()
            self._status_label.clear()
            self._refresh_preview()
            return

        self._preview_table.setRowCount(0)
        self._stats_badge.setText("")

        _tag, untagged, label = self._corpus_tag_selection()
        current_direction = self._direction_combo.currentText()

        if any_pending and self._tag_combo.count() == 0:
            self._empty.hide_state()
            other_direction = self._first_direction_label_with_pending(
                exclude_kind=self._direction_combo.currentData()
            )
            if other_direction:
                self._status_label.setText(
                    tr(
                        "learning.switch_direction_hint",
                        current=current_direction,
                        direction=other_direction,
                    )
                )
            else:
                self._status_label.clear()
            return

        if not any_pending:
            self._form_host.setVisible(False)
            title = tr("learning.empty_all_categories_done_title")
            body = tr("learning.empty_all_categories_done_body")
            action = "" if self._standalone else tr("learning.empty_open_main")
            self._empty.set_content(title, body, action=action)
            return

        self._empty.hide_state()
        if records:
            self._status_label.setText(
                tr("learning.empty_deck_current_status", tag=label)
            )
            return

        self._form_host.setVisible(False)
        if untagged:
            title = tr("learning.empty_untagged_title")
            body = tr("learning.empty_untagged_body")
        else:
            title = tr("learning.empty_tag_title", tag=label)
            body = tr("learning.empty_tag_body", tag=label)
        action = "" if self._standalone else tr("learning.empty_open_main")
        self._empty.set_content(title, body, action=action)

    def _refresh_preview(self) -> None:
        records = self._corpus_records()
        pending = self._pending_corpus_records()
        if not pending:
            self._preview_table.setRowCount(0)
            self._stats_badge.setText("")
            return
        max_candidates = int(get_feature("learning.ai_corpus_analysis").get("max_candidates", 120))
        difficult = compute_difficult_words(pending)
        candidates = select_candidates(
            pending,
            max_candidates=max_candidates,
            starred_only=self._starred_only.isChecked(),
            difficult_items=difficult,
        )
        self._stats_badge.setText(
            tr(
                "learning.preview_stats",
                new=len(pending),
                records=len(records),
                candidates=len(candidates),
            )
        )
        preview = candidates[:_PREVIEW_ROW_LIMIT]
        self._preview_table.setRowCount(len(preview))
        for row, candidate in enumerate(preview):
            for col, text in enumerate(
                (
                    candidate.source_text,
                    candidate.result_text,
                    _reason_label(candidate.reason),
                )
            ):
                item = QTableWidgetItem(text)
                if col < 2 and text:
                    item.setToolTip(text)
                self._preview_table.setItem(row, col, item)

    def current_model_id(self) -> str | None:
        if self._model_combo.count() == 0:
            return None
        return self._model_combo.currentData()

    def set_status(self, text: str) -> None:
        self._status_label.setText(text)

    def _analysis_running(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def _reset_analysis_ui(self) -> None:
        self._create_btn.setEnabled(bool(self._pending_corpus_records()))
        self._cancel_btn.setVisible(False)
        self._progress_bar.setVisible(False)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)

    def _run_create_deck(self) -> None:
        if not is_enabled("learning.ai_corpus_analysis"):
            QMessageBox.information(
                self,
                tr("learning.window_title"),
                tr("learning.analysis_disabled"),
            )
            return
        if self._analysis_running():
            return
        pending = self._pending_corpus_records()
        if not pending:
            self._status_label.setText(tr("learning.no_new_corpus"))
            return
        tag, _untagged, deck_label = self._corpus_tag_selection()
        direction = self._direction_combo.currentData()
        max_candidates = int(get_feature("learning.ai_corpus_analysis").get("max_candidates", 120))
        candidates = select_candidates(
            pending,
            max_candidates=max_candidates,
            starred_only=self._starred_only.isChecked(),
            difficult_items=compute_difficult_words(pending),
        )
        direction_label = self._direction_combo.currentText()
        confirm = QMessageBox.question(
            self,
            tr("learning.analysis_confirm_title", deck=deck_label),
            tr(
                "learning.analysis_confirm_body",
                records=len(pending),
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
            pending,
            tag=tag,
            direction=direction,
            model_entry=model_entry,
            deck_display_name=deck_label,
            max_candidates=int(feature.get("max_candidates", 120)),
            batch_size=int(feature.get("batch_size", 40)),
            starred_only=self._starred_only.isChecked(),
            parent=self,
        )
        self._worker.progress.connect(self._on_analysis_progress)
        self._worker.finished.connect(self._on_analysis_finished)
        self._worker.error.connect(self._on_analysis_error)
        self._worker.cancelled.connect(self._on_analysis_cancelled)
        self._create_btn.setEnabled(False)
        self._cancel_btn.setVisible(True)
        self._progress_bar.setVisible(True)
        self._progress_bar.setRange(0, 0)
        self._status_label.setText(tr("learning.analysis_running"))
        self._worker.start()

    def _on_analysis_progress(self, message: str) -> None:
        self._status_label.setText(message)

    def _cancel_analysis(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
            self._status_label.setText(tr("learning.analysis_cancelled"))
            self._reset_analysis_ui()

    def _on_analysis_finished(self, deck_id: int, summary: str) -> None:
        self._worker = None
        self._reset_analysis_ui()
        self._status_label.setText(tr("learning.analysis_done"))
        self.deck_created.emit(deck_id, summary)

    def _on_analysis_error(self, message: str) -> None:
        self._worker = None
        self._reset_analysis_ui()
        if message:
            self._status_label.setText(tr("main.status_error", message=message))

    def _on_analysis_cancelled(self) -> None:
        self._worker = None
        self._reset_analysis_ui()
