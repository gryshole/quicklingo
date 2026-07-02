from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from quicklingo.features import feature_keys, get_all_features, is_enabled, save_features
from quicklingo.i18n import tr
from quicklingo.ui.settings.base_tab import SettingsTab
from quicklingo.ui.settings.feature_help import attach_feature_help

FEATURE_I18N: dict[str, tuple[str, str | None]] = {
    "ui.always_on_top": ("settings.features.ui_always_on_top", None),
    "ui.remember_geometry": ("settings.features.ui_remember_geometry", None),
    "ui.remember_zoom": ("settings.features.ui_remember_zoom", None),
    "ui.auto_copy_result": ("settings.features.ui_auto_copy_result", None),
    "ui.single_line_input": ("settings.features.ui_single_line_input", None),
    "ui.system_tray": ("settings.features.ui_system_tray", "settings.features.ui_system_tray_note"),
    "ui.autostart": ("settings.features.ui_autostart", "settings.features.ui_autostart_note"),
    "history.auto_save": ("settings.features.history_auto_save", None),
    "history.search": ("settings.features.history_search", None),
    "history.filters": ("settings.features.history_filters", None),
    "history.export": ("settings.features.history_export", None),
    "history.dashboard": ("settings.features.history_dashboard", None),
    "history.model_stats": ("settings.features.history_model_stats", None),
    "history.tags": ("settings.features.history_tags", None),
    "history.meeting_transcript": (
        "settings.features.history_meeting_transcript",
        None,
    ),
    "learning.phrasebook": ("settings.features.learning_phrasebook", None),
    "learning.difficult_words": ("settings.features.learning_difficult_words", None),
    "learning.ai_corpus_analysis": (
        "settings.features.learning_ai_corpus_analysis",
        "settings.features.learning_ai_corpus_analysis_note",
    ),
    "learning.anki_preview": ("settings.features.learning_anki_preview", None),
    "learning.anki_export": ("settings.features.learning_anki_export", None),
    "learning.deck_scope": ("settings.features.learning_deck_scope", None),
    "learning.daily_review": ("settings.features.learning_daily_review", None),
    "learning.srs_review": ("settings.features.learning_srs_review", None),
    "learning.review_typing": ("settings.features.learning_review_typing", None),
    "learning.card_images": ("settings.features.learning_card_images", None),
    "learning.card_pronunciation": ("settings.features.learning_card_pronunciation", None),
    "learning.streak": ("settings.features.learning_streak", None),
    "learning.extract_vocab": ("settings.features.learning_extract_vocab", None),
    "learning.quiz": ("settings.features.learning_quiz", None),
    "learning.progress_dashboard": ("settings.features.learning_progress_dashboard", None),
    "learning.tts_enabled": ("settings.features.learning_tts_enabled", None),
    "learning.tts_auto_play": ("settings.features.learning_tts_auto_play", None),
    "translation.response_cache": (
        "settings.features.translation_response_cache",
        "settings.features.translation_response_cache_note",
    ),
    "translation.context_window": ("settings.features.translation_context_window", None),
    "translation.glossary": ("settings.features.translation_glossary", None),
    "translation.streaming": ("settings.features.translation_streaming", None),
    "translation.request_queue": ("settings.features.translation_request_queue", None),
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
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        self._body_layout = QVBoxLayout(body)
        scroll.setWidget(body)
        outer.addWidget(scroll)

        self._groups: dict[str, QGroupBox] = {}
        self._checkboxes: dict[str, QCheckBox] = {}
        self._spinboxes: dict[tuple[str, str], QSpinBox] = {}
        self._line_edits: dict[tuple[str, str], QLineEdit] = {}
        self._text_edits: dict[tuple[str, str], QPlainTextEdit] = {}
        self._build_groups()
        self._body_layout.addStretch()
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
        spin.valueChanged.connect(self.mark_dirty)
        self._spinboxes[(key, field)] = spin
        form.addRow(tr(label_key), spin)

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

    def _build_groups(self) -> None:
        for group_id, (_title_key, keys) in self._group_specs.items():
            group = QGroupBox()
            form = QFormLayout(group)
            self._groups[group_id] = group
            for key in keys:
                self._add_checkbox(form, key)
            hook = self._group_hooks.get(group_id)
            if hook is not None:
                hook(form)
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
