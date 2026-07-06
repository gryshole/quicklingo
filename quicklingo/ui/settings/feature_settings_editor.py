from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from quicklingo.features import feature_keys, get_all_features, is_enabled, save_features
from quicklingo.i18n import tr
from quicklingo.ui.settings.base_tab import SettingsTab
from quicklingo.ui.settings.feature_help import attach_feature_help
from quicklingo.ui.settings_theme import configure_prompt_reset_button, configure_settings_group_box

FEATURE_I18N: dict[str, tuple[str, str | None]] = {
    "ui.always_on_top": ("settings.features.ui_always_on_top", None),
    "ui.auto_copy_result": ("settings.features.ui_auto_copy_result", None),
    "ui.single_line_input": ("settings.features.ui_single_line_input", None),
    "ui.system_tray": ("settings.features.ui_system_tray", "settings.features.ui_system_tray_note"),
    "ui.autostart": ("settings.features.ui_autostart", "settings.features.ui_autostart_note"),
    "history.auto_save": ("settings.features.history_auto_save", None),
    "history.tags": ("settings.features.history_tags", None),
    "history.meeting_transcript": (
        "settings.features.history_meeting_transcript",
        None,
    ),
    "learning.ai_corpus_analysis": (
        "settings.features.learning_ai_corpus_analysis",
        "settings.features.learning_ai_corpus_analysis_note",
    ),
    "learning.anki_export": ("settings.features.learning_anki_export", None),
    "learning.srs_review": ("settings.features.learning_srs_review", None),
    "learning.card_images": ("settings.features.learning_card_images", None),
    "learning.quiz": ("settings.features.learning_quiz", None),
    "learning.tts_enabled": ("settings.features.learning_tts_enabled", None),
    "learning.tts_auto_play": ("settings.features.learning_tts_auto_play", None),
    "learning.ai_deck_generator": (
        "settings.features.learning_ai_deck_generator",
        "settings.features.learning_ai_deck_generator_note",
    ),
    "translation.response_cache": (
        "settings.features.translation_response_cache",
        "settings.features.translation_response_cache_note",
    ),
    "translation.context_window": ("settings.features.translation_context_window", None),
    "input.global_hotkey.translate_selection": (
        "settings.features.hotkey_translate_selection",
        "settings.features.hotkey_note",
    ),
    "input.global_hotkey.translate_clipboard": (
        "settings.features.hotkey_translate_clipboard",
        "settings.features.hotkey_note",
    ),
    "input.double_ctrl_c": ("settings.features.input_double_ctrl_c", None),
    "input.tutor_capture": (
        "settings.features.input_tutor_capture",
        "settings.features.input_tutor_capture_note",
    ),
    "input.replace_in_place": (
        "settings.features.input_replace_in_place",
        "settings.features.input_replace_in_place_note",
    ),
    "privacy.encrypted_keys": (
        "settings.features.privacy_encrypted_keys",
        "settings.features.privacy_encrypted_keys_note",
    ),
}

GroupHook = Callable[[QFormLayout], None]
GroupSpecs = dict[str, tuple[str, list[str]]]


