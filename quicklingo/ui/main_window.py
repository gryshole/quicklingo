from PySide6.QtCore import Qt, QByteArray, Signal

from PySide6.QtGui import QCloseEvent, QGuiApplication, QHideEvent, QShowEvent

from PySide6.QtWidgets import (

    QApplication,

    QComboBox,

    QFrame,

    QGridLayout,

    QHBoxLayout,

    QLabel,

    QMainWindow,

    QMessageBox,

    QPushButton,

    QSizePolicy,

    QVBoxLayout,

    QWidget,

)



import sys

from quicklingo.config.loader import (

    get_directions,

    get_formatter,

    get_profiles_for_direction,

    reload_config,

    resolve_active_profile_id,

    resolve_learning_direction,

)


from quicklingo import settings
from quicklingo.db import history
from quicklingo.features import feature_changed, is_enabled, save_features

from quicklingo.i18n import tr, translate_message

from quicklingo.input.hotkeys import copy_selection_to_clipboard
from quicklingo.input.tutor_capture_log import log_debug

from quicklingo.providers.registry import get_model_by_index, get_model_entries
from quicklingo.providers.setup_info import PROVIDER_HINT_KEYS, provider_needs_api_key

from quicklingo.ui.controllers.translation_controller import TranslationController
from quicklingo.ui.controllers.tutor_input import append_character, backspace as tutor_backspace
from quicklingo.ui.controllers.update_controller import UpdateController
from quicklingo.ui.app_theme import (
    GLOBAL_BTN_OFF,
    GLOBAL_BTN_ON,
    GLOBAL_BTN_UNSUPPORTED,
    main_window_stylesheet,
    OUTPUT_PLACEHOLDER_STYLE,
    STATUS_ERROR_STYLE,
    STATUS_MUTED_STYLE,
    apply_compact_form_label_style,
    apply_combo_font,
    apply_section_title_style,
    compact_form_row,
    sync_compact_form_label_width,
    make_compact_section_card,
    make_section_card,
)
from quicklingo.ui.qt_utils import (
    configure_single_line_combo,
    open_help,
    raise_window,
    reload_combo,
)
from quicklingo.ui.widgets.segmented_control import SegmentedControl
from quicklingo.ui.dialogs.learning_onboarding_dialog import LearningOnboardingDialog
from quicklingo.ui.history_window import HistoryWindow
from quicklingo.ui.learning_window import LearningWindow
from quicklingo.ui.quiz_questions_window import QuizQuestionsWindow

from quicklingo.ui.settings_dialog import SettingsDialog

from quicklingo.ui.zoomable_text_edit import ZoomableInputEdit, ZoomableLineEdit, ZoomableTextEdit

from quicklingo.version import __version__


