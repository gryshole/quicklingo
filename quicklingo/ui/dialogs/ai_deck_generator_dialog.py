from __future__ import annotations

import re

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from quicklingo.config.loader import get_directions
from quicklingo.db import learning
from quicklingo.features import get_feature, is_enabled
from quicklingo.i18n import tr
from quicklingo.learning.ai_deck.models import CEFR_LEVELS, AiDeckParams, TAG_PATTERN
from quicklingo.learning.ai_deck.topics import (
    CUSTOM_TOPIC_KEY,
    LEXICON_TYPE_KEYS,
    TOPIC_KEYS,
    lexicon_type_label,
    topic_label,
)
from quicklingo.providers.registry import get_model_by_index, get_model_entries
from quicklingo.ui.qt_utils import configure_single_line_combo, reload_combo
from quicklingo.workers.ai_deck_generator_worker import AiDeckGeneratorWorker

_PAGE_FORM = 0
_PAGE_LOADING = 1
_PAGE_ERROR = 2

_PRIMARY_BTN = """
    QPushButton {
        background: #2563eb;
        color: #ffffff;
        border: none;
        border-radius: 8px;
        padding: 10px 20px;
        font-weight: 600;
    }
    QPushButton:hover { background: #1d4ed8; }
    QPushButton:disabled { background: #94a3b8; }
"""


class AiDeckGeneratorDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        initial_model_id: str | None = None,
    ) -> None:
        super().__init__(parent)
        self._initial_model_id = initial_model_id
        self._worker: AiDeckGeneratorWorker | None = None
        self._result: tuple[int, str, dict] | None = None
        self.setMinimumWidth(480)
        self.setModal(True)

        root = QVBoxLayout(self)
        self._stack = QStackedWidget()
        root.addWidget(self._stack)

        self._stack.addWidget(self._build_form_page())
        self._stack.addWidget(self._build_loading_page())
        self._stack.addWidget(self._build_error_page())

        self.retranslate_ui()

    def result_data(self) -> tuple[int, str, dict]:
        if self._result is None:
            raise RuntimeError("dialog not completed")
        return self._result

    def retranslate_ui(self) -> None:
        self.setWindowTitle(tr("learning.ai_deck.dialog_title"))
        self._tag_label.setText(tr("learning.ai_deck.tag"))
        self._tag_field.setPlaceholderText(tr("learning.ai_deck.tag_placeholder"))
        self._level_label.setText(tr("learning.ai_deck.level"))
        self._model_label.setText(tr("learning.model"))
        self._topic_label.setText(tr("learning.ai_deck.topic"))
        self._custom_topic_label.setText(tr("learning.ai_deck.custom_topic"))
        self._custom_topic_field.setPlaceholderText(tr("learning.ai_deck.custom_topic_placeholder"))
        self._lexicon_label.setText(tr("learning.ai_deck.lexicon"))
        self._count_label.setText(tr("learning.ai_deck.word_count"))
        self._direction_label.setText(tr("learning.ai_deck.direction"))
        self._generate_btn.setText(tr("learning.ai_deck.generate"))
        self._cancel_btn.setText(tr("common.cancel"))
        self._loading_title.setText(tr("learning.ai_deck.generating"))
        self._retry_btn.setText(tr("learning.ai_deck.retry"))
        self._error_close_btn.setText(tr("common.close"))
        self._reload_topic_combo()
        self._reload_lexicon_combo()
        self._reload_model_combo()

    def _reload_model_combo(self) -> None:
        current = self._model_combo.currentData() if self._model_combo.count() else None
        if current is None:
            current = self._initial_model_id
        reload_combo(
            self._model_combo,
            [(entry.model_id, entry.display_name) for entry in get_model_entries()],
            current_data=current,
        )
        if self._model_combo.count() and self._model_combo.currentIndex() < 0:
            self._model_combo.setCurrentIndex(0)

    def _build_form_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        form = QFormLayout()
        self._tag_field = QLineEdit()
        self._tag_label = QLabel()
        form.addRow(self._tag_label, self._tag_field)

        self._level_combo = QComboBox()
        configure_single_line_combo(self._level_combo)
        for level in CEFR_LEVELS:
            self._level_combo.addItem(level, level)
        self._level_combo.setCurrentIndex(2)
        self._level_label = QLabel()
        form.addRow(self._level_label, self._level_combo)

        self._model_combo = QComboBox()
        configure_single_line_combo(self._model_combo)
        self._model_label = QLabel()
        form.addRow(self._model_label, self._model_combo)

        self._topic_combo = QComboBox()
        configure_single_line_combo(self._topic_combo)
        self._topic_combo.currentIndexChanged.connect(self._update_custom_topic_visibility)
        self._topic_label = QLabel()
        form.addRow(self._topic_label, self._topic_combo)

        self._custom_topic_field = QLineEdit()
        self._custom_topic_label = QLabel()
        form.addRow(self._custom_topic_label, self._custom_topic_field)

        self._lexicon_combo = QComboBox()
        configure_single_line_combo(self._lexicon_combo)
        self._lexicon_label = QLabel()
        form.addRow(self._lexicon_label, self._lexicon_combo)

        self._count_spin = QSpinBox()
        self._count_spin.setRange(10, 30)
        self._count_spin.setValue(15)
        self._count_label = QLabel()
        form.addRow(self._count_label, self._count_spin)

        self._direction_combo = QComboBox()
        configure_single_line_combo(self._direction_combo)
        for direction in get_directions():
            self._direction_combo.addItem(direction.label, direction.id)
        self._direction_label = QLabel()
        form.addRow(self._direction_label, self._direction_combo)

        layout.addLayout(form)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self._cancel_btn = QPushButton()
        self._cancel_btn.clicked.connect(self.reject)
        self._generate_btn = QPushButton()
        self._generate_btn.setStyleSheet(_PRIMARY_BTN)
        self._generate_btn.clicked.connect(self._start_generation)
        buttons.addWidget(self._cancel_btn)
        buttons.addWidget(self._generate_btn)
        layout.addLayout(buttons)
        self._update_custom_topic_visibility()
        return page

    def _build_loading_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addStretch()
        self._loading_title = QLabel()
        self._loading_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._loading_status = QLabel()
        self._loading_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._loading_status.setWordWrap(True)
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        layout.addWidget(self._loading_title)
        layout.addWidget(self._loading_status)
        layout.addWidget(self._progress)
        self._loading_cancel_btn = QPushButton()
        self._loading_cancel_btn.clicked.connect(self._cancel_worker)
        layout.addWidget(self._loading_cancel_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()
        return page

    def _build_error_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addStretch()
        self._error_label = QLabel()
        self._error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._error_label.setWordWrap(True)
        layout.addWidget(self._error_label)
        row = QHBoxLayout()
        row.addStretch()
        self._retry_btn = QPushButton()
        self._retry_btn.clicked.connect(lambda: self._stack.setCurrentIndex(_PAGE_FORM))
        self._error_close_btn = QPushButton()
        self._error_close_btn.clicked.connect(self.reject)
        row.addWidget(self._retry_btn)
        row.addWidget(self._error_close_btn)
        row.addStretch()
        layout.addLayout(row)
        layout.addStretch()
        return page

    def _reload_topic_combo(self) -> None:
        current = self._topic_combo.currentData()
        self._topic_combo.clear()
        for key in TOPIC_KEYS:
            self._topic_combo.addItem(topic_label(key), key)
        if current is not None:
            index = self._topic_combo.findData(current)
            if index >= 0:
                self._topic_combo.setCurrentIndex(index)

    def _reload_lexicon_combo(self) -> None:
        current = self._lexicon_combo.currentData()
        self._lexicon_combo.clear()
        for key in LEXICON_TYPE_KEYS:
            self._lexicon_combo.addItem(lexicon_type_label(key), key)
        if current is not None:
            index = self._lexicon_combo.findData(current)
            if index >= 0:
                self._lexicon_combo.setCurrentIndex(index)

    def _update_custom_topic_visibility(self) -> None:
        is_custom = self._topic_combo.currentData() == CUSTOM_TOPIC_KEY
        self._custom_topic_label.setVisible(is_custom)
        self._custom_topic_field.setVisible(is_custom)
        self._custom_topic_field.setEnabled(is_custom)

    def _collect_params(self, *, merge_existing: bool) -> AiDeckParams:
        return AiDeckParams(
            tag=self._tag_field.text().strip().lower(),
            level=str(self._level_combo.currentData()),
            topic_key=str(self._topic_combo.currentData()),
            custom_topic=self._custom_topic_field.text().strip(),
            lexicon_type=str(self._lexicon_combo.currentData()),
            word_count=int(self._count_spin.value()),
            direction=str(self._direction_combo.currentData()),
            merge_existing=merge_existing,
        )

    def _validate(self, params: AiDeckParams) -> bool:
        if not re.fullmatch(TAG_PATTERN, params.normalized_tag()):
            QMessageBox.warning(self, tr("learning.ai_deck.dialog_title"), tr("learning.ai_deck.tag_invalid"))
            return False
        if params.topic_key == CUSTOM_TOPIC_KEY and not params.custom_topic.strip():
            QMessageBox.warning(
                self,
                tr("learning.ai_deck.dialog_title"),
                tr("learning.ai_deck.custom_topic_required"),
            )
            return False
        return True

    def _start_generation(self) -> None:
        if not is_enabled("learning.ai_deck_generator"):
            return
        params = self._collect_params(merge_existing=False)
        if not self._validate(params):
            return

        existing = learning.find_deck_by_tag(params.normalized_tag(), params.direction)
        merge_existing = False
        if existing is not None:
            answer = QMessageBox.question(
                self,
                tr("learning.ai_deck.duplicate_title"),
                tr("learning.ai_deck.duplicate_message", tag=params.normalized_tag()),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            merge_existing = True
            params = self._collect_params(merge_existing=True)

        model_entry = get_model_by_index(self._model_combo.currentIndex())
        if self._model_combo.count() == 0:
            QMessageBox.warning(self, tr("learning.ai_deck.dialog_title"), tr("learning.ai_deck.no_model"))
            return

        feature = get_feature("learning.ai_deck_generator")
        batch_size = int(feature.get("batch_size", 10))
        self._stack.setCurrentIndex(_PAGE_LOADING)
        self._loading_status.setText(tr("learning.ai_deck.step1"))
        self._loading_cancel_btn.setText(tr("common.cancel"))
        self._generate_btn.setEnabled(False)
        self._cancel_btn.setEnabled(False)

        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(200)

        self._worker = AiDeckGeneratorWorker(
            params,
            model_entry=model_entry,
            batch_size=batch_size,
            parent=self,
        )
        self._worker.progress.connect(self._loading_status.setText)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.error.connect(self._on_worker_error)
        self._worker.start()

    def _cancel_worker(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
        self.reject()

    def _on_worker_finished(self, deck_id: int, summary: str, media_meta: dict) -> None:
        self._worker = None
        self._result = (deck_id, summary, media_meta)
        self.accept()

    def _on_worker_error(self, message: str) -> None:
        self._worker = None
        self._error_label.setText(tr("learning.ai_deck.error", message=message))
        self._stack.setCurrentIndex(_PAGE_ERROR)
        self._generate_btn.setEnabled(True)
        self._cancel_btn.setEnabled(True)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
        super().closeEvent(event)
