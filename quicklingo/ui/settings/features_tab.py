from __future__ import annotations

from PySide6.QtWidgets import QFormLayout

from quicklingo.ui.settings.feature_settings_editor import FeatureSettingsEditor, GroupSpecs


def _general_extras(form: QFormLayout, editor: FeatureSettingsEditor) -> None:
    editor._add_hotkey_row(
        form,
        feature_key="ui.system_tray",
        field="hotkey",
        title_key="settings.features.tray_hotkey",
        uses_enabled_flag=False,
    )


def _input_extras(form: QFormLayout, editor: FeatureSettingsEditor) -> None:
    editor._add_hotkey_row(
        form,
        feature_key="input.global_hotkey.translate_selection",
        field="combo",
        title_key="settings.features.hotkey_translate_selection",
        uses_enabled_flag=True,
    )
    editor._add_hotkey_row(
        form,
        feature_key="input.global_hotkey.translate_clipboard",
        field="combo",
        title_key="settings.features.hotkey_translate_clipboard",
        uses_enabled_flag=True,
    )
    editor._add_hotkey_row(
        form,
        feature_key="input.tutor_capture",
        field="hotkey",
        title_key="settings.features.input_tutor_capture",
        uses_enabled_flag=False,
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
            "ui.single_line_input",
        ],
    ),
    "translation": (
        "settings.features.group_translation",
        [
            "translation.response_cache",
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
            },
            parent=parent,
        )
