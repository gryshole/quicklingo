from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QObject, Signal

SUPPORTED_LANGUAGES = ("en", "uk")
DEFAULT_LANGUAGE = "en"


class _I18nCore(QObject):
    language_changed = Signal()


_core = _I18nCore()
_catalogs: dict[str, dict[str, str]] = {}
_current_language = DEFAULT_LANGUAGE


def _locales_dir() -> Path:
    return Path(__file__).resolve().parent / "locales"


def _load_catalog(language: str) -> dict[str, str]:
    path = _locales_dir() / f"{language}.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _ensure_catalogs() -> None:
    global _catalogs
    if _catalogs:
        return
    _catalogs["en"] = _load_catalog("en")
    _catalogs["uk"] = _load_catalog("uk")


def init_language() -> None:
    from quicklingo import settings

    _ensure_catalogs()
    set_language(settings.get_ui_language(), emit=False)


def get_language() -> str:
    return _current_language


def language_changed() -> Signal:
    return _core.language_changed


def set_language(language: str, *, emit: bool = True) -> None:
    global _current_language
    _ensure_catalogs()
    lang = language if language in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
    changed = lang != _current_language
    _current_language = lang
    if emit and changed:
        _core.language_changed.emit()


def tr(key: str, **params: object) -> str:
    _ensure_catalogs()
    text = _catalogs.get(_current_language, {}).get(key)
    if text is None:
        text = _catalogs.get("en", {}).get(key, key)
    if params:
        try:
            return text.format(**params)
        except (KeyError, IndexError, ValueError):
            return text
    return text


class TranslatableError(Exception):
    def __init__(self, key: str, **params: object) -> None:
        self.key = key
        self.params = params
        super().__init__(key)

    def __str__(self) -> str:
        return translate_message(self.key, **self.params)


def translate_message(message: str, **params: object) -> str:
    """Translate a message key or pass through plain text."""
    if "." in message and message.split(".", 1)[0] in {
        "common",
        "main",
        "history",
        "settings",
        "validation",
        "errors",
    }:
        return tr(message, **params)
    return message.format(**params) if params else message
