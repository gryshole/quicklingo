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

from quicklingo.config.loader import get_directions, get_formatter, reload_config, resolve_active_profile_id
from quicklingo.db import history
from quicklingo.i18n import tr, translate_message
from quicklingo.providers.registry import get_model_by_index, get_model_entries
from quicklingo import settings
from quicklingo.ui.history_window import HistoryWindow
from quicklingo.ui.settings_dialog import SettingsDialog
from quicklingo.ui.zoomable_text_edit import ZoomableLineEdit, ZoomableTextEdit
from quicklingo.workers.translate_worker import TranslateWorker


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._worker: TranslateWorker | None = None
        self._pending_source = ""
        self._pending_direction = "ua-en"
        self._pending_profile_id = "detailed"
        self._pending_model_id = ""
        self._history_window: HistoryWindow | None = None
        self._direction_radios: list[tuple[QRadioButton, str]] = []
        self._direction_group: QButtonGroup | None = None
        self._main_layout: QVBoxLayout | None = None
        self._status_key = "main.status_ready"
        self._status_params: dict = {}
        self._status_is_error = False

        self.setWindowTitle("QuickLingo")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)

        self._tools_menu = None
        self._history_action = None
        self._settings_action = None
        self._create_menu_bar()

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        self._main_layout = layout
        layout.setContentsMargins(12, 8, 12, 12)
        layout.setSpacing(10)

        self._model_label = QLabel()
        self._model_combo = QComboBox()
        for entry in get_model_entries():
            self._model_combo.addItem(entry.display_name, entry.model_id)
        self._model_combo.currentIndexChanged.connect(lambda _: self._check_api_key())

        self._direction_label = QLabel()
        self._direction_group = QButtonGroup(self)
        self._build_direction_radios()

        self._input_label = QLabel()
        self._input_field = ZoomableLineEdit()
        self._input_field.returnPressed.connect(self._submit_translation)

        self._output_label = QLabel()
        self._output_field = ZoomableTextEdit()

        input_zoom, output_zoom = settings.get_zoom_steps()
        self._input_field.set_zoom_steps(input_zoom)
        self._output_field.set_zoom_steps(output_zoom)

        self._status_label = QLabel()
        self._status_label.setWordWrap(True)

        layout.addWidget(self._model_label)
        layout.addWidget(self._model_combo)
        layout.addWidget(self._direction_label)
        for radio, _direction_id in self._direction_radios:
            layout.addWidget(radio)
        layout.addWidget(self._input_label)
        layout.addWidget(self._input_field)
        layout.addWidget(self._output_label)
        layout.addWidget(self._output_field, stretch=1)
        layout.addWidget(self._status_label)

        self._input_label_ref = self._input_label
        self.retranslate_ui()
        self._restore_ui_preferences()
        self._check_api_key()
        self._restore_window_geometry()

    def retranslate_ui(self) -> None:
        self._model_label.setText(tr("main.model_label"))
        self._direction_label.setText(tr("main.direction_label"))
        self._input_label.setText(tr("main.input_label"))
        self._input_field.setPlaceholderText(tr("main.input_placeholder"))
        self._output_label.setText(tr("main.output_label"))
        self._output_field.setPlaceholderText(tr("main.output_placeholder"))
        if self._tools_menu:
            self._tools_menu.setTitle(tr("main.menu_tools"))
        if self._history_action:
            self._history_action.setText(tr("main.menu_history"))
        if self._settings_action:
            self._settings_action.setText(tr("main.menu_settings"))
        if self._status_is_error:
            self._set_status(self._status_key, error=True, **self._status_params)
        elif self._status_key == "main.status_api_key":
            self._check_api_key()
        else:
            self._set_status(self._status_key, error=False, **self._status_params)
        if self._history_window is not None:
            self._history_window.retranslate_ui()

    def _build_direction_radios(self) -> None:
        self._direction_radios.clear()
        if self._direction_group is not None:
            for btn in self._direction_group.buttons():
                self._direction_group.removeButton(btn)
        self._direction_group = QButtonGroup(self)
        for index, direction in enumerate(get_directions()):
            radio = QRadioButton(direction.label)
            if index == 0:
                radio.setChecked(True)
            self._direction_group.addButton(radio)
            self._direction_radios.append((radio, direction.id))

    def _rebuild_direction_radios(self) -> None:
        if self._main_layout is None:
            return
        selected = self._current_direction()
        for radio, _ in self._direction_radios:
            self._main_layout.removeWidget(radio)
            radio.deleteLater()
        self._build_direction_radios()
        insert_at = self._main_layout.indexOf(self._input_label_ref)
        for offset, (radio, _direction_id) in enumerate(self._direction_radios):
            self._main_layout.insertWidget(insert_at + offset, radio)
        for radio, direction_id in self._direction_radios:
            if direction_id == selected:
                radio.setChecked(True)
                break
        else:
            if self._direction_radios:
                self._direction_radios[0][0].setChecked(True)
        model_id, direction = settings.get_ui_preferences()
        if direction:
            for radio, direction_id in self._direction_radios:
                if direction_id == direction:
                    radio.setChecked(True)
                    break

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
        if direction:
            for radio, direction_id in self._direction_radios:
                if direction_id == direction:
                    radio.setChecked(True)
                    break

    def _create_menu_bar(self) -> None:
        menu_bar = self.menuBar()
        menu_bar.setFixedHeight(22)
        menu_bar.setStyleSheet(
            "QMenuBar { padding: 0px; spacing: 0px; background: transparent; }"
            "QMenuBar::item { padding: 1px 8px; margin: 0px; }"
            "QMenuBar::item:selected { background: #e5e7eb; }"
        )
        self._tools_menu = menu_bar.addMenu("")
        self._settings_action = self._tools_menu.addAction("")
        self._settings_action.triggered.connect(self._open_settings)
        self._history_action = self._tools_menu.addAction("")
        self._history_action.triggered.connect(self._open_history)

    def _open_history(self) -> None:
        if self._history_window is None:
            self._history_window = HistoryWindow(self)
            self._history_window.finished.connect(self._on_history_closed)
        self._history_window.refresh()
        self._history_window.show()
        self._history_window.raise_()
        self._history_window.activateWindow()

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self)
        dialog.config_changed.connect(self._on_config_changed)
        dialog.api_keys_changed.connect(self._check_api_key)
        dialog.exec()
        self._check_api_key()

    def _on_config_changed(self) -> None:
        reload_config()
        self._rebuild_direction_radios()

    def _on_history_closed(self) -> None:
        self._history_window = None

    def _check_api_key(self) -> None:
        entry = get_model_by_index(self._model_combo.currentIndex())
        api_key = settings.get_api_key(entry.api_provider)
        if not api_key:
            self._set_status(
                "main.status_api_key",
                error=True,
                provider=tr(f"settings.api_keys.provider_{entry.api_provider}"),
            )
        else:
            self._set_status("main.status_ready", error=False)

    def _current_direction(self) -> str:
        for radio, direction_id in self._direction_radios:
            if radio.isChecked():
                return direction_id
        directions = get_directions()
        return directions[0].id if directions else "ua-en"

    def _set_status(self, key: str, *, error: bool, **params) -> None:
        self._status_key = key
        self._status_params = params
        self._status_is_error = error
        if key == "main.status_error":
            message = tr(key, message=translate_message(params.get("message", "")))
        else:
            message = tr(key, **params)
        color = "#c0392b" if error else "#555555"
        self._status_label.setStyleSheet(f"color: {color};")
        self._status_label.setText(message)

    def _set_busy(self, busy: bool) -> None:
        self._input_field.setEnabled(not busy)
        self._model_combo.setEnabled(not busy)
        for radio, _direction_id in self._direction_radios:
            radio.setEnabled(not busy)

    def _submit_translation(self) -> None:
        text = self._input_field.text().strip()
        if not text:
            return
        if self._worker is not None and self._worker.isRunning():
            return

        self._pending_source = text
        self._pending_direction = self._current_direction()
        self._pending_profile_id = resolve_active_profile_id(self._pending_direction)
        model_entry = get_model_by_index(self._model_combo.currentIndex())
        self._pending_model_id = model_entry.model_id

        self._input_field.clear()
        self._set_busy(True)
        self._set_status("main.status_translating", error=False)

        self._worker = TranslateWorker(
            text,
            self._pending_direction,
            model_entry,
            profile_id=self._pending_profile_id,
            parent=self,
        )
        self._worker.finished.connect(self._on_translation_finished)
        self._worker.error.connect(self._on_translation_error)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.error.connect(self._worker.deleteLater)
        self._worker.start()

    def _show_result(self, result: str, direction: str, profile_id: str) -> None:
        formatter = get_formatter(direction, profile_id)
        self._output_field.set_result_html(formatter(result))

    def _on_translation_finished(self, result: str) -> None:
        self._show_result(result, self._pending_direction, self._pending_profile_id)
        history.save_translation(
            self._pending_direction,
            self._pending_source,
            result,
            self._pending_model_id,
        )
        self._worker = None
        self._set_busy(False)
        self._set_status("main.status_ready", error=False)
        self._input_field.setFocus()

    def _on_translation_error(self, message: str) -> None:
        self._worker = None
        self._set_busy(False)
        self._set_status(
            "main.status_error",
            error=True,
            message=str(exc),
        )
        self._input_field.setFocus()
