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
