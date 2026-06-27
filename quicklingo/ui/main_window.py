from PySide6.QtCore import Qt, QByteArray

from PySide6.QtGui import QCloseEvent, QGuiApplication

from PySide6.QtWidgets import (

    QButtonGroup,

    QComboBox,

    QHBoxLayout,

    QLabel,

    QMainWindow,

    QPushButton,

    QRadioButton,

    QVBoxLayout,

    QWidget,

)



from quicklingo.config.loader import (

    get_directions,

    get_formatter,

    get_profiles_for_direction,

    reload_config,

    resolve_active_profile_id,

)

from quicklingo.db import history

from quicklingo.features import feature_changed, get_feature, is_enabled

from quicklingo.i18n import tr, translate_message

from quicklingo.input.hotkeys import copy_selection_to_clipboard, paste_text

from quicklingo.providers.registry import get_model_by_index, get_model_entries

from quicklingo import settings

from quicklingo.ui.history_window import HistoryWindow
from quicklingo.ui.dashboard_window import DashboardWindow
from quicklingo.ui.learning_window import LearningWindow

from quicklingo.ui.settings_dialog import SettingsDialog

from quicklingo.ui.zoomable_text_edit import ZoomableInputEdit, ZoomableTextEdit

from quicklingo.workers.translate_worker import TranslateWorker





class _QueuedRequest:

    __slots__ = ("text", "direction", "profile_id", "model_index")



    def __init__(self, text: str, direction: str, profile_id: str, model_index: int) -> None:

        self.text = text

        self.direction = direction

        self.profile_id = profile_id

        self.model_index = model_index





