from __future__ import annotations

import copy
from typing import Any

from PySide6.QtCore import QObject, Signal

from quicklingo import settings

FEATURE_DEFAULTS: dict[str, dict[str, Any]] = {
    "ui.always_on_top": {"enabled": True},
    "ui.remember_geometry": {"enabled": True},
    "ui.remember_zoom": {"enabled": True},
    "ui.auto_copy_result": {"enabled": False},
    "ui.single_line_input": {"enabled": True},
    "ui.system_tray": {"enabled": False, "hotkey": "<ctrl>+<shift>+q"},
    "ui.autostart": {"enabled": False},
    "history.auto_save": {"enabled": True},
    "history.search": {"enabled": True},
    "history.filters": {"enabled": True},
    "history.export": {"enabled": True},
    "history.dashboard": {"enabled": True},
    "history.model_stats": {"enabled": True},
    "history.tags": {"enabled": True},
    "history.meeting_transcript": {"enabled": True, "session_gap_min": 15},
    "learning.phrasebook": {"enabled": True},
    "learning.word_frequency": {"enabled": True, "top_n": 50},
    "learning.difficult_words": {"enabled": True},
    "learning.ai_corpus_analysis": {
        "enabled": True,
        "max_candidates": 120,
        "batch_size": 40,
    },
    "learning.anki_preview": {"enabled": True},
    "learning.anki_export": {"enabled": True},
    "learning.deck_scope": {"enabled": True},
    "learning.daily_review": {"enabled": True, "daily_limit": 20},
    "learning.srs_review": {"enabled": False},
    "learning.streak": {"enabled": True},
    "learning.extract_vocab": {"enabled": False},
    "translation.response_cache": {"enabled": True, "ttl_days": 30},
    "translation.context_window": {"enabled": False, "last_n": 3},
    "translation.glossary": {"enabled": False},
    "translation.streaming": {"enabled": True},
    "translation.request_queue": {"enabled": True},
    "input.global_hotkey.translate_selection": {
        "enabled": False,
        "combo": "<ctrl>+<shift>+t",
    },
    "input.global_hotkey.translate_clipboard": {
        "enabled": False,
        "combo": "<ctrl>+<shift>+v",
    },
    "input.double_ctrl_c": {"enabled": False},
    "input.replace_in_place": {"enabled": False},
    "privacy.encrypted_keys": {"enabled": False},
}


class _FeatureNotifier(QObject):
    changed = Signal()


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
    _notifier.changed.emit()


def _apply_side_effects(features: dict[str, dict[str, Any]]) -> None:
    from quicklingo.platform import autostart

    if autostart.autostart_supported():
        autostart.set_enabled(bool(features.get("ui.autostart", {}).get("enabled", False)))


def feature_keys() -> list[str]:
    return list(FEATURE_DEFAULTS.keys())
