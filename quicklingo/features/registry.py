from __future__ import annotations

import copy
from typing import Any

from PySide6.QtCore import QObject, Signal

from quicklingo import settings

FEATURE_DEFAULTS: dict[str, dict[str, Any]] = {
    "ui.always_on_top": {"enabled": True},
    "ui.auto_copy_result": {"enabled": False},
    "ui.single_line_input": {"enabled": True},
    "ui.system_tray": {"enabled": False, "hotkey": "<ctrl>+<shift>+q"},
    "ui.autostart": {"enabled": False},
    "history.auto_save": {"enabled": True},
    "history.tags": {"enabled": True},
    "history.meeting_transcript": {"enabled": True, "session_gap_min": 15},
    "learning.ai_corpus_analysis": {
        "max_candidates": 120,
        "batch_size": 40,
        "card_prompt_template": "",
        "card_prompt_template_ua_en": "",
        "card_prompt_template_en_ua": "",
    },
    "learning.anki_export": {"enabled": True},
    "learning.srs_review": {
        "enabled": True,
        "desired_retention": 90,
        "new_cards_per_day": 10,
        "daily_limit": 20,
    },
    "learning.card_images": {"enabled": False, "max_images_per_batch": 25},
    "learning.quiz": {
        "question_count": 15,
        "feedback_delay_ms": 1800,
        "choices_pool_size": 6,
        "choices_display_count": 4,
        "generation_max_retries": 3,
        "type_picker_lookback": 10,
        "quiz_system_prompt_template": "",
        "quiz_prompt_fill_blank": "",
        "quiz_prompt_definition_match": "",
        "quiz_prompt_translation_recall": "",
        "last_deck_selection_mode": "all",
        "last_deck_ids": [],
        "last_generation_deck_id": "",
    },
    "learning.tts_enabled": {},
    "learning.tts_auto_play": {"enabled": False},
    "learning.ai_deck_generator": {"batch_size": 10, "max_words": 30},
    "translation.response_cache": {"enabled": True, "ttl_days": 30},
    "translation.context_window": {"enabled": False, "last_n": 3},
    "input.global_hotkey.translate_selection": {
        "enabled": False,
        "combo": "<ctrl>+<shift>+t",
    },
    "input.global_hotkey.translate_clipboard": {
        "enabled": False,
        "combo": "<ctrl>+<shift>+v",
    },
    "input.double_ctrl_c": {"enabled": False},
    "input.tutor_capture": {
        "enabled": False,
        "hotkey": "<ctrl>+<alt>+g",
    },
    "input.replace_in_place": {"enabled": False},
    "privacy.encrypted_keys": {"enabled": False},
}


class _FeatureNotifier(QObject):
    changed = Signal(list)


_notifier = _FeatureNotifier()


def feature_changed() -> _FeatureNotifier:
    return _notifier


def default_features() -> dict[str, dict[str, Any]]:
    return copy.deepcopy(FEATURE_DEFAULTS)


def _merged_features() -> dict[str, dict[str, Any]]:
    merged = default_features()
    stored = settings.get_features_raw()
    for key, value in stored.items():
        if key not in merged or not isinstance(value, dict):
            continue
        entry = dict(merged[key])
        entry.update(value)
        if "enabled" in entry:
            entry["enabled"] = bool(entry["enabled"])
        merged[key] = entry
    return merged


def get_all_features() -> dict[str, dict[str, Any]]:
    return _merged_features()


def get_feature(key: str) -> dict[str, Any]:
    return dict(_merged_features().get(key, {}))


def is_enabled(key: str) -> bool:
    # Always-on capabilities; only limits/prompts (where applicable) stay configurable.
    if key in {
        "history.auto_save",
        "history.tags",
        "learning.ai_corpus_analysis",
        "learning.quiz",
        "learning.ai_deck_generator",
        "learning.tts_enabled",
    }:
        return True
    feature = get_feature(key)
    if not feature:
        return False
    return bool(feature.get("enabled", False))


def save_features(features: dict[str, dict[str, Any]]) -> None:
    merged = _merged_features()
    for key, patch in features.items():
        if key not in FEATURE_DEFAULTS or not isinstance(patch, dict):
            continue
        entry = dict(merged.get(key, {}))
        entry.update(patch)
        if "enabled" in entry:
            entry["enabled"] = bool(entry["enabled"])
        merged[key] = entry
    settings.save_features_raw(
        {key: merged[key] for key in FEATURE_DEFAULTS if key in merged}
    )
    _apply_side_effects(merged)
    _notifier.changed.emit(list(features.keys()))


def _apply_side_effects(features: dict[str, dict[str, Any]]) -> None:
    from quicklingo.platform import autostart

    if autostart.autostart_supported():
        autostart.set_enabled(bool(features.get("ui.autostart", {}).get("enabled", False)))


def feature_keys() -> list[str]:
    return list(FEATURE_DEFAULTS.keys())
