import base64
import json
from binascii import Error as BinasciiError

from quicklingo.paths import user_data_dir

_SETTINGS_FILE = "settings.json"


def _settings_path():
    return user_data_dir() / _SETTINGS_FILE


def _load() -> dict:
    path = _settings_path()
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save(data: dict) -> None:
    _settings_path().write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def get_zoom_steps() -> tuple[int, int]:
    data = _load()
    return (
        int(data.get("zoom_input_steps", 0)),
        int(data.get("zoom_output_steps", 0)),
    )


def save_zoom_steps(input_steps: int, output_steps: int) -> None:
    data = _load()
    data["zoom_input_steps"] = input_steps
    data["zoom_output_steps"] = output_steps
    _save(data)


def get_window_geometry_state() -> bytes | None:
    data = _load()
    encoded = data.get("window_geometry")
    if not isinstance(encoded, str) or not encoded:
        return None
    try:
        return base64.b64decode(encoded)
    except (BinasciiError, ValueError):
        return None


def save_window_geometry_state(state: bytes) -> None:
    data = _load()
    data["window_geometry"] = base64.b64encode(state).decode("ascii")
    for key in ("window_x", "window_y", "window_width", "window_height"):
        data.pop(key, None)
    _save(data)


def _default_active_profiles() -> dict[str, str]:
    from quicklingo.config.loader import get_directions

    return {direction.id: direction.default_profile for direction in get_directions()}


def get_active_profiles() -> dict[str, str]:
    data = _load()
    stored = data.get("active_profiles")
    defaults = _default_active_profiles()
    if not isinstance(stored, dict):
        return defaults
    merged = dict(defaults)
    for direction_id, profile_id in stored.items():
        if isinstance(direction_id, str) and isinstance(profile_id, str):
            merged[direction_id] = profile_id
    return merged


def save_active_profiles(active_profiles: dict[str, str]) -> None:
    data = _load()
    data["active_profiles"] = active_profiles
    _save(data)


def get_active_profile(direction_id: str) -> str:
    return get_active_profiles().get(direction_id, "detailed")


def get_ui_preferences() -> tuple[str | None, str | None]:
    from quicklingo.config.loader import get_direction

    data = _load()
    model_id = data.get("selected_model_id")
    direction = data.get("translation_direction")
    if not isinstance(model_id, str):
        model_id = None
    if not isinstance(direction, str) or get_direction(direction) is None:
        direction = None
    return model_id, direction


def save_ui_preferences(model_id: str, direction: str) -> None:
    data = _load()
    data["selected_model_id"] = model_id
    data["translation_direction"] = direction
    _save(data)


def get_ui_language() -> str:
    data = _load()
    lang = data.get("ui_language", "en")
    return lang if lang in ("en", "uk") else "en"


def save_ui_language(lang: str) -> None:
    data = _load()
    data["ui_language"] = lang if lang in ("en", "uk") else "en"
    _save(data)


def get_api_key(provider: str) -> str:
    data = _load()
    key_name = {
        "groq": "groq_api_key",
        "gemini": "gemini_api_key",
    }.get(provider)
    if not key_name:
        return ""
    value = data.get(key_name, "")
    if not isinstance(value, str):
        return ""
    return _decode_api_key_value(value.strip())


def _decode_api_key_value(value: str) -> str:
    if not value:
        return ""
    from quicklingo.privacy import dpapi

    if value.startswith("dpapi:"):
        if dpapi.dpapi_available():
            return dpapi.decrypt(value)
        return ""
    return value


def _encode_api_key_value(value: str) -> str:
    if not value:
        return ""
    from quicklingo.features import is_enabled
    from quicklingo.privacy import dpapi

    if is_enabled("privacy.encrypted_keys") and dpapi.dpapi_available():
        return dpapi.encrypt(value)
    return value


def get_api_keys() -> tuple[str, str]:
    return get_api_key("groq"), get_api_key("gemini")


def save_api_keys(*, groq: str, gemini: str) -> None:
    data = _load()
    data["groq_api_key"] = _encode_api_key_value(groq.strip())
    data["gemini_api_key"] = _encode_api_key_value(gemini.strip())
    _save(data)


def get_main_model_ids() -> list[str]:
    _defaults = (
        "llama-3.1-8b-instant",
        "llama-3.3-70b-versatile",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
    )
    data = _load()
    stored = data.get("main_model_ids")
    if not isinstance(stored, list):
        return list(_defaults)
    ids = [item for item in stored if isinstance(item, str) and item.strip()]
    return ids if ids else list(_defaults)


def save_main_model_ids(
    model_ids: list[str],
    *,
    custom_providers: dict[str, str] | None = None,
) -> None:
    data = _load()
    data["main_model_ids"] = model_ids
    if custom_providers is not None:
        data["custom_model_providers"] = custom_providers
    _save(data)


def get_custom_model_providers() -> dict[str, str]:
    data = _load()
    stored = data.get("custom_model_providers")
    if not isinstance(stored, dict):
        return {}
    return {
        key: value
        for key, value in stored.items()
        if isinstance(key, str) and isinstance(value, str) and value in ("groq", "gemini")
    }


def get_models_add_provider() -> str:
    data = _load()
    provider = data.get("models_add_provider", "groq")
    return provider if provider in ("groq", "gemini") else "groq"


def save_models_add_provider(provider: str) -> None:
    data = _load()
    data["models_add_provider"] = provider if provider in ("groq", "gemini") else "groq"
    _save(data)


def migrate_api_keys_to_encrypted() -> None:
    data = _load()
    changed = False
    for key_name in ("groq_api_key", "gemini_api_key"):
        value = data.get(key_name, "")
        if isinstance(value, str) and value and not value.startswith("dpapi:"):
            data[key_name] = _encode_api_key_value(value)
            changed = True
    if changed:
        _save(data)


def get_features_raw() -> dict:
    data = _load()
    stored = data.get("features")
    return stored if isinstance(stored, dict) else {}


def save_features_raw(features: dict) -> None:
    data = _load()
    data["features"] = features
    _save(data)


def get_learning_streak() -> tuple[int, str]:
    data = _load()
    streak = int(data.get("learning_streak", 0))
    last = data.get("learning_last_review_date", "")
    return streak, last if isinstance(last, str) else ""


def record_learning_review_today() -> int:
    from datetime import date, timedelta

    data = _load()
    today = date.today().isoformat()
    last = data.get("learning_last_review_date", "")
    streak = int(data.get("learning_streak", 0))
    if last == today:
        return streak
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    if last == yesterday:
        streak += 1
    else:
        streak = 1
    data["learning_streak"] = streak
    data["learning_last_review_date"] = today
    _save(data)
    return streak
