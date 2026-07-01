from pathlib import Path

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
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
from quicklingo.learning.difficult_words import compute_difficult_words
from quicklingo.learning.review_queue import card_bucket, count_due_cards
from quicklingo.providers.registry import get_model_by_index, get_model_entries
from quicklingo.ui.qt_utils import configure_single_line_combo, reload_combo
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


_LEARNING_CARDS_TABLE_WIDTHS = [140, 140, 100, 160, 80, 52]
_LEARNING_CARDS_PRIORITY_WIDTH = 52


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
            self._context.setPlaceholderText("One English example sentence per line")
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


class LearningWindow(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        restore_window_geometry(self, "learning", default_width=860, default_height=640)
        self._worker: CorpusAnalysisWorker | None = None
        self._media_worker: CardMediaWorker | None = None
        self._current_deck_id: int | None = None

        layout = QVBoxLayout(self)
        self._tabs = QTabWidget()

        self._analyze_tab = self._build_analyze_tab()
        self._cards_tab = self._build_cards_tab()
        self._review_tab = self._build_review_tab()

        self._tabs.addTab(self._analyze_tab, "")
        self._tabs.addTab(self._cards_tab, "")
        self._tabs.addTab(self._review_tab, "")
        self._tabs.currentChanged.connect(self._on_tab_changed)

        layout.addWidget(self._tabs)
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

    def _build_analyze_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        self._tag_combo = QComboBox()
        self._tag_combo.setEditable(True)
        self._direction_combo = QComboBox()
        for direction in get_directions():
            self._direction_combo.addItem(direction.label, direction.id)
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
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        self._preview_btn = QPushButton()
        self._preview_btn.clicked.connect(self._preview_local)
        self._analyze_btn = QPushButton()
        self._analyze_btn.clicked.connect(self._run_analysis)
        self._cancel_btn = QPushButton()
        self._cancel_btn.clicked.connect(self._cancel_analysis)
        self._cancel_btn.setVisible(False)
        btn_row.addWidget(self._preview_btn)
        btn_row.addWidget(self._analyze_btn)
        btn_row.addWidget(self._cancel_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._status_label = QLabel()
        self._status_label.setWordWrap(True)
        self._preview_field = QTextEdit()
        self._preview_field.setReadOnly(True)
        self._summary_field = QTextEdit()
        self._summary_field.setReadOnly(True)
        self._preview_title = QLabel()
        self._summary_title = QLabel()
        layout.addWidget(self._status_label)
        layout.addWidget(self._preview_title)
        layout.addWidget(self._preview_field, stretch=1)
        layout.addWidget(self._summary_title)
        layout.addWidget(self._summary_field, stretch=1)
        return widget

    def _build_cards_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        top = QHBoxLayout()
        self._deck_combo = QComboBox()
        self._deck_combo.currentIndexChanged.connect(self._load_cards)
        self._export_btn = QPushButton()
        self._export_btn.clicked.connect(self._export_anki)
        self._edit_card_btn = QPushButton()
        self._edit_card_btn.clicked.connect(self._edit_selected_card)
        self._media_btn = QPushButton()
        self._media_btn.clicked.connect(self._generate_media_for_deck)
        self._delete_card_btn = QPushButton()
        self._delete_card_btn.clicked.connect(self._delete_selected_card)
        self._delete_deck_btn = QPushButton()
        self._delete_deck_btn.clicked.connect(self._delete_selected_deck)
        self._deck_label = QLabel()
        top.addWidget(self._deck_label)
        top.addWidget(self._deck_combo, stretch=1)
        top.addWidget(self._export_btn)
        top.addWidget(self._edit_card_btn)
        top.addWidget(self._media_btn)
        top.addWidget(self._delete_card_btn)
        top.addWidget(self._delete_deck_btn)
        layout.addLayout(top)

        self._cards_table = QTableWidget(0, 6)
        self._cards_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._cards_table.doubleClicked.connect(self._edit_selected_card)
        self._cards_table.horizontalHeader().setStretchLastSection(False)
        layout.addWidget(self._cards_table, stretch=1)
        return widget

    def _build_review_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        top = QHBoxLayout()
        self._review_deck_combo = QComboBox()
        self._review_deck_combo.currentIndexChanged.connect(self._on_review_deck_changed)
        self._review_deck_label = QLabel()
        top.addWidget(self._review_deck_label)
        top.addWidget(self._review_deck_combo, stretch=1)
        layout.addLayout(top)
        self._review_session = ReviewSessionWidget()
        self._review_session.grade_submitted.connect(self._review_session.update_streak)
        self._review_session.session_finished.connect(self._review_session.update_streak)
        self._review_session.session_finished.connect(self._refresh_deck_combo_due_counts)
        layout.addWidget(self._review_session, stretch=1)
        return widget

    def retranslate_ui(self) -> None:
        self.setWindowTitle(tr("learning.window_title"))
        self._tabs.setTabText(0, tr("learning.tab_analyze"))
        self._tabs.setTabText(1, tr("learning.tab_cards"))
        self._tabs.setTabText(2, tr("learning.tab_review"))
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
        self._cards_table.setHorizontalHeaderLabels(
            [
                tr("learning.card_front"),
                tr("learning.card_back"),
                tr("learning.card_hint"),
                tr("learning.card_notes"),
                tr("learning.card_status"),
                tr("learning.card_priority"),
            ]
        )
        self._review_deck_label.setText(tr("learning.deck"))
        self._review_session.retranslate_ui()

    def _configure_cards_table_columns(self) -> None:
        header = self._cards_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(40)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.resizeSection(5, min(header.sectionSize(5), _LEARNING_CARDS_PRIORITY_WIDTH))

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
        if not is_enabled("history.tags"):
            return
        current = self._tag_combo.currentText()
        self._tag_combo.blockSignals(True)
        self._tag_combo.clear()
        self._tag_combo.addItem("")
        for tag in history.get_distinct_tags():
            self._tag_combo.addItem(tag)
        index = self._tag_combo.findText(current)
        if index >= 0:
            self._tag_combo.setCurrentIndex(index)
        else:
            self._tag_combo.setEditText(current)
        self._tag_combo.blockSignals(False)

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

    def _on_tab_changed(self, index: int) -> None:
        if index == 1:
            self._load_cards()
        if index == 2:
            self._on_review_deck_changed()

    def _on_review_deck_changed(self) -> None:
        deck_id = self._review_deck_combo.currentData()
        deck = learning.get_deck(deck_id) if deck_id else None
        direction = deck.direction if deck else "ua-en"
        self._review_session.set_deck(deck_id, direction=direction)

    def _corpus_records(self) -> list[history.TranslationRecord]:
        tag = self._tag_combo.currentText().strip()
        direction = self._direction_combo.currentData()
        return history.search_records(
            direction=direction,
            tag=tag or None,
            limit=5000,
        )

    def _preview_local(self) -> None:
        if not is_enabled("learning.difficult_words"):
            return
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
            return
        if self._worker is not None and self._worker.isRunning():
            return
        records = self._corpus_records()
        if not records:
            self._status_label.setText(tr("learning.no_corpus"))
            return
        tag = self._tag_combo.currentText().strip()
        direction = self._direction_combo.currentData()
        model_entry = get_model_by_index(self._model_combo.currentIndex())
        feature = get_feature("learning.ai_corpus_analysis")
        self._worker = CorpusAnalysisWorker(
            records,
            tag=tag,
            direction=direction,
            model_entry=model_entry,
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
        self._tabs.setCurrentIndex(1)
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

    def _load_cards(self) -> None:
        if not is_enabled("learning.anki_preview"):
            return
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
        self._cards_table.setRowCount(len(cards))
        for row, card in enumerate(cards):
            for col, text in enumerate(
                (
                    card.front,
                    card.back,
                    card.hint,
                    card.notes,
                    self._status_label_for_card(card),
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
        super().closeEvent(event)