class FeatureSettingsEditor(SettingsTab):
    def __init__(
        self,
        group_specs: GroupSpecs,
        *,
        group_hooks: dict[str, GroupHook] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._group_specs = group_specs
        self._group_hooks = group_hooks or {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        body.setObjectName("settingsTabBody")
        self._body_layout = QVBoxLayout(body)
        self._body_layout.setSpacing(0)
        self._body_layout.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(body)
        outer.addWidget(scroll)

        self._groups: dict[str, QGroupBox] = {}
        self._checkboxes: dict[str, QCheckBox] = {}
        self._spinboxes: dict[tuple[str, str], QSpinBox] = {}
        self._line_edits: dict[tuple[str, str], QLineEdit] = {}
        self._text_edits: dict[tuple[str, str], QPlainTextEdit] = {}
        self._build_groups()
        self._body_layout.addSpacing(30)
        self.reload()

    def _add_checkbox(self, form: QFormLayout, key: str) -> None:
        if key not in feature_keys():
            return
        title_key_i18n, note_key = FEATURE_I18N.get(key, (key, None))
        checkbox = QCheckBox(tr(title_key_i18n))
        if note_key:
            checkbox.setToolTip(tr(note_key))
        checkbox.toggled.connect(self.mark_dirty)
        attach_feature_help(checkbox, key, title_key_i18n)
        self._checkboxes[key] = checkbox
        form.addRow(checkbox)

    def _add_spin(
        self, form: QFormLayout, key: str, field: str, label_key: str, min_v: int, max_v: int
    ) -> None:
        spin = QSpinBox()
        spin.setRange(min_v, max_v)
        spin.setMaximumWidth(80)
        spin.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        spin.valueChanged.connect(self.mark_dirty)
        self._spinboxes[(key, field)] = spin
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(QLabel(tr(label_key)))
        row.addWidget(spin)
        row.addStretch()
        wrap = QWidget()
        wrap.setLayout(row)
        form.addRow(wrap)

    def _add_spin_form(
        self, form: QFormLayout, key: str, field: str, label_key: str, min_v: int, max_v: int
    ) -> None:
        spin = QSpinBox()
        spin.setRange(min_v, max_v)
        spin.setMaximumWidth(80)
        spin.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        spin.valueChanged.connect(self.mark_dirty)
        self._spinboxes[(key, field)] = spin
        label = QLabel(tr(label_key))
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.addRow(label, spin)

    def _add_combo_field(self, form: QFormLayout, key: str, field: str, label_key: str) -> None:
        edit = QLineEdit()
        edit.textChanged.connect(self.mark_dirty)
        self._line_edits[(key, field)] = edit
        form.addRow(tr(label_key), edit)

    def _add_text_area(
        self,
        form: QFormLayout,
        key: str,
        field: str,
        label_key: str,
        *,
        reset_factory: Callable[[], str] | None = None,
    ) -> None:
        from quicklingo.learning.card_prompt import get_builtin_card_prompt_template

        factory = reset_factory or (lambda: get_builtin_card_prompt_template("ua-en"))
        column = QVBoxLayout()
        edit = QPlainTextEdit()
        edit.setMinimumHeight(120)
        edit.setPlaceholderText(tr("settings.features.corpus_card_prompt_placeholder"))
        edit.textChanged.connect(self.mark_dirty)
        reset_btn = QPushButton(tr("settings.features.corpus_card_prompt_reset"))
        reset_btn.clicked.connect(lambda: edit.setPlainText(factory()))
        btn_row = QHBoxLayout()
        btn_row.addWidget(reset_btn)
        btn_row.addStretch()
        column.addWidget(edit)
        column.addLayout(btn_row)
        wrap = QWidget()
        wrap.setLayout(column)
        self._text_edits[(key, field)] = edit
        form.addRow(tr(label_key), wrap)

    def _add_prompt_field(
        self,
        form: QFormLayout,
        key: str,
        field: str,
        label_key: str,
        *,
        reset_factory: Callable[[], str],
        placeholder_key: str = "settings.features.corpus_card_prompt_placeholder",
    ) -> None:
        label = QLabel(tr(label_key))
        label.setObjectName("promptFieldLabel")
        edit = QPlainTextEdit()
        edit.setObjectName("promptFieldEdit")
        edit.setMinimumHeight(80)
        edit.setMaximumHeight(90)
        edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        edit.setPlaceholderText(tr(placeholder_key))
        edit.textChanged.connect(self.mark_dirty)
        reset_btn = QPushButton(tr("settings.features.corpus_card_prompt_reset"))
        configure_prompt_reset_button(reset_btn)
        reset_btn.clicked.connect(lambda: edit.setPlainText(reset_factory()))
        field_column = QVBoxLayout()
        field_column.setContentsMargins(0, 0, 0, 0)
        field_column.setSpacing(6)
        field_column.addWidget(edit)
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.addStretch()
        btn_row.addWidget(reset_btn)
        field_column.addLayout(btn_row)
        field_wrap = QWidget()
        field_wrap.setLayout(field_column)
        field_wrap.setMinimumHeight(114)
        field_wrap.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        block = QVBoxLayout()
        block.setContentsMargins(0, 0, 0, 0)
        block.setSpacing(4)
        block.addWidget(label)
        block.addWidget(field_wrap)
        wrap = QWidget()
        wrap.setLayout(block)
        wrap.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        wrap.setMinimumHeight(148)
        self._text_edits[(key, field)] = edit
        form.addRow(wrap)

    def _build_groups(self) -> None:
        for index, (group_id, (_title_key, keys)) in enumerate(self._group_specs.items()):
            group = QGroupBox()
            form = QFormLayout(group)
            form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
            form.setLabelAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            self._groups[group_id] = group
            for key in keys:
                self._add_checkbox(form, key)
            hook = self._group_hooks.get(group_id)
            if hook is not None:
                hook(form)
            configure_settings_group_box(group)
            if index > 0:
                self._body_layout.addSpacing(15)
            self._body_layout.addWidget(group)

    def retranslate_ui(self) -> None:
        for group_id, group in self._groups.items():
            title_key, _keys = self._group_specs[group_id]
            group.setTitle(tr(title_key))
        for key, checkbox in self._checkboxes.items():
            title_key, note_key = FEATURE_I18N.get(key, (key, None))
            checkbox.setText(tr(title_key))
            if note_key:
                checkbox.setToolTip(tr(note_key))

    def reload(self) -> None:
        features = get_all_features()
        for key, checkbox in self._checkboxes.items():
            checkbox.blockSignals(True)
            checkbox.setChecked(is_enabled(key))
            checkbox.blockSignals(False)
        for (key, field), spin in self._spinboxes.items():
            value = features.get(key, {}).get(field, spin.value())
            spin.blockSignals(True)
            spin.setValue(int(value))
            spin.blockSignals(False)
        for (key, field), edit in self._line_edits.items():
            value = str(features.get(key, {}).get(field, edit.text()))
            edit.blockSignals(True)
            edit.setText(value)
            edit.blockSignals(False)
        for (key, field), edit in self._text_edits.items():
            value = str(features.get(key, {}).get(field, edit.toPlainText()))
            edit.blockSignals(True)
            edit.setPlainText(value)
            edit.blockSignals(False)
        self.retranslate_ui()
        self.mark_clean()

    def save(self) -> bool:
        patch: dict[str, dict] = {}
        for key, checkbox in self._checkboxes.items():
            patch.setdefault(key, {})["enabled"] = checkbox.isChecked()
        for (key, field), spin in self._spinboxes.items():
            patch.setdefault(key, {})[field] = spin.value()
        for (key, field), edit in self._line_edits.items():
            patch.setdefault(key, {})[field] = edit.text().strip()
        for (key, field), edit in self._text_edits.items():
            patch.setdefault(key, {})[field] = edit.toPlainText().strip()
        save_features(patch)
        self.mark_clean()
        return True
