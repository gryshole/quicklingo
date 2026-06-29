from PySide6.QtCore import Qt, QByteArray, QUrl, Signal

from PySide6.QtGui import QCloseEvent, QDesktopServices, QGuiApplication, QHideEvent, QShowEvent

from PySide6.QtWidgets import (

    QApplication,

    QButtonGroup,

    QComboBox,

    QHBoxLayout,

    QLabel,

    QMainWindow,

    QMessageBox,

    QProgressDialog,

    QPushButton,

    QRadioButton,

    QSizePolicy,

    QVBoxLayout,

    QWidget,

)



import os
import sys
from pathlib import Path



from quicklingo import app as ql_app
from quicklingo.config.loader import (

    get_directions,

    get_formatter,

    get_profiles_for_direction,

    reload_config,

    resolve_active_profile_id,

)

from quicklingo.db import history

from quicklingo.features import feature_changed, get_feature, is_enabled, save_features

from quicklingo.i18n import tr, translate_message

from quicklingo.input.hotkeys import copy_selection_to_clipboard, paste_text
from quicklingo.input.tutor_capture_log import log_debug

from quicklingo.providers.registry import get_model_by_index, get_model_entries
from quicklingo.providers.setup_info import PROVIDER_HINT_KEYS, provider_needs_api_key

from quicklingo import settings

from quicklingo.ui.help_dialog import show_help
from quicklingo.ui.history_window import HistoryWindow
from quicklingo.ui.dashboard_window import DashboardWindow
from quicklingo.ui.learning_window import LearningWindow

from quicklingo.ui.settings_dialog import SettingsDialog

from quicklingo.ui.zoomable_text_edit import ZoomableInputEdit, ZoomableLineEdit, ZoomableTextEdit

from quicklingo.update.checker import (
    UpdateInfo,
    current_version,
    default_download_path,
    is_newer,
)
from quicklingo.update.install import launch_update, updater_available
from quicklingo.version import __version__
from quicklingo.workers.translate_worker import TranslateWorker
from quicklingo.workers.update_worker import UpdateCheckWorker, UpdateDownloadWorker





class _QueuedRequest:

    __slots__ = ("text", "direction", "profile_id", "model_index")



    def __init__(self, text: str, direction: str, profile_id: str, model_index: int) -> None:

        self.text = text

        self.direction = direction

        self.profile_id = profile_id

        self.model_index = model_index