class MainWindow(QMainWindow):

    visibility_changed = Signal(bool)

    def __init__(self) -> None:

        super().__init__()

        self._translation = TranslationController(self)
        self._updates = UpdateController(self)

        self._force_quit = False
        self._tray_manager = None
        self._history_window: HistoryWindow | None = None
        self._learning_window: LearningWindow | None = None
        self._quiz_questions_window: QuizQuestionsWindow | None = None
        self._direction_control: SegmentedControl | None = None

        self._main_layout: QVBoxLayout | None = None

        self._input_layout: QVBoxLayout | None = None

        self._tag_row: QHBoxLayout | None = None

        self._status_key = "main.status_ready"

        self._status_params: dict = {}

        self._status_is_error = False



        self.setWindowTitle("QuickLingo")



        self._tools_menu = None

        self._history_action = None

        self._learning_action = None

        self._quiz_questions_action = None

        self._settings_action = None

        self._help_menu = None

        self._help_about_action = None

        self._help_check_updates_action = None

        self._help_models_action = None

        self._help_directions_profiles_action = None

        self._help_features_action = None

        self._help_history_action = None

        self._help_learning_action = None
        self._help_onboarding_action = None

        self._create_menu_bar()



        central = QWidget()
        central.setObjectName("appRoot")
        self.setCentralWidget(central)
        self.setStyleSheet(main_window_stylesheet())

        layout = QVBoxLayout(central)
        self._main_layout = layout
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(14)

        self._settings_section_label = QLabel()
        apply_section_title_style(self._settings_section_label)

        self._model_label = QLabel()
        apply_compact_form_label_style(self._model_label)
        self._model_combo = QComboBox()
        self._model_combo.currentIndexChanged.connect(lambda _: self._check_api_key())
        configure_single_line_combo(self._model_combo)
        self._reload_model_combo()

        self._direction_label = QLabel()
        apply_compact_form_label_style(self._direction_label)

        self._direction_control = SegmentedControl()
        self._build_direction_segments()

        self._profile_label = QLabel()
        apply_compact_form_label_style(self._profile_label)
        self._profile_combo = QComboBox()
        self._profile_combo.currentIndexChanged.connect(self._on_profile_changed)
        configure_single_line_combo(self._profile_combo)

        self._tag_label = QLabel()
        apply_compact_form_label_style(self._tag_label)
        self._tag_combo = QComboBox()
        self._tag_combo.setEditable(True)
        self._tag_combo.setMinimumWidth(48)
        apply_combo_font(self._tag_combo)
        self._reload_tag_combo()

        self._input_section_label = QLabel()
        apply_section_title_style(self._input_section_label)

        self._input_label = QLabel()
        self._input_label.setWordWrap(True)
        self._input_label.setMinimumWidth(0)

        self._tutor_capture_btn = QPushButton()
        self._tutor_capture_btn.setObjectName("globalInputBtn")
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
        apply_section_title_style(self._output_label)

        self._output_field = ZoomableTextEdit()
        self._output_field.setFrameShape(QFrame.Shape.NoFrame)
        self._output_field.set_text_selectable(True)
        self._output_field.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        self._output_host = QWidget()
        self._output_host.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        output_host_layout = QGridLayout(self._output_host)
        output_host_layout.setContentsMargins(0, 0, 0, 0)
        output_host_layout.addWidget(self._output_field, 0, 0)

        self._output_placeholder = QLabel()
        self._output_placeholder.setAlignment(
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
        )
        self._output_placeholder.setStyleSheet(OUTPUT_PLACEHOLDER_STYLE)
        self._output_placeholder.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents
        )
        output_host_layout.addWidget(
            self._output_placeholder, 0, 0, Qt.AlignmentFlag.AlignCenter
        )
        self._output_field.result_changed.connect(self._sync_output_placeholder)



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



        settings_card, settings_layout = make_compact_section_card("settingsCard")
        settings_card.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
        )
        settings_layout.addWidget(self._settings_section_label)
        settings_layout.addLayout(compact_form_row(self._model_label, self._model_combo))
        settings_layout.addLayout(
            compact_form_row(self._direction_label, self._direction_control)
        )
        settings_layout.addLayout(
            compact_form_row(self._profile_label, self._profile_combo)
        )
        self._tag_row = compact_form_row(self._tag_label, self._tag_combo)
        settings_layout.addLayout(self._tag_row)

        input_card, input_layout = make_section_card("inputCard", margins=(12, 10, 12, 10))
        self._input_layout = input_layout
        input_card.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
        )
        input_layout.addWidget(self._input_section_label)
        input_layout.addLayout(self._input_header)
        input_layout.addWidget(self._input_field)

        result_card, result_layout = make_section_card("resultCard", margins=(12, 10, 12, 10))
        result_card.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding
        )
        result_layout.addWidget(self._output_label)
        result_layout.addWidget(self._output_host, stretch=1)
        result_layout.addLayout(action_row)

        layout.addWidget(settings_card)
        layout.addWidget(input_card)
        layout.addWidget(result_card, stretch=1)
        layout.addWidget(self._status_label)



        self._input_label_ref = self._input_label

        self._refresh_input_label()

        self.sync_tutor_capture_ui()

        self._direction_control.selection_changed.connect(
            lambda _: self._refresh_profile_combo()
        )

        self.retranslate_ui()

        self._apply_window_features()

        self._restore_ui_preferences()

        self._refresh_profile_combo()

        self._check_api_key()

        self._apply_tag_visibility()

        self._restore_window_geometry()
        self.setMinimumWidth(260)



    def retranslate_ui(self) -> None:

        self.setWindowTitle(f"QuickLingo {__version__}")

        self._settings_section_label.setText(tr("main.section_settings").upper())
        self._input_section_label.setText(tr("main.section_input").upper())

        self._model_label.setText(tr("main.model_label"))

        self._direction_label.setText(tr("main.direction_label"))

        self._profile_label.setText(tr("main.profile_label"))

        self._tag_label.setText(tr("main.tag_label"))
        self._tag_combo.setPlaceholderText(tr("main.tag_placeholder"))
        sync_compact_form_label_width(
            [
                self._model_label,
                self._direction_label,
                self._profile_label,
                self._tag_label,
            ]
        )

        self._refresh_input_label()
        self._input_field.setPlaceholderText(tr("main.input_placeholder"))

        self._output_label.setText(tr("main.section_result").upper())

        self._output_placeholder.setText(tr("main.output_placeholder"))

        self._sync_output_placeholder()

        self._cancel_btn.setText(tr("main.cancel"))

        self._retry_btn.setText(tr("main.retry"))

        if self._tools_menu:

            self._tools_menu.setTitle(tr("main.menu_tools"))

        if self._history_action:

            self._history_action.setText(tr("main.menu_history"))

        if self._learning_action:

            self._learning_action.setText(tr("main.menu_learning"))

        if self._quiz_questions_action:

            self._quiz_questions_action.setText(tr("main.menu_quiz_questions"))
            self._quiz_questions_action.setVisible(is_enabled("learning.quiz"))

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

        if self._help_features_action:

            self._help_features_action.setText(tr("main.menu_help_features"))

        if self._help_history_action:

            self._help_history_action.setText(tr("main.menu_help_history"))

        if self._help_learning_action:

            self._help_learning_action.setText(tr("main.menu_help_learning"))

        if self._help_onboarding_action:

            self._help_onboarding_action.setText(tr("learning.onboarding.show_again"))

        self._tutor_capture_btn.setText(f"⚡ {tr('main.tutor_capture_btn')}")

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



    def _sync_output_placeholder(self) -> None:
        self._output_placeholder.setVisible(not self._output_field.has_result())



    def apply_features(self) -> None:

        self._apply_window_features()

        self._apply_tag_visibility()

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

        if sys.platform != "win32":
            self._tutor_capture_btn.setToolTip(tr("main.tutor_capture_btn_tooltip_unsupported"))
            self._tutor_capture_btn.setStyleSheet(GLOBAL_BTN_UNSUPPORTED)
        elif enabled:
            self._tutor_capture_btn.setStyleSheet(GLOBAL_BTN_ON)
            self._tutor_capture_btn.setToolTip(tr("main.tutor_capture_btn_tooltip_on"))
        else:
            self._tutor_capture_btn.setStyleSheet(GLOBAL_BTN_OFF)
            self._tutor_capture_btn.setToolTip(tr("main.tutor_capture_btn_tooltip_off"))



    def _on_tutor_capture_btn_toggled(self, checked: bool) -> None:

        if checked == is_enabled("input.tutor_capture"):

            return

        self._apply_tutor_capture_btn_style(checked)

        if self._status_key == "main.status_ready" and not self._status_is_error:

            if checked:

                self._status_label.setStyleSheet(STATUS_MUTED_STYLE)

                self._status_label.setText(tr("main.status_tutor_capture_active"))

            else:

                self._status_label.setStyleSheet(STATUS_MUTED_STYLE)

                self._status_label.setText(tr("main.status_ready"))

        save_features({"input.tutor_capture": {"enabled": checked}})



    def is_translation_busy(self) -> bool:
        return self._translation.is_busy()



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

        append_character(self._input_field, char)



    def on_tutor_backspace(self) -> None:
        reason = self._tutor_input_block_reason()
        if reason is not None:
            log_debug(f"UI reject backspace reason={reason}")
            return

        tutor_backspace(self._input_field)



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

        if self._input_layout is None:

            return

        current_mode = self._single_line_input_enabled()

        if self._input_single_line_mode == current_mode:

            return

        self._input_single_line_mode = current_mode

        text = self._input_field.input_text()

        zoom = self._input_field.zoom_steps()

        enabled = self._input_field.isEnabled()

        placeholder = self._input_field.placeholderText()

        self._input_layout.removeWidget(self._input_field)

        self._input_field.deleteLater()

        self._input_field = self._create_input_field()

        self._input_field.submit_requested.connect(self._submit_translation)

        self._input_field.set_zoom_steps(zoom)

        self._input_field.setEnabled(enabled)

        if placeholder:

            self._input_field.setPlaceholderText(placeholder)

        if text:

            self._input_field.set_input_text(text)

        self._input_layout.addWidget(self._input_field)



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

        self._translation.set_replace_after_translate(
            replace_in_place and is_enabled("input.replace_in_place")
        )

        raise_window(self)

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



    def _build_direction_segments(self) -> None:

        if self._direction_control is None:
            return

        self._direction_control.clear_segments()
        for index, direction in enumerate(get_directions()):
            self._direction_control.add_segment(
                direction.id, direction.label, checked=(index == 0)
            )

    def _rebuild_direction_segments(self) -> None:

        if self._direction_control is None:
            return

        selected = self._current_direction()
        self._direction_control.blockSignals(True)
        self._build_direction_segments()
        self._direction_control.set_current_id(selected)

        model_id, direction = settings.get_ui_preferences()
        if direction:
            self._direction_control.set_current_id(direction)
        self._direction_control.blockSignals(False)

        self._refresh_profile_combo()



    def closeEvent(self, event: QCloseEvent) -> None:

        if (

            not self._force_quit

            and is_enabled("ui.system_tray")

            and hasattr(self, "_tray_manager")

            and self._tray_manager is not None

        ):

            settings.save_last_tag(self._current_tag())

            event.ignore()

            self.hide()

            return

        model_entry = get_model_by_index(self._model_combo.currentIndex())

        settings.save_ui_preferences(model_entry.model_id, self._current_direction())
        settings.save_last_tag(self._current_tag())

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

        if direction and self._direction_control is not None:

            self._direction_control.set_current_id(direction)

        saved_tag = settings.get_last_tag()
        if saved_tag and is_enabled("history.tags"):
            self._set_tag_combo_text(saved_tag)



    def _set_tag_combo_text(self, tag: str) -> None:
        index = self._tag_combo.findText(tag)
        if index >= 0:
            self._tag_combo.setCurrentIndex(index)
        else:
            self._tag_combo.setEditText(tag)



    def _create_menu_bar(self) -> None:

        menu_bar = self.menuBar()

        menu_bar.setFixedHeight(22)

        menu_bar.setStyleSheet(

            "QMenuBar { padding: 0px; spacing: 0px; background: transparent; }"

            "QMenuBar::item { padding: 1px 8px; margin: 0px; }"

            "QMenuBar::item:selected { background: #e2e8f0; }"

        )

        self._tools_menu = menu_bar.addMenu("")

        self._settings_action = self._tools_menu.addAction("")

        self._settings_action.triggered.connect(self._open_settings)

        self._history_action = self._tools_menu.addAction("")

        self._history_action.triggered.connect(self._open_history)

        self._learning_action = self._tools_menu.addAction("")

        self._learning_action.triggered.connect(self._open_learning)

        self._quiz_questions_action = self._tools_menu.addAction("")
        self._quiz_questions_action.triggered.connect(self._open_quiz_questions)
        self._quiz_questions_action.setVisible(is_enabled("learning.quiz"))

        self._help_menu = menu_bar.addMenu("")

        self._help_about_action = self._help_menu.addAction("")

        self._help_about_action.triggered.connect(lambda: self._open_help_topic("about"))

        self._help_check_updates_action = self._help_menu.addAction("")

        self._help_check_updates_action.triggered.connect(self._check_for_updates)

        self._help_menu.addSeparator()

        self._help_models_action = self._help_menu.addAction("")

        self._help_models_action.triggered.connect(lambda: self._open_help_topic("models"))

        self._help_directions_profiles_action = self._help_menu.addAction("")

        self._help_directions_profiles_action.triggered.connect(
            lambda: self._open_help_topic("directions_profiles")
        )

        self._help_features_action = self._help_menu.addAction("")

        self._help_features_action.triggered.connect(
            lambda: self._open_help_topic("features")
        )

        self._help_history_action = self._help_menu.addAction("")

        self._help_history_action.triggered.connect(
            lambda: self._open_help_topic("history")
        )

        self._help_learning_action = self._help_menu.addAction("")

        self._help_learning_action.triggered.connect(
            lambda: self._open_help_topic("learning")
        )

        self._help_onboarding_action = self._help_menu.addAction("")
        self._help_onboarding_action.triggered.connect(self._show_learning_onboarding)



    def _open_help_topic(self, topic: str) -> None:
        open_help(topic, self)

    def _show_learning_onboarding(self) -> None:
        LearningOnboardingDialog.show_guide(self, standalone=False)

    def _check_for_updates(self) -> None:
        self._updates.check_for_updates()

    def _open_history(self) -> None:

        if self._history_window is None:

            self._history_window = HistoryWindow(self)

            self._history_window.finished.connect(self._on_history_closed)

            self._history_window.reopen_requested.connect(self._reopen_from_history)
            self._history_window.create_deck_from_tag_requested.connect(
                self._create_deck_from_history_tag
            )

        self._history_window.refresh()

        self._reload_tag_combo()

        raise_window(self._history_window)

    def _create_deck_from_history_tag(self, tag: str, direction: str) -> None:
        self._open_learning()
        if self._learning_window is None:
            return
        self._learning_window.navigate_to(
            "create_deck",
            tag=tag or None,
            direction=direction,
            untagged=not tag,
        )

    def _open_learning(self) -> None:
        if self._learning_window is None:
            self._learning_window = LearningWindow(self)
            self._learning_window.closed.connect(self._on_learning_closed)
        self._learning_window._reload_tags()
        self._learning_window._reload_decks()
        self._learning_window._reload_model_combo()
        raise_window(self._learning_window)

    def _on_learning_closed(self) -> None:
        self._learning_window = None

    def _open_quiz_questions(self) -> None:
        if self._quiz_questions_window is None:
            self._quiz_questions_window = QuizQuestionsWindow(self)
            self._quiz_questions_window.finished.connect(self._on_quiz_questions_closed)
        self._quiz_questions_window.refresh()
        raise_window(self._quiz_questions_window)

    def _on_quiz_questions_closed(self) -> None:
        self._quiz_questions_window = None

    def _add_vocab_to_deck(
        self, word: str, source: str, direction: str, tag: str, result: str
    ) -> None:
        if self._learning_window is None:
            self._learning_window = LearningWindow(self)
            self._learning_window.closed.connect(self._on_learning_closed)
        if resolve_learning_direction(direction) == "en-ua":
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
        raise_window(self._learning_window)



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
        reload_combo(
            self._model_combo,
            [(entry.model_id, entry.display_name) for entry in get_model_entries()],
            current_data=current,
        )
        if self._model_combo.count() and self._model_combo.currentIndex() < 0:
            self._model_combo.setCurrentIndex(0)
        if hasattr(self, "_status_label"):
            self._check_api_key()

    def _on_config_changed(self) -> None:

        reload_config()

        self._rebuild_direction_segments()

        self._reload_model_combo()

        if self._learning_window is not None:
            self._learning_window._reload_model_combo()



    def _on_history_closed(self) -> None:

        self._history_window = None

        self._reload_tag_combo()



    def _current_tag(self) -> str:

        if not is_enabled("history.tags"):

            return ""

        return self._tag_combo.currentText().strip()



    def _reload_tag_combo(self) -> None:

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

        elif current:

            self._tag_combo.setEditText(current)

        self._tag_combo.blockSignals(False)



    def _apply_tag_visibility(self) -> None:

        show = is_enabled("history.tags")

        self._tag_label.setVisible(show)

        self._tag_combo.setVisible(show)



    def _reopen_from_history(

        self, source_text: str, direction: str, profile_id: str

    ) -> None:

        if self._direction_control is not None:
            self._direction_control.set_current_id(direction)

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
            if not self._translation.is_busy():
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
        elif not self._translation.is_busy():
            self._set_status("main.status_ready", error=False)



    def _current_direction(self) -> str:

        if self._direction_control is not None:
            current = self._direction_control.current_id()
            if current:
                return current

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

        color = STATUS_ERROR_STYLE if error else STATUS_MUTED_STYLE

        self._status_label.setStyleSheet(color)

        self._status_label.setText(message)



    def _set_busy(self, busy: bool) -> None:

        self._input_field.setEnabled(not busy)

        self._model_combo.setEnabled(not busy)

        self._profile_combo.setEnabled(not busy)

        self._tag_combo.setEnabled(not busy)

        if self._direction_control is not None:
            self._direction_control.set_enabled_all(not busy)

        self._cancel_btn.setVisible(busy)

        self._retry_btn.setVisible(False)



    def _submit_translation(self) -> None:
        self._translation.submit()

    def _start_translation(self, text: str) -> None:
        self._translation.start(text)

    def _cancel_translation(self) -> None:
        self._translation.cancel()

    def _retry_translation(self) -> None:
        self._translation.retry()

    def _show_result(self, result: str, direction: str, profile_id: str) -> None:

        formatter = get_formatter(direction, profile_id)

        self._output_field.set_result_html(formatter(result))

