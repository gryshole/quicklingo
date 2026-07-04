from PySide6.QtWidgets import QFormLayout

from quicklingo.ui.settings.feature_settings_editor import FeatureSettingsEditor, GroupSpecs


def _general_extras(form: QFormLayout, editor: FeatureSettingsEditor) -> None:
    editor._add_combo_field(form, "ui.system_tray", "hotkey", "settings.features.tray_hotkey")


def _input_extras(form: QFormLayout, editor: FeatureSettingsEditor) -> None:
    editor._add_combo_field(
        form,
        "input.global_hotkey.translate_selection",
        "combo",
        "settings.features.hotkey_combo",
    )
    editor._add_combo_field(
        form,
        "input.global_hotkey.translate_clipboard",
        "combo",
        "settings.features.hotkey_combo",
    )
    editor._add_combo_field(
        form,
        "input.tutor_capture",
        "hotkey",
        "settings.features.tutor_capture_hotkey",
    )


def _translation_extras(form: QFormLayout, editor: FeatureSettingsEditor) -> None:
    editor._add_spin(
        form,
        "translation.response_cache",
        "ttl_days",
        "settings.features.cache_ttl_days",
        1,
        365,
    )


def _history_extras(form: QFormLayout, editor: FeatureSettingsEditor) -> None:
    editor._add_spin(
        form,
        "history.meeting_transcript",
        "session_gap_min",
        "settings.features.session_gap_min",
        1,
        240,
    )


_FEATURE_GROUP_SPECS: GroupSpecs = {
    "general": (
        "settings.features.group_general",
        [
            "ui.always_on_top",
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
            "input.tutor_capture",
            "ui.single_line_input",
        ],
    ),
    "translation": (
        "settings.features.group_translation",
        [
            "translation.response_cache",
        ],
    ),
    "history": (
        "settings.features.group_history",
        [
            "history.auto_save",
            "history.tags",
        ],
    ),
    "privacy": (
        "settings.features.group_privacy",
        ["privacy.encrypted_keys"],
    ),
}


class FeaturesTab(FeatureSettingsEditor):
    def __init__(self, parent=None) -> None:
        super().__init__(
            _FEATURE_GROUP_SPECS,
            group_hooks={
                "general": lambda form: _general_extras(form, self),
                "input": lambda form: _input_extras(form, self),
                "translation": lambda form: _translation_extras(form, self),
                "history": lambda form: _history_extras(form, self),
            },
            parent=parent,
        )