class MainWindow(QMainWindow):

    def __init__(self) -> None:

        super().__init__()

        self._worker: TranslateWorker | None = None

        self._pending_source = ""

        self._pending_direction = "ua-en"

        self._pending_profile_id = "detailed"

        self._pending_model_id = ""

        self._pending_from_cache = False

        self._last_error_message = ""

        self._request_queue: list[_QueuedRequest] = []

        self._replace_after_translate = False

        self._force_quit = False
        self._tray_manager = None
        self._history_window: HistoryWindow | None = None
        self._learning_window: LearningWindow | None = None
        self._dashboard_window: DashboardWindow | None = None

        self._direction_radios: list[tuple[QRadioButton, str]] = []

        self._direction_group: QButtonGroup | None = None

        self._main_layout: QVBoxLayout | None = None

        self._direction_row: QHBoxLayout | None = None

        self._status_key = "main.status_ready"

        self._status_params: dict = {}

        self._status_is_error = False



        self.setWindowTitle("QuickLingo")



        self._tools_menu = None

        self._history_action = None

        self._learning_action = None

        self._dashboard_action = None

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

        self._model_combo.currentIndexChanged.connect(lambda _: self._check_api_key())

        self._reload_model_combo()



        self._direction_label = QLabel()

        self._swap_direction_btn = QPushButton()

        self._swap_direction_btn.clicked.connect(self._swap_direction)



        self._profile_label = QLabel()

        self._profile_combo = QComboBox()

        self._profile_combo.currentIndexChanged.connect(self._on_profile_changed)



        self._direction_group = QButtonGroup(self)

        self._build_direction_radios()



        self._input_label = QLabel()

        self._input_field = ZoomableInputEdit()

        self._input_field.submit_requested.connect(self._submit_translation)



        self._output_label = QLabel()

        self._output_field = ZoomableTextEdit()

        self._output_field.set_text_selectable(True)



        self._cancel_btn = QPushButton()

        self._cancel_btn.clicked.connect(self._cancel_translation)

        self._cancel_btn.setVisible(False)

        self._retry_btn = QPushButton()

        self._retry_btn.clicked.connect(self._retry_translation)

        self._retry_btn.setVisible(False)



        input_zoom, output_zoom = settings.get_zoom_steps()

        self._input_field.set_zoom_steps(input_zoom)

        self._output_field.set_zoom_steps(output_zoom)



        self._status_label = QLabel()

        self._status_label.setWordWrap(True)



        action_row = QHBoxLayout()

        action_row.addWidget(self._cancel_btn)

        action_row.addWidget(self._retry_btn)

        action_row.addStretch()



        layout.addWidget(self._model_label)

        layout.addWidget(self._model_combo)

        layout.addWidget(self._direction_label)



        self._direction_row = QHBoxLayout()

        for radio, _direction_id in self._direction_radios:

            self._direction_row.addWidget(radio)

        self._direction_row.addWidget(self._swap_direction_btn)

        self._direction_row.addStretch()

        layout.addLayout(self._direction_row)



        layout.addWidget(self._profile_label)

        layout.addWidget(self._profile_combo)

        layout.addWidget(self._input_label)

        layout.addWidget(self._input_field)

        layout.addWidget(self._output_label)

        layout.addWidget(self._output_field, stretch=1)

        layout.addLayout(action_row)

        layout.addWidget(self._status_label)



        self._input_label_ref = self._input_label

        self._direction_group.buttonClicked.connect(lambda _: self._refresh_profile_combo())

        self.retranslate_ui()

        self._apply_window_features()

        self._restore_ui_preferences()

        self._refresh_profile_combo()

        self._check_api_key()

        self._restore_window_geometry()



    def retranslate_ui(self) -> None:

        self._model_label.setText(tr("main.model_label"))

        self._direction_label.setText(tr("main.direction_label"))

        self._profile_label.setText(tr("main.profile_label"))

        self._input_label.setText(tr("main.input_label"))

        self._input_field.setPlaceholderText(tr("main.input_placeholder"))

        self._output_label.setText(tr("main.output_label"))

        self._output_field.setPlaceholderText(tr("main.output_placeholder"))

        self._swap_direction_btn.setText(tr("main.swap_direction"))

        self._cancel_btn.setText(tr("main.cancel"))

        self._retry_btn.setText(tr("main.retry"))

        if self._tools_menu:

            self._tools_menu.setTitle(tr("main.menu_tools"))

        if self._history_action:

            self._history_action.setText(tr("main.menu_history"))

        if self._learning_action:

            self._learning_action.setText(tr("main.menu_learning"))

        if self._dashboard_action:

            self._dashboard_action.setText(tr("main.menu_dashboard"))

        if self._settings_action:

            self._settings_action.setText(tr("main.menu_settings"))

        if self._status_is_error:

            self._set_status(self._status_key, error=True, **self._status_params)

        elif self._status_key == "main.status_api_key":

            self._check_api_key()

        elif self._status_key == "main.status_cached":

            self._set_status("main.status_cached", error=False)

        elif self._status_key == "main.status_cancelled":

            self._set_status("main.status_cancelled", error=False)

        else:

            self._set_status(self._status_key, error=False, **self._status_params)

        self._refresh_profile_combo()

        if self._history_window is not None:

            self._history_window.retranslate_ui()

        if self._learning_window is not None:

            self._learning_window.retranslate_ui()



    def apply_features(self) -> None:

        self._apply_window_features()

        self._output_field.set_text_selectable(True)



    def translate_external_text(self, text: str, *, replace_in_place: bool = False) -> None:

        text = text.strip()

        if not text:

            return

        self._replace_after_translate = replace_in_place and is_enabled("input.replace_in_place")

        self.show()

        self.raise_()

        self.activateWindow()

        self._input_field.setPlainText(text)

        self._submit_translation()



    def translate_selection(self) -> None:

        if not is_enabled("input.global_hotkey.translate_selection"):

            return

        text = copy_selection_to_clipboard()

        if text:

            self.translate_external_text(text, replace_in_place=True)



    def translate_clipboard(self) -> None:

        if not is_enabled("input.global_hotkey.translate_clipboard"):

            return

        text = QGuiApplication.clipboard().text().strip()

        if text:

            self.translate_external_text(text, replace_in_place=False)



    def translate_double_ctrl_c(self) -> None:

        if not is_enabled("input.double_ctrl_c"):

            return

        text = QGuiApplication.clipboard().text().strip()

        if text:

            self.translate_external_text(text, replace_in_place=False)



    def _apply_window_features(self) -> None:

        flags = Qt.WindowType.Window

        if is_enabled("ui.always_on_top"):

            flags |= Qt.WindowType.WindowStaysOnTopHint

        self.setWindowFlags(flags)

        self.show()



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

        if self._main_layout is None or self._direction_row is None:

            return

        selected = self._current_direction()

        while self._direction_row.count():
            item = self._direction_row.takeAt(0)
            widget = item.widget()
            if widget is not None and widget is not self._swap_direction_btn:
                widget.deleteLater()

        self._build_direction_radios()

        for radio, _direction_id in self._direction_radios:

            self._direction_row.addWidget(radio)

        self._direction_row.addWidget(self._swap_direction_btn)

        self._direction_row.addStretch()

        self._direction_group.buttonClicked.connect(lambda _: self._refresh_profile_combo())

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

        self._refresh_profile_combo()



    def closeEvent(self, event: QCloseEvent) -> None:

        if (

            not self._force_quit

            and is_enabled("ui.system_tray")

            and hasattr(self, "_tray_manager")

            and self._tray_manager is not None

        ):

            event.ignore()

            self.hide()

            return

        model_entry = get_model_by_index(self._model_combo.currentIndex())

        settings.save_ui_preferences(model_entry.model_id, self._current_direction())

        if is_enabled("ui.remember_zoom"):

            settings.save_zoom_steps(

                self._input_field.zoom_steps(),

                self._output_field.zoom_steps(),

            )

        if is_enabled("ui.remember_geometry"):

            settings.save_window_geometry_state(bytes(self.saveGeometry()))

        super().closeEvent(event)



    def _restore_window_geometry(self) -> None:

        if not is_enabled("ui.remember_geometry"):

            self._default_geometry()

            return

        saved = settings.get_window_geometry_state()

        if saved and self.restoreGeometry(QByteArray(saved)):

            return

        self._default_geometry()



    def _default_geometry(self) -> None:

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

        self._learning_action = self._tools_menu.addAction("")

        self._learning_action.triggered.connect(self._open_learning)

        self._dashboard_action = self._tools_menu.addAction("")

        self._dashboard_action.triggered.connect(self._open_dashboard)



    def _open_history(self) -> None:

        if self._history_window is None:

            self._history_window = HistoryWindow(self)

            self._history_window.finished.connect(self._on_history_closed)

            self._history_window.reopen_requested.connect(self._reopen_from_history)
            self._history_window.add_to_deck_requested.connect(self._add_vocab_to_deck)

        self._history_window.refresh()

        self._history_window.show()

        self._history_window.raise_()

        self._history_window.activateWindow()

    def _open_learning(self) -> None:
        if self._learning_window is None:
            self._learning_window = LearningWindow(self)
            self._learning_window.finished.connect(self._on_learning_closed)
        self._learning_window._reload_tags()
        self._learning_window._reload_decks()
        self._learning_window._reload_model_combo()
        self._learning_window.show()
        self._learning_window.raise_()
        self._learning_window.activateWindow()

    def _on_learning_closed(self) -> None:
        self._learning_window = None

    def _open_dashboard(self) -> None:
        if self._dashboard_window is None:
            self._dashboard_window = DashboardWindow(self)
            self._dashboard_window.finished.connect(self._on_dashboard_closed)
        self._dashboard_window.refresh()
        self._dashboard_window.show()
        self._dashboard_window.raise_()
        self._dashboard_window.activateWindow()

    def _on_dashboard_closed(self) -> None:
        self._dashboard_window = None

    def _add_vocab_to_deck(
        self, word: str, source: str, direction: str, tag: str, result: str
    ) -> None:
        if self._learning_window is None:
            self._learning_window = LearningWindow(self)
            self._learning_window.finished.connect(self._on_learning_closed)
        if direction == "en-ua":
            front, back = word, source.strip()
        else:
            front, back = source.strip() or word, word
        self._learning_window.add_vocab_card(
            front,
            back,
            context=result.strip()[:400],
            tag=tag,
            direction=direction,
        )
        self._learning_window.show()
        self._learning_window.raise_()
        self._learning_window.activateWindow()



    def _open_settings(self) -> None:

        dialog = SettingsDialog(self)

        dialog.config_changed.connect(self._on_config_changed)

        dialog.api_keys_changed.connect(self._check_api_key)

        dialog.exec()

        self.apply_features()

        self._check_api_key()



    def _reload_model_combo(self) -> None:
        current = self._model_combo.currentData() if self._model_combo.count() else None
        if current is None:
            stored_model, _ = settings.get_ui_preferences()
            current = stored_model
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
        if hasattr(self, "_status_label"):
            self._check_api_key()

    def _on_config_changed(self) -> None:

        reload_config()

        self._rebuild_direction_radios()

        self._reload_model_combo()

        if self._learning_window is not None:
            self._learning_window._reload_model_combo()



    def _on_history_closed(self) -> None:

        self._history_window = None



    def _reopen_from_history(

        self, source_text: str, direction: str, profile_id: str

    ) -> None:

        for radio, direction_id in self._direction_radios:

            radio.setChecked(direction_id == direction)

        self._refresh_profile_combo()

        index = self._profile_combo.findData(profile_id)

        if index >= 0:

            self._profile_combo.setCurrentIndex(index)

        self._input_field.setPlainText(source_text)

        self.raise_()

        self.activateWindow()

        self._input_field.setFocus()



    def _check_api_key(self) -> None:

        entry = get_model_by_index(self._model_combo.currentIndex())

        api_key = settings.get_api_key(entry.api_provider)

        if not api_key:

            self._set_status(

                "main.status_api_key",

                error=True,

                provider=tr(f"settings.api_keys.provider_{entry.api_provider}"),

            )

        elif not self._worker or not self._worker.isRunning():

            self._set_status("main.status_ready", error=False)



    def _current_direction(self) -> str:

        for radio, direction_id in self._direction_radios:

            if radio.isChecked():

                return direction_id

        directions = get_directions()

        return directions[0].id if directions else "ua-en"



    def _refresh_profile_combo(self) -> None:

        direction = self._current_direction()

        active_id = self._profile_combo.currentData()

        self._profile_combo.blockSignals(True)

        self._profile_combo.clear()

        for profile in get_profiles_for_direction(direction):

            self._profile_combo.addItem(profile.name, profile.id)

        target = active_id or resolve_active_profile_id(direction)

        index = self._profile_combo.findData(target)

        if index < 0:

            index = self._profile_combo.findData(resolve_active_profile_id(direction))

        if index >= 0:

            self._profile_combo.setCurrentIndex(index)

        self._profile_combo.blockSignals(False)



    def _on_profile_changed(self) -> None:

        direction = self._current_direction()

        profile_id = self._profile_combo.currentData()

        if not profile_id:

            return

        active = settings.get_active_profiles()

        if active.get(direction) == profile_id:

            return

        active[direction] = profile_id

        settings.save_active_profiles(active)



    def _swap_direction(self) -> None:

        directions = get_directions()

        if len(directions) < 2:

            return

        current = self._current_direction()

        ids = [d.id for d in directions]

        if current not in ids:

            target_id = directions[0].id

        else:

            idx = ids.index(current)

            target_id = ids[(idx + 1) % len(ids)]

        for radio, direction_id in self._direction_radios:

            if direction_id == target_id:

                radio.setChecked(True)

                break

        self._refresh_profile_combo()



    def _current_profile_id(self) -> str:

        profile_id = self._profile_combo.currentData()

        if profile_id:

            return profile_id

        return resolve_active_profile_id(self._current_direction())



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

        self._profile_combo.setEnabled(not busy)

        self._swap_direction_btn.setEnabled(not busy)

        for radio, _direction_id in self._direction_radios:

            radio.setEnabled(not busy)

        self._cancel_btn.setVisible(busy)

        self._retry_btn.setVisible(False)



    def _submit_translation(self) -> None:

        text = self._input_field.input_text()

        if not text:

            return



        if self._worker is not None and self._worker.isRunning():

            if is_enabled("translation.request_queue"):

                self._request_queue.append(

                    _QueuedRequest(

                        text,

                        self._current_direction(),

                        self._current_profile_id(),

                        self._model_combo.currentIndex(),

                    )

                )

                self._input_field.clear_input()

                self._set_status("main.status_queued", error=False, count=len(self._request_queue))

            return



        self._start_translation(text)



    def _start_translation(self, text: str) -> None:

        self._pending_source = text

        self._pending_direction = self._current_direction()

        self._pending_profile_id = self._current_profile_id()

        model_entry = get_model_by_index(self._model_combo.currentIndex())

        self._pending_model_id = model_entry.model_id

        self._pending_from_cache = False

        self._last_error_message = ""



        cached = None

        if is_enabled("translation.response_cache"):

            ttl = int(get_feature("translation.response_cache").get("ttl_days", 30))

            cached = history.find_cached(

                self._pending_direction,

                text,

                self._pending_profile_id,

                ttl_days=ttl,

            )



        self._input_field.clear_input()



        if cached is not None:

            self._pending_from_cache = True

            self._on_translation_finished(cached)

            return



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

        self._worker.chunk.connect(self._on_translation_chunk)

        self._worker.error.connect(self._on_translation_error)

        self._worker.cancelled.connect(self._on_translation_cancelled)

        self._worker.finished.connect(self._worker.deleteLater)

        self._worker.error.connect(self._worker.deleteLater)

        self._worker.cancelled.connect(self._worker.deleteLater)

        self._worker.start()



    def _cancel_translation(self) -> None:

        if self._worker is not None and self._worker.isRunning():

            self._worker.cancel()



    def _retry_translation(self) -> None:

        if not self._pending_source:

            return

        self._input_field.setPlainText(self._pending_source)

        self._submit_translation()



    def _show_result(self, result: str, direction: str, profile_id: str) -> None:

        formatter = get_formatter(direction, profile_id)

        self._output_field.set_result_html(formatter(result))

    def _on_translation_chunk(self, partial: str) -> None:
        self._output_field.set_result_plain(partial)



    def _on_translation_finished(self, result: str) -> None:

        from_cache = self._pending_from_cache

        self._show_result(result, self._pending_direction, self._pending_profile_id)

        if is_enabled("history.auto_save") and not from_cache:

            history.save_translation(

                self._pending_direction,

                self._pending_source,

                result,

                self._pending_model_id,

                profile_id=self._pending_profile_id,

            )

        if is_enabled("ui.auto_copy_result"):

            QGuiApplication.clipboard().setText(result)

        if self._replace_after_translate:

            paste_text(result)

            self._replace_after_translate = False

        self._worker = None

        self._set_busy(False)

        if from_cache:

            self._set_status("main.status_cached", error=False)

        else:

            self._set_status("main.status_ready", error=False)

        self._process_queue()

        self._input_field.setFocus()



    def _on_translation_error(self, message: str) -> None:

        self._last_error_message = message

        self._worker = None

        self._set_busy(False)

        self._retry_btn.setVisible(True)

        self._set_status(

            "main.status_error",

            error=True,

            message=message,

        )

        self._process_queue()

        self._input_field.setFocus()



    def _on_translation_cancelled(self) -> None:

        self._worker = None

        self._set_busy(False)

        self._set_status("main.status_cancelled", error=False)

        self._process_queue()

        self._input_field.setFocus()



    def _process_queue(self) -> None:

        if not is_enabled("translation.request_queue") or not self._request_queue:

            return

        if self._worker is not None and self._worker.isRunning():

            return

        next_req = self._request_queue.pop(0)

        index = next_req.model_index

        if 0 <= index < self._model_combo.count():

            self._model_combo.setCurrentIndex(index)

        for radio, direction_id in self._direction_radios:

            radio.setChecked(direction_id == next_req.direction)

        self._refresh_profile_combo()

        profile_index = self._profile_combo.findData(next_req.profile_id)

        if profile_index >= 0:

            self._profile_combo.setCurrentIndex(profile_index)

        self._start_translation(next_req.text)


