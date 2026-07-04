import base64
import json
from binascii import Error as BinasciiError

from quicklingo.paths import user_data_dir

_SETTINGS_FILE = "settings.json"

API_KEY_FIELDS: dict[str, str] = {
    "groq": "groq_api_key",
    "gemini": "gemini_api_key",
    "openrouter": "openrouter_api_key",
    "mistral": "mistral_api_key",
    "ollama": "ollama_api_key",
    "deepseek": "deepseek_api_key",
    "openai": "openai_api_key",
    "anthropic": "anthropic_api_key",
}

API_PROVIDERS: tuple[str, ...] = (
    "groq",
    "gemini",
    "openrouter",
    "mistral",
    "ollama",
    "deepseek",
    "openai",
    "anthropic",
)

DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434/v1"


DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434/v1"


class SettingsStore:
    """JSON settings file with load/save/update helpers."""

    def load(self) -> dict:
        path = _settings_path()
        if not path.is_file():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def save(self, data: dict) -> None:
        _settings_path().write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def update(self, patch: dict) -> None:
        data = self.load()
        data.update(patch)
        self.save(data)


_store = SettingsStore()


def _settings_path():
    return user_data_dir() / _SETTINGS_FILE


def _load() -> dict:
    return _store.load()


def _save(data: dict) -> None:
    _store.save(data)


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


def get_tool_window_state(window_id: str) -> dict:
    data = _load()
    states = data.get("tool_windows")
    if not isinstance(states, dict):
        return {}
    state = states.get(window_id)
    return dict(state) if isinstance(state, dict) else {}


def save_tool_window_state(window_id: str, patch: dict) -> None:
    data = _load()
    states = data.get("tool_windows")
    if not isinstance(states, dict):
        states = {}
    entry = dict(states.get(window_id, {}))
    entry.update(patch)
    states[window_id] = entry
    data["tool_windows"] = states
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


def get_last_tag() -> str:
    data = _load()
    tag = data.get("last_tag")
    return tag.strip() if isinstance(tag, str) else ""


def save_last_tag(tag: str) -> None:
    data = _load()
    data["last_tag"] = tag.strip()
    _save(data)


def get_profile_order() -> list[str]:
    data = _load()
    stored = data.get("profile_order")
    if not isinstance(stored, list):
        return []
    return [item for item in stored if isinstance(item, str) and item.strip()]


def save_profile_order(profile_ids: list[str]) -> None:
    data = _load()
    data["profile_order"] = profile_ids
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
    key_name = API_KEY_FIELDS.get(provider)
    if not key_name:
        return ""
    data = _load()
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


def get_api_keys() -> dict[str, str]:
    return {provider: get_api_key(provider) for provider in API_KEY_FIELDS}


def save_api_keys(
    *,
    groq: str = "",
    gemini: str = "",
    openrouter: str = "",
    mistral: str = "",
    ollama: str = "",
    deepseek: str = "",
    openai: str = "",
    anthropic: str = "",
) -> None:
    data = _load()
    for provider, value in (
        ("groq", groq),
        ("gemini", gemini),
        ("openrouter", openrouter),
        ("mistral", mistral),
        ("ollama", ollama),
        ("deepseek", deepseek),
        ("openai", openai),
        ("anthropic", anthropic),
    ):
        data[API_KEY_FIELDS[provider]] = _encode_api_key_value(value.strip())
    _save(data)


def get_ollama_base_url() -> str:
    data = _load()
    url = data.get("ollama_base_url", DEFAULT_OLLAMA_BASE_URL)
    if not isinstance(url, str) or not url.strip():
        return DEFAULT_OLLAMA_BASE_URL
    return url.strip().rstrip("/")


def save_ollama_base_url(url: str) -> None:
    data = _load()
    cleaned = url.strip().rstrip("/") or DEFAULT_OLLAMA_BASE_URL
    data["ollama_base_url"] = cleaned
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
        if isinstance(key, str) and isinstance(value, str) and value in API_PROVIDERS
    }


def get_models_add_provider() -> str:
    data = _load()
    provider = data.get("models_add_provider", "groq")
    return provider if provider in API_PROVIDERS else "groq"


def save_models_add_provider(provider: str) -> None:
    data = _load()
    data["models_add_provider"] = provider if provider in API_PROVIDERS else "groq"
    _save(data)


def migrate_api_keys_to_encrypted() -> None:
    data = _load()
    changed = False
    for key_name in API_KEY_FIELDS.values():
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


def get_learning_show_onboarding() -> bool:
    data = _load()
    return bool(data.get("learning_show_onboarding", True))


def set_learning_show_onboarding(show: bool) -> None:
    _store.update({"learning_show_onboarding": show})


def get_learning_flow_hint_dismissed() -> bool:
    data = _load()
    return bool(data.get("learning_flow_hint_dismissed", False))


def set_learning_flow_hint_dismissed(dismissed: bool) -> None:
    _store.update({"learning_flow_hint_dismissed": dismissed})


def get_learning_flow_cycle_completed() -> bool:
    data = _load()
    return bool(data.get("learning_flow_cycle_completed", False))


def set_learning_flow_cycle_completed(completed: bool) -> None:
    _store.update({"learning_flow_cycle_completed": completed})
