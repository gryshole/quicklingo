from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from quicklingo.features import feature_keys, get_all_features, is_enabled, save_features
from quicklingo.i18n import tr
from quicklingo.ui.settings.base_tab import SettingsTab
from quicklingo.ui.settings.feature_help import attach_feature_help

_FEATURE_I18N: dict[str, tuple[str, str | None]] = {
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
    "learning.word_frequency": ("settings.features.learning_word_frequency", None),
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
    "learning.streak": ("settings.features.learning_streak", None),
    "learning.extract_vocab": ("settings.features.learning_extract_vocab", None),
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
    "input.replace_in_place": (
        "settings.features.input_replace_in_place",
        "settings.features.input_replace_in_place_note",
    ),
    "privacy.encrypted_keys": (
        "settings.features.privacy_encrypted_keys",
        "settings.features.privacy_encrypted_keys_note",
    ),
}


class FeaturesTab(SettingsTab):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
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
        self._build_groups()
        self._body_layout.addStretch()
        self.reload()

    def _add_checkbox(self, form: QFormLayout, key: str) -> None:
        if key not in feature_keys():
            return
        title_key_i18n, note_key = _FEATURE_I18N.get(key, (key, None))
        checkbox = QCheckBox(tr(title_key_i18n))
        if note_key:
            checkbox.setToolTip(tr(note_key))
        checkbox.toggled.connect(self.mark_dirty)
        attach_feature_help(checkbox, key, title_key_i18n)
        self._checkboxes[key] = checkbox
        form.addRow(checkbox)

    def _add_spin(self, form: QFormLayout, key: str, field: str, label_key: str, min_v: int, max_v: int) -> None:
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

    def _build_groups(self) -> None:
        group_specs = {
            "general": (
                "settings.features.group_general",
                [
                    "ui.always_on_top",
                    "ui.remember_geometry",
                    "ui.remember_zoom",
                    "ui.auto_copy_result",
                    "ui.system_tray",
                    "ui.autostart",
                ],
            ),
            "input": (
                "settings.features.group_input",
                [
                    "input.global_hotkey.translate_selection",
                    "input.global_hotkey.translate_clipboard",
                    "input.double_ctrl_c",
                    "input.replace_in_place",
                    "ui.single_line_input",
                ],
            ),
            "translation": (
                "settings.features.group_translation",
                [
                    "translation.response_cache",
                    "translation.context_window",
                    "translation.glossary",
                    "translation.streaming",
                    "translation.request_queue",
                ],
            ),
            "history": (
                "settings.features.group_history",
                [
                    "history.auto_save",
                    "history.search",
                    "history.filters",
                    "history.export",
                    "history.dashboard",
                    "history.model_stats",
                    "history.tags",
                    "history.meeting_transcript",
                    "learning.phrasebook",
                    "learning.word_frequency",
                    "learning.difficult_words",
                    "learning.ai_corpus_analysis",
                    "learning.anki_preview",
                    "learning.anki_export",
                    "learning.deck_scope",
                    "learning.daily_review",
                    "learning.srs_review",
                    "learning.streak",
                    "learning.extract_vocab",
                ],
            ),
            "privacy": (
                "settings.features.group_privacy",
                ["privacy.encrypted_keys"],
            ),
        }
        for group_id, (title_key, keys) in group_specs.items():
            group = QGroupBox()
            form = QFormLayout(group)
            self._groups[group_id] = group
            for key in keys:
                self._add_checkbox(form, key)
            if group_id == "general":
                self._add_combo_field(
                    form, "ui.system_tray", "hotkey", "settings.features.tray_hotkey"
                )
            if group_id == "input":
                self._add_combo_field(
                    form,
                    "input.global_hotkey.translate_selection",
                    "combo",
                    "settings.features.hotkey_combo",
                )
                self._add_combo_field(
                    form,
                    "input.global_hotkey.translate_clipboard",
                    "combo",
                    "settings.features.hotkey_combo",
                )
            if group_id == "translation":
                self._add_spin(
                    form,
                    "translation.response_cache",
                    "ttl_days",
                    "settings.features.cache_ttl_days",
                    1,
                    365,
                )
                self._add_spin(
                    form,
                    "translation.context_window",
                    "last_n",
                    "settings.features.context_last_n",
                    1,
                    20,
                )
            if group_id == "history":
                self._add_spin(
                    form,
                    "history.meeting_transcript",
                    "session_gap_min",
                    "settings.features.session_gap_min",
                    1,
                    240,
                )
                self._add_spin(
                    form,
                    "learning.word_frequency",
                    "top_n",
                    "settings.features.word_freq_top_n",
                    5,
                    500,
                )
                self._add_spin(
                    form,
                    "learning.ai_corpus_analysis",
                    "max_candidates",
                    "settings.features.corpus_max_candidates",
                    20,
                    300,
                )
                self._add_spin(
                    form,
                    "learning.ai_corpus_analysis",
                    "batch_size",
                    "settings.features.corpus_batch_size",
                    10,
                    80,
                )
                self._add_spin(
                    form,
                    "learning.daily_review",
                    "daily_limit",
                    "settings.features.daily_review_limit",
                    5,
                    100,
                )
            self._body_layout.addWidget(group)

    def retranslate_ui(self) -> None:
        group_titles = {
            "general": tr("settings.features.group_general"),
            "input": tr("settings.features.group_input"),
            "translation": tr("settings.features.group_translation"),
            "history": tr("settings.features.group_history"),
            "privacy": tr("settings.features.group_privacy"),
        }
        for group_id, group in self._groups.items():
            group.setTitle(group_titles[group_id])
        for key, checkbox in self._checkboxes.items():
            title_key, note_key = _FEATURE_I18N.get(key, (key, None))
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
        save_features(patch)
        self.mark_clean()
        return True