class MainWindow(QMainWindow):

    visibility_changed = Signal(bool)

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

        self._help_menu = None

        self._help_about_action = None

        self._help_check_updates_action = None

        self._help_models_action = None

        self._help_directions_profiles_action = None

        self._help_formatters_action = None

        self._help_features_action = None

        self._help_history_action = None

        self._help_learning_action = None

        self._help_dashboard_action = None

        self._help_glossary_action = None

        self._update_check_worker: UpdateCheckWorker | None = None

        self._update_download_worker: UpdateDownloadWorker | None = None

        self._update_progress: QProgressDialog | None = None

        self._pending_update_info: UpdateInfo | None = None

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

        self._tutor_capture_btn = QPushButton()

        self._tutor_capture_btn.setCheckable(True)

        self._tutor_capture_btn.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )

        self._tutor_capture_btn.toggled.connect(self._on_tutor_capture_btn_toggled)

        self._input_header = QHBoxLayout()

        self._input_header.setContentsMargins(0, 0, 0, 0)

        self._input_header.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self._input_header.addWidget(self._input_label, stretch=1)

        self._input_header.addWidget(self._tutor_capture_btn)

        self._input_single_line_mode: bool | None = None
        self._input_field = self._create_input_field()
        self._input_single_line_mode = self._single_line_input_enabled()
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
        self._status_label.setTextFormat(Qt.TextFormat.RichText)
        self._status_label.setOpenExternalLinks(True)



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

        layout.addLayout(self._input_header)

        layout.addWidget(self._input_field)

        layout.addWidget(self._output_label)

        layout.addWidget(self._output_field, stretch=1)

        layout.addLayout(action_row)

        layout.addWidget(self._status_label)



        self._input_label_ref = self._input_label

        self._refresh_input_label()

        self.sync_tutor_capture_ui()

        self._direction_group.buttonClicked.connect(lambda _: self._refresh_profile_combo())

        self.retranslate_ui()

        self._apply_window_features()

        self._restore_ui_preferences()

        self._refresh_profile_combo()

        self._check_api_key()

        self._restore_window_geometry()



    def retranslate_ui(self) -> None:

        self.setWindowTitle(f"QuickLingo {__version__}")

        self._model_label.setText(tr("main.model_label"))

        self._direction_label.setText(tr("main.direction_label"))

        self._profile_label.setText(tr("main.profile_label"))

        self._refresh_input_label()
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

        if self._help_menu:

            self._help_menu.setTitle(tr("main.menu_help"))

        if self._help_about_action:

            self._help_about_action.setText(tr("main.menu_help_about"))

        if self._help_check_updates_action:

            self._help_check_updates_action.setText(tr("main.menu_help_check_updates"))

        if self._help_models_action:

            self._help_models_action.setText(tr("main.menu_help_models"))

        if self._help_directions_profiles_action:

            self._help_directions_profiles_action.setText(
                tr("main.menu_help_directions_profiles")
            )

        if self._help_formatters_action:

            self._help_formatters_action.setText(tr("main.menu_help_formatters"))

        if self._help_features_action:

            self._help_features_action.setText(tr("main.menu_help_features"))

        if self._help_history_action:

            self._help_history_action.setText(tr("main.menu_help_history"))

        if self._help_learning_action:

            self._help_learning_action.setText(tr("main.menu_help_learning"))

        if self._help_dashboard_action:

            self._help_dashboard_action.setText(tr("main.menu_help_dashboard"))

        if self._help_glossary_action:

            self._help_glossary_action.setText(tr("main.menu_help_glossary"))

        self._tutor_capture_btn.setText(tr("main.tutor_capture_btn"))

        self.sync_tutor_capture_ui()

        if self._status_is_error:

            self._set_status(self._status_key, error=True, **self._status_params)

        elif self._status_key == "main.status_api_key_hint":

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

        self._rebuild_input_field()

        self._refresh_input_label()

        self.sync_tutor_capture_ui()



    def sync_tutor_capture_ui(self) -> None:

        import sys

        enabled = is_enabled("input.tutor_capture")

        self._tutor_capture_btn.blockSignals(True)

        self._tutor_capture_btn.setChecked(enabled)

        self._tutor_capture_btn.blockSignals(False)

        self._tutor_capture_btn.setEnabled(sys.platform == "win32")

        self._apply_tutor_capture_btn_style(enabled)

        self._render_status()



    def _apply_tutor_capture_btn_style(self, enabled: bool) -> None:

        import sys

        # Same box model in both states so the input label row does not shift.
        box = "border: 1px solid; padding: 4px 10px; min-width: 72px; min-height: 24px; max-height: 24px;"
        if sys.platform != "win32":

            self._tutor_capture_btn.setToolTip(tr("main.tutor_capture_btn_tooltip_unsupported"))

            self._tutor_capture_btn.setStyleSheet(
                f"QPushButton {{ {box} border-color: #c8c8c8; background: #f3f4f6; }}"
            )

        elif enabled:

            self._tutor_capture_btn.setStyleSheet(
                "QPushButton { "
                f"{box} "
                "background-color: #dbeafe; border-color: #93c5fd; font-weight: bold; "
                "}"
            )

            self._tutor_capture_btn.setToolTip(tr("main.tutor_capture_btn_tooltip_on"))

        else:

            self._tutor_capture_btn.setStyleSheet(
                "QPushButton { "
                f"{box} "
                "background-color: #f9fafb; border-color: #d1d5db; "
                "}"
            )

            self._tutor_capture_btn.setToolTip(tr("main.tutor_capture_btn_tooltip_off"))



    def _on_tutor_capture_btn_toggled(self, checked: bool) -> None:

        if checked == is_enabled("input.tutor_capture"):

            return

        self._apply_tutor_capture_btn_style(checked)

        if self._status_key == "main.status_ready" and not self._status_is_error:

            if checked:

                self._status_label.setStyleSheet("color: #555555;")

                self._status_label.setText(tr("main.status_tutor_capture_active"))

            else:

                self._status_label.setStyleSheet("color: #555555;")

                self._status_label.setText(tr("main.status_ready"))

        save_features({"input.tutor_capture": {"enabled": checked}})



    def is_translation_busy(self) -> bool:

        return self._worker is not None and self._worker.isRunning()



    def _tutor_input_block_reason(self) -> str | None:
        if not is_enabled("input.tutor_capture"):
            return "feature_disabled"
        modal = QApplication.activeModalWidget()
        if modal is not None:
            return f"modal_open:{type(modal).__name__}"
        if self.is_translation_busy():
            return "translation_busy"
        return None

    def _tutor_input_allowed(self) -> bool:
        return self._tutor_input_block_reason() is None

    def on_tutor_character(self, char: str) -> None:
        reason = self._tutor_input_block_reason()
        if reason is not None:
            log_debug(f"UI reject char={char!r} reason={reason}")
            return

        if isinstance(self._input_field, ZoomableLineEdit):

            self._input_field.setText(self._input_field.text() + char)

        else:

            self._input_field.setPlainText(self._input_field.toPlainText() + char)



    def on_tutor_backspace(self) -> None:
        reason = self._tutor_input_block_reason()
        if reason is not None:
            log_debug(f"UI reject backspace reason={reason}")
            return

        if isinstance(self._input_field, ZoomableLineEdit):

            text = self._input_field.text()

            if text:

                self._input_field.setText(text[:-1])

        else:

            text = self._input_field.toPlainText()

            if text:

                self._input_field.setPlainText(text[:-1])



    def on_tutor_enter(self) -> None:
        reason = self._tutor_input_block_reason()
        if reason is not None:
            log_debug(f"UI reject enter reason={reason}")
            return

        self._submit_translation()



    def showEvent(self, event: QShowEvent) -> None:

        super().showEvent(event)

        self.visibility_changed.emit(True)



    def hideEvent(self, event: QHideEvent) -> None:

        super().hideEvent(event)

        self.visibility_changed.emit(False)



    def _single_line_input_enabled(self) -> bool:

        return is_enabled("ui.single_line_input")



    def _create_input_field(self):

        if self._single_line_input_enabled():

            return ZoomableLineEdit()

        return ZoomableInputEdit()



    def _rebuild_input_field(self) -> None:

        if self._main_layout is None:

            return

        current_mode = self._single_line_input_enabled()

        if self._input_single_line_mode == current_mode:

            return

        self._input_single_line_mode = current_mode

        text = self._input_field.input_text()

        zoom = self._input_field.zoom_steps()

        enabled = self._input_field.isEnabled()

        placeholder = self._input_field.placeholderText()

        field_index = self._main_layout.indexOf(self._input_field)

        self._main_layout.removeWidget(self._input_field)

        self._input_field.deleteLater()

        self._input_field = self._create_input_field()

        self._input_field.submit_requested.connect(self._submit_translation)

        self._input_field.set_zoom_steps(zoom)

        self._input_field.setEnabled(enabled)

        if placeholder:

            self._input_field.setPlaceholderText(placeholder)

        if text:

            self._input_field.set_input_text(text)

        self._main_layout.insertWidget(field_index, self._input_field)



    def _refresh_input_label(self) -> None:

        label_key = (

            "main.input_label_single"

            if self._single_line_input_enabled()

            else "main.input_label"

        )

        self._input_label.setText(tr(label_key))



    def translate_external_text(self, text: str, *, replace_in_place: bool = False) -> None:

        text = text.strip()

        if not text:

            return

        self._replace_after_translate = replace_in_place and is_enabled("input.replace_in_place")

        self.show()

        self.raise_()

        self.activateWindow()

        self._input_field.set_input_text(text)

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

        want_on_top = is_enabled("ui.always_on_top")
        has_on_top = bool(self.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
        if want_on_top == has_on_top:
            return

        flags = self.windowFlags()
        if want_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowType.WindowStaysOnTopHint

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

        self._help_menu = menu_bar.addMenu("")

        self._help_about_action = self._help_menu.addAction("")

        self._help_about_action.triggered.connect(self._open_help_about)

        self._help_check_updates_action = self._help_menu.addAction("")

        self._help_check_updates_action.triggered.connect(self._check_for_updates)

        self._help_menu.addSeparator()

        self._help_models_action = self._help_menu.addAction("")

        self._help_models_action.triggered.connect(self._open_help_models)

        self._help_directions_profiles_action = self._help_menu.addAction("")

        self._help_directions_profiles_action.triggered.connect(
            self._open_help_directions_profiles
        )

        self._help_formatters_action = self._help_menu.addAction("")

        self._help_formatters_action.triggered.connect(self._open_help_formatters)

        self._help_features_action = self._help_menu.addAction("")

        self._help_features_action.triggered.connect(self._open_help_features)

        self._help_history_action = self._help_menu.addAction("")

        self._help_history_action.triggered.connect(self._open_help_history)

        self._help_learning_action = self._help_menu.addAction("")

        self._help_learning_action.triggered.connect(self._open_help_learning)

        self._help_dashboard_action = self._help_menu.addAction("")

        self._help_dashboard_action.triggered.connect(self._open_help_dashboard)

        self._help_glossary_action = self._help_menu.addAction("")

        self._help_glossary_action.triggered.connect(self._open_help_glossary)



    def _open_help_about(self) -> None:

        show_help("about", self)

    def _check_for_updates(self) -> None:
        if self._update_check_worker is not None and self._update_check_worker.isRunning():
            return

        self._update_check_worker = UpdateCheckWorker(self)
        self._update_check_worker.finished_ok.connect(self._on_update_check_ok)
        self._update_check_worker.finished_error.connect(self._on_update_check_error)
        self._update_check_worker.start()

    def _on_update_check_error(self, message: str) -> None:
        QMessageBox.warning(
            self,
            tr("common.error"),
            tr("update.error").format(message=message),
        )

    def _on_update_check_ok(self, info: UpdateInfo) -> None:
        current = current_version()
        if not is_newer(info.latest_version, current):
            QMessageBox.information(
                self,
                tr("main.menu_help_check_updates"),
                tr("update.up_to_date").format(version=current),
            )
            return

        self._pending_update_info = info
        message = tr("update.available").format(current=current, latest=info.latest_version)
        box = QMessageBox(self)
        box.setWindowTitle(tr("main.menu_help_check_updates"))
        box.setText(message)
        box.setIcon(QMessageBox.Icon.Information)

        install_btn = box.addButton(tr("update.install_now"), QMessageBox.ButtonRole.AcceptRole)
        browser_btn = box.addButton(tr("update.open_browser"), QMessageBox.ButtonRole.ActionRole)
        box.addButton(tr("common.cancel"), QMessageBox.ButtonRole.RejectRole)

        box.exec()
        clicked = box.clickedButton()
        if clicked is browser_btn and info.release_url:
            QDesktopServices.openUrl(QUrl(info.release_url))
        elif clicked is install_btn:
            self._start_update_download(info)

    def _start_update_download(self, info: UpdateInfo) -> None:
        if sys.platform != "win32":
            QMessageBox.warning(self, tr("common.error"), tr("update.windows_only"))
            return

        if not updater_available():
            QMessageBox.warning(self, tr("common.error"), tr("update.updater_missing"))
            if info.release_url:
                QDesktopServices.openUrl(QUrl(info.release_url))
            return

        confirm = QMessageBox.question(
            self,
            tr("common.confirm"),
            tr("update.confirm_quit"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        dest = default_download_path(info.latest_version)
        self._update_progress = QProgressDialog(tr("update.downloading"), tr("common.cancel"), 0, 100, self)
        self._update_progress.setWindowTitle(tr("main.menu_help_check_updates"))
        self._update_progress.setWindowModality(Qt.WindowModality.WindowModal)
        self._update_progress.setMinimumDuration(0)
        self._update_progress.canceled.connect(self._cancel_update_download)
        self._update_progress.show()

        self._update_download_worker = UpdateDownloadWorker(info, dest, self)
        self._update_download_worker.progress.connect(self._on_update_download_progress)
        self._update_download_worker.finished_ok.connect(self._on_update_download_ok)
        self._update_download_worker.finished_error.connect(self._on_update_download_error)
        self._update_download_worker.start()

    def _cancel_update_download(self) -> None:
        if self._update_download_worker is not None and self._update_download_worker.isRunning():
            self._update_download_worker.terminate()
            self._update_download_worker.wait(2000)

    def _on_update_download_progress(self, downloaded: int, total: object) -> None:
        if self._update_progress is None:
            return
        if total is None:
            self._update_progress.setRange(0, 0)
            return
        total_int = int(total)
        if total_int <= 0:
            return
        self._update_progress.setRange(0, total_int)
        self._update_progress.setValue(min(downloaded, total_int))

    def _on_update_download_error(self, message: str) -> None:
        if self._update_progress is not None:
            self._update_progress.close()
            self._update_progress = None
        QMessageBox.warning(
            self,
            tr("common.error"),
            tr("update.error").format(message=message),
        )

    def _on_update_download_ok(self, zip_path: str) -> None:
        if self._update_progress is not None:
            self._update_progress.close()
            self._update_progress = None

        app_instance = ql_app.get_app()
        if app_instance is None:
            QMessageBox.warning(self, tr("common.error"), tr("update.error").format(message="app"))
            return

        try:
            app_instance.prepare_quit_for_update()
            launch_update(Path(zip_path), pid=os.getpid())
        except Exception as exc:
            QMessageBox.warning(
                self,
                tr("common.error"),
                tr("update.error").format(message=str(exc)),
            )
            return

        QApplication.quit()



    def _open_help_models(self) -> None:

        show_help("models", self)



    def _open_help_directions_profiles(self) -> None:

        show_help("directions_profiles", self)



    def _open_help_formatters(self) -> None:

        show_help("formatters", self)



    def _open_help_features(self) -> None:

        show_help("features", self)



    def _open_help_history(self) -> None:

        show_help("history", self)



    def _open_help_learning(self) -> None:

        show_help("learning", self)



    def _open_help_dashboard(self) -> None:

        show_help("dashboard", self)



    def _open_help_glossary(self) -> None:

        show_help("glossary", self)



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

        self._input_field.set_input_text(source_text)

        self.raise_()

        self.activateWindow()

        self._input_field.setFocus()



    def _check_api_key(self) -> None:

        entry = get_model_by_index(self._model_combo.currentIndex())
        provider_id = entry.api_provider

        if not provider_needs_api_key(provider_id):
            if not self._worker or not self._worker.isRunning():
                self._set_status("main.status_ready", error=False)
            return

        api_key = settings.get_api_key(provider_id)
        if not api_key:
            hint_key = PROVIDER_HINT_KEYS.get(provider_id, "")
            self._set_status(
                "main.status_api_key_hint",
                error=True,
                provider=tr(f"settings.api_keys.provider_{provider_id}"),
                hint=tr(hint_key) if hint_key else "",
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

        self._render_status()



    def _render_status(self) -> None:

        key = self._status_key

        params = self._status_params

        error = self._status_is_error

        if (

            is_enabled("input.tutor_capture")

            and key == "main.status_ready"

            and not error

        ):

            message = tr("main.status_tutor_capture_active")

        elif key == "main.status_error":

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

        self._input_field.set_input_text(self._pending_source)

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


