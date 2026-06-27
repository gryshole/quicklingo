from PySide6.QtCore import Qt
from pathlib import Path
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

from quicklingo.config.loader import get_direction_label, get_directions
from quicklingo.db import history, learning
from quicklingo.features import get_feature, is_enabled
from quicklingo.i18n import tr
from quicklingo.learning.anki_export import export_anki_apkg, export_anki_csv
from quicklingo.learning.corpus_analysis import select_candidates
from quicklingo.learning.difficult_words import compute_difficult_words
from quicklingo import settings
from quicklingo.providers.registry import get_model_by_index, get_model_entries
from quicklingo.workers.corpus_analysis_worker import CorpusAnalysisWorker


class LearningWindow(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.resize(860, 640)
        self._worker: CorpusAnalysisWorker | None = None
        self._current_deck_id: int | None = None
        self._review_cards: list[learning.LearningCard] = []
        self._review_index = 0
        self._showing_back = False

        layout = QVBoxLayout(self)
        self._tabs = QTabWidget()

        self._analyze_tab = self._build_analyze_tab()
        self._cards_tab = self._build_cards_tab()
        self._review_tab = self._build_review_tab()

        self._tabs.addTab(self._analyze_tab, "")
        self._tabs.addTab(self._cards_tab, "")
        self._tabs.addTab(self._review_tab, "")

        layout.addWidget(self._tabs)
        self.retranslate_ui()
        self._reload_tags()
        self._reload_decks()

    def _build_analyze_tab(self) -> QDialog:
        widget = QDialog()
        layout = QVBoxLayout(widget)

        form = QFormLayout()
        self._tag_combo = QComboBox()
        self._tag_combo.setEditable(True)
        self._direction_combo = QComboBox()
        for direction in get_directions():
            self._direction_combo.addItem(direction.label, direction.id)
        self._starred_only = QCheckBox()
        self._model_combo = QComboBox()
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

    def _build_cards_tab(self) -> QDialog:
        widget = QDialog()
        layout = QVBoxLayout(widget)
        top = QHBoxLayout()
        self._deck_combo = QComboBox()
        self._deck_combo.currentIndexChanged.connect(self._load_cards)
        self._export_btn = QPushButton()
        self._export_btn.clicked.connect(self._export_anki)
        self._delete_card_btn = QPushButton()
        self._delete_card_btn.clicked.connect(self._delete_selected_card)
        self._deck_label = QLabel()
        top.addWidget(self._deck_label)
        top.addWidget(self._deck_combo, stretch=1)
        top.addWidget(self._export_btn)
        top.addWidget(self._delete_card_btn)
        layout.addLayout(top)

        self._cards_table = QTableWidget(0, 4)
        self._cards_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._cards_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._cards_table, stretch=1)
        return widget

    def _build_review_tab(self) -> QDialog:
        widget = QDialog()
        layout = QVBoxLayout(widget)
        top = QHBoxLayout()
        self._review_deck_combo = QComboBox()
        self._review_deck_combo.currentIndexChanged.connect(self._reset_review)
        self._start_review_btn = QPushButton()
        self._start_review_btn.clicked.connect(self._start_review)
        self._review_deck_label = QLabel()
        top.addWidget(self._review_deck_label)
        top.addWidget(self._review_deck_combo, stretch=1)
        top.addWidget(self._start_review_btn)
        layout.addLayout(top)

        self._streak_label = QLabel()
        self._review_progress = QLabel()
        self._review_front = QTextEdit()
        self._review_front.setReadOnly(True)
        self._review_back = QTextEdit()
        self._review_back.setReadOnly(True)
        self._review_back.setVisible(False)

        btn_row = QHBoxLayout()
        self._show_answer_btn = QPushButton()
        self._show_answer_btn.clicked.connect(self._show_answer)
        self._again_btn = QPushButton()
        self._again_btn.clicked.connect(lambda: self._submit_grade(1))
        self._hard_btn = QPushButton()
        self._hard_btn.clicked.connect(lambda: self._submit_grade(2))
        self._good_btn = QPushButton()
        self._good_btn.clicked.connect(lambda: self._submit_grade(3))
        self._easy_btn = QPushButton()
        self._easy_btn.clicked.connect(lambda: self._submit_grade(4))
        self._again_btn.setVisible(False)
        self._hard_btn.setVisible(False)
        self._good_btn.setVisible(False)
        self._easy_btn.setVisible(False)
        btn_row.addWidget(self._show_answer_btn)
        btn_row.addWidget(self._again_btn)
        btn_row.addWidget(self._hard_btn)
        btn_row.addWidget(self._good_btn)
        btn_row.addWidget(self._easy_btn)
        btn_row.addStretch()
        layout.addWidget(self._streak_label)
        layout.addWidget(self._review_progress)
        layout.addWidget(self._review_front, stretch=1)
        layout.addWidget(self._review_back, stretch=1)
        layout.addLayout(btn_row)
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
        self._delete_card_btn.setText(tr("learning.delete_card"))
        self._cards_table.setHorizontalHeaderLabels(
            [tr("learning.card_front"), tr("learning.card_back"), tr("learning.card_context"), tr("learning.card_priority")]
        )
        self._review_deck_label.setText(tr("learning.deck"))
        self._start_review_btn.setText(tr("learning.start_review"))
        self._show_answer_btn.setText(tr("learning.show_answer"))
        self._again_btn.setText(tr("learning.review_again"))
        self._hard_btn.setText(tr("learning.review_hard"))
        self._good_btn.setText(tr("learning.review_good"))
        self._easy_btn.setText(tr("learning.review_easy"))
        self._update_streak_label()

    def _reload_model_combo(self) -> None:
        current = self._model_combo.currentData() if self._model_combo.count() else None
        self._model_combo.blockSignals(True)
        self._model_combo.clear()
        for entry in get_model_entries():
            self._model_combo.addItem(entry.display_name, entry.model_id)
        index = self._model_combo.findData(current)
        if index >= 0:
            self._model_combo.setCurrentIndex(index)
        elif self._model_combo.count():
            self._model_combo.setCurrentIndex(0)
        self._model_combo.blockSignals(False)

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
                label = f"{deck.name} ({get_direction_label(deck.direction)})"
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

    def _on_analysis_finished(self, deck_id: int, summary: str) -> None:
        self._worker = None
        self._current_deck_id = deck_id
        self._analyze_btn.setEnabled(True)
        self._cancel_btn.setVisible(False)
        self._summary_field.setPlainText(summary)
        self._status_label.setText(tr("learning.analysis_done"))
        self._reload_decks()
        self._load_cards()
        self._tabs.setCurrentIndex(1)

    def _on_analysis_error(self, message: str) -> None:
        self._worker = None
        self._analyze_btn.setEnabled(True)
        self._cancel_btn.setVisible(False)
        self._status_label.setText(tr("main.status_error", message=message))

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
        self._cards_table.setRowCount(len(cards))
        for row, card in enumerate(cards):
            self._cards_table.setItem(row, 0, QTableWidgetItem(card.front))
            self._cards_table.setItem(row, 1, QTableWidgetItem(card.back))
            self._cards_table.setItem(row, 2, QTableWidgetItem(card.context))
            self._cards_table.setItem(row, 3, QTableWidgetItem(str(card.priority)))

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

    def _update_streak_label(self) -> None:
        if not is_enabled("learning.streak"):
            self._streak_label.setText("")
            return
        streak, _last = settings.get_learning_streak()
        self._streak_label.setText(tr("learning.streak_label", streak=streak))

    def _reset_review(self) -> None:
        self._review_cards = []
        self._review_index = 0
        self._showing_back = False
        self._review_front.clear()
        self._review_back.clear()
        self._review_back.setVisible(False)
        self._again_btn.setVisible(False)
        self._hard_btn.setVisible(False)
        self._good_btn.setVisible(False)
        self._easy_btn.setVisible(False)
        self._review_progress.setText("")

    def _uses_fsrs(self) -> bool:
        return is_enabled("learning.srs_review")

    def _hide_grade_buttons(self) -> None:
        self._again_btn.setVisible(False)
        self._hard_btn.setVisible(False)
        self._good_btn.setVisible(False)
        self._easy_btn.setVisible(False)

    def _show_grade_buttons(self) -> None:
        if self._uses_fsrs():
            self._again_btn.setVisible(True)
            self._hard_btn.setVisible(True)
            self._good_btn.setVisible(True)
            self._easy_btn.setVisible(True)
        else:
            self._again_btn.setVisible(True)
            self._good_btn.setVisible(True)
            self._hard_btn.setVisible(False)
            self._easy_btn.setVisible(False)

    def _start_review(self) -> None:
        if not is_enabled("learning.daily_review"):
            return
        deck_id = self._review_deck_combo.currentData()
        if deck_id is None:
            return
        limit = int(get_feature("learning.daily_review").get("daily_limit", 20))
        self._review_cards = learning.get_due_cards(deck_id, limit=limit)
        self._review_index = 0
        self._showing_back = False
        if not self._review_cards:
            self._review_progress.setText(tr("learning.no_due_cards"))
            return
        self._show_current_review_card()

    def _show_current_review_card(self) -> None:
        if self._review_index >= len(self._review_cards):
            self._review_progress.setText(tr("learning.review_complete"))
            self._review_front.clear()
            self._review_back.clear()
            self._hide_grade_buttons()
            return
        card = self._review_cards[self._review_index]
        self._review_progress.setText(
            tr("learning.review_progress", current=self._review_index + 1, total=len(self._review_cards))
        )
        self._review_front.setPlainText(card.front)
        self._review_back.setPlainText(card.back + ("\n\n" + card.context if card.context else ""))
        self._review_back.setVisible(False)
        self._showing_back = False
        self._hide_grade_buttons()

    def _show_answer(self) -> None:
        if self._review_index >= len(self._review_cards):
            return
        self._review_back.setVisible(True)
        self._showing_back = True
        self._show_grade_buttons()

    def _after_grade(self) -> None:
        if is_enabled("learning.streak"):
            settings.record_learning_review_today()
            self._update_streak_label()
        self._review_index += 1
        self._show_current_review_card()

    def _submit_grade(self, rating_value: int) -> None:
        if self._uses_fsrs():
            self._grade_fsrs(rating_value)
        elif rating_value == 1:
            self._grade_review(True)
        elif rating_value == 3:
            self._grade_review(False)

    def _grade_review(self, again: bool) -> None:
        if self._review_index >= len(self._review_cards):
            return
        card = self._review_cards[self._review_index]
        learning.record_review(card.id, again=again)
        self._after_grade()

    def _grade_fsrs(self, rating_value: int) -> None:
        if self._review_index >= len(self._review_cards):
            return
        from fsrs import Rating

        card = self._review_cards[self._review_index]
        learning.record_review(card.id, fsrs_rating=Rating(rating_value))
        self._after_grade()

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
