import os

from PySide6.QtCore import Qt, QByteArray
from PySide6.QtGui import QCloseEvent, QGuiApplication
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QLabel,
    QMainWindow,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from quicklingo.db import history
from quicklingo.providers.registry import get_model_by_index, get_model_entries
from quicklingo import settings
from quicklingo.ui.format_output import format_en_ua_output, format_ua_en_output
from quicklingo.ui.history_window import HistoryWindow
from quicklingo.ui.zoomable_text_edit import ZoomableLineEdit, ZoomableTextEdit
from quicklingo.workers.translate_worker import TranslateWorker


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._worker: TranslateWorker | None = None
        self._pending_source = ""
        self._pending_direction = "ua-en"
        self._pending_model_id = ""
        self._history_window: HistoryWindow | None = None

        self.setWindowTitle("QuickLingo")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)

        self._create_menu_bar()

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(12, 8, 12, 12)
        layout.setSpacing(10)

        model_label = QLabel("Модель:")
        self._model_combo = QComboBox()
        for entry in get_model_entries():
            self._model_combo.addItem(entry.display_name, entry.model_id)
        self._model_combo.currentIndexChanged.connect(lambda _: self._check_api_key())

        direction_label = QLabel("Напрямок перекладу:")
        self._direction_group = QButtonGroup(self)
        self._ua_en_radio = QRadioButton("Укр → Англ")
        self._en_ua_radio = QRadioButton("Англ → Укр")
        self._ua_en_radio.setChecked(True)
        self._direction_group.addButton(self._ua_en_radio, 0)
        self._direction_group.addButton(self._en_ua_radio, 1)

        input_label = QLabel("Введіть текст (Enter — переклад):")
        self._input_field = ZoomableLineEdit()
        self._input_field.setPlaceholderText("Введіть текст...")
        self._input_field.returnPressed.connect(self._submit_translation)

        output_label = QLabel("Результат:")
        self._output_field = ZoomableTextEdit()
        self._output_field.setPlaceholderText("Тут з'явиться переклад...")

        input_zoom, output_zoom = settings.get_zoom_steps()
        self._input_field.set_zoom_steps(input_zoom)
        self._output_field.set_zoom_steps(output_zoom)

        self._status_label = QLabel()
        self._status_label.setWordWrap(True)
        self._set_status("Готово", error=False)

        layout.addWidget(model_label)
        layout.addWidget(self._model_combo)
        layout.addWidget(direction_label)
        layout.addWidget(self._ua_en_radio)
        layout.addWidget(self._en_ua_radio)
        layout.addWidget(input_label)
        layout.addWidget(self._input_field)
        layout.addWidget(output_label)
        layout.addWidget(self._output_field, stretch=1)
        layout.addWidget(self._status_label)

        self._restore_ui_preferences()
        self._check_api_key()
        self._restore_window_geometry()

    def closeEvent(self, event: QCloseEvent) -> None:
        model_entry = get_model_by_index(self._model_combo.currentIndex())
        settings.save_ui_preferences(model_entry.model_id, self._current_direction())
        settings.save_zoom_steps(
            self._input_field.zoom_steps(),
            self._output_field.zoom_steps(),
        )
        settings.save_window_geometry_state(bytes(self.saveGeometry()))
        super().closeEvent(event)

    def _restore_window_geometry(self) -> None:
        saved = settings.get_window_geometry_state()
        if saved and self.restoreGeometry(QByteArray(saved)):
            return

        screen = QGuiApplication.primaryScreen()
        if screen:
            available = screen.availableGeometry()
            width = max(280, int(available.width() * 0.18))
            height = max(400, int(available.height() * 0.70))
            self.resize(width, height)
            self.move(available.right() - width - 16, available.top() + 16)

    def _restore_ui_preferences(self) -> None:
        model_id, direction = settings.get_ui_preferences()
        if model_id:
            index = self._model_combo.findData(model_id)
            if index >= 0:
                self._model_combo.setCurrentIndex(index)
        if direction == "en-ua":
            self._en_ua_radio.setChecked(True)
        elif direction == "ua-en":
            self._ua_en_radio.setChecked(True)

    def _create_menu_bar(self) -> None:
        menu_bar = self.menuBar()
        menu_bar.setFixedHeight(22)
        menu_bar.setStyleSheet(
            "QMenuBar { padding: 0px; spacing: 0px; background: transparent; }"
            "QMenuBar::item { padding: 1px 8px; margin: 0px; }"
            "QMenuBar::item:selected { background: #e5e7eb; }"
        )
        tools_menu = menu_bar.addMenu("Tools")
        history_action = tools_menu.addAction("Історія запитів")
        history_action.triggered.connect(self._open_history)

    def _open_history(self) -> None:
        if self._history_window is None:
            self._history_window = HistoryWindow(self)
            self._history_window.finished.connect(self._on_history_closed)
        self._history_window.refresh()
        self._history_window.show()
        self._history_window.raise_()
        self._history_window.activateWindow()

    def _on_history_closed(self) -> None:
        self._history_window = None

    def _check_api_key(self) -> None:
        entry = get_model_by_index(self._model_combo.currentIndex())
        api_key = os.environ.get(entry.env_key, "")
        if not api_key or api_key == "your_key_here":
            self._set_status(
                f"Увага: {entry.env_key} не налаштовано. Додайте ключ у файл .env.",
                error=True,
            )
        else:
            self._set_status("Готово", error=False)

    def _current_direction(self) -> str:
        return "ua-en" if self._ua_en_radio.isChecked() else "en-ua"

    def _set_status(self, message: str, *, error: bool) -> None:
        color = "#c0392b" if error else "#555555"
        self._status_label.setStyleSheet(f"color: {color};")
        self._status_label.setText(message)

    def _set_busy(self, busy: bool) -> None:
        self._input_field.setEnabled(not busy)
        self._model_combo.setEnabled(not busy)
        self._ua_en_radio.setEnabled(not busy)
        self._en_ua_radio.setEnabled(not busy)

    def _submit_translation(self) -> None:
        text = self._input_field.text().strip()
        if not text:
            return
        if self._worker is not None and self._worker.isRunning():
            return

        self._pending_source = text
        self._pending_direction = self._current_direction()
        model_entry = get_model_by_index(self._model_combo.currentIndex())
        self._pending_model_id = model_entry.model_id

        self._input_field.clear()
        self._set_busy(True)
        self._set_status("Перекладаю...", error=False)

        self._worker = TranslateWorker(text, self._pending_direction, model_entry, self)
        self._worker.finished.connect(self._on_translation_finished)
        self._worker.error.connect(self._on_translation_error)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.error.connect(self._worker.deleteLater)
        self._worker.start()

    def _show_result(self, result: str, direction: str) -> None:
        if direction == "en-ua":
            self._output_field.set_result_html(format_en_ua_output(result))
        elif direction == "ua-en":
            self._output_field.set_result_html(format_ua_en_output(result))
        else:
            self._output_field.set_result_plain(result)

    def _on_translation_finished(self, result: str) -> None:
        self._show_result(result, self._pending_direction)
        history.save_translation(
            self._pending_direction,
            self._pending_source,
            result,
            self._pending_model_id,
        )
        self._worker = None
        self._set_busy(False)
        self._set_status("Готово", error=False)
        self._input_field.setFocus()

    def _on_translation_error(self, message: str) -> None:
        self._worker = None
        self._set_busy(False)
        self._set_status(f"Помилка: {message}", error=True)
        self._input_field.setFocus()
