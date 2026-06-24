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
