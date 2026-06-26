from __future__ import annotations

import json
from pathlib import Path

from quicklingo.config.formatter_registry import get_formatter_callable
from quicklingo.config.models import Direction, FormatterDef, Profile
from quicklingo.config.seed import ensure_user_config
from quicklingo.paths import user_config_dir
from quicklingo import settings

_DIRECTIONS: dict[str, Direction] = {}
_PROFILES: dict[str, Profile] = {}
_FORMATTERS: dict[str, FormatterDef] = {}


def reload_config() -> None:
    global _DIRECTIONS, _PROFILES, _FORMATTERS
    ensure_user_config()
    _DIRECTIONS = _load_directions()
    _PROFILES = _load_profiles()
    _FORMATTERS = _load_formatters()


def _config_root() -> Path:
    return user_config_dir()


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_json_dir(subdir: str) -> dict[str, dict]:
    items: dict[str, dict] = {}
    base = _config_root() / subdir
    if not base.is_dir():
        return items
    for path in sorted(base.glob("*.json")):
        data = _read_json(path)
        item_id = data.get("id") or path.stem
        items[item_id] = data
    return items


def _resolve_prompt_path(relative: str) -> tuple[str, Path | None]:
    candidate = _config_root() / relative
    if candidate.is_file():
        return relative, candidate
    return relative, None


def _load_directions() -> dict[str, Direction]:
    directions: dict[str, Direction] = {}
    for item_id, data in _load_json_dir("directions").items():
        directions[item_id] = Direction(
            id=item_id,
            label=data["label"],
            source_lang=data.get("source_lang", ""),
            target_lang=data.get("target_lang", ""),
            default_profile=data.get("default_profile", "detailed"),
            enabled=bool(data.get("enabled", True)),
        )
    return directions


def _load_formatters() -> dict[str, FormatterDef]:
    formatters: dict[str, FormatterDef] = {}
    for item_id, data in _load_json_dir("formatters").items():
        formatters[item_id] = FormatterDef(
            id=item_id,
            name=data.get("name", item_id),
            engine=data["engine"],
            rules=list(data.get("rules", [])),
        )
    return formatters


def _load_profiles() -> dict[str, Profile]:
    profiles: dict[str, Profile] = {}
    for item_id, data in _load_json_dir("profiles").items():
        prompt_paths: dict[str, str] = {}
        prompts: dict[str, str] = {}
        for direction_id, rel in data.get("prompts", {}).items():
            rel_str, path = _resolve_prompt_path(rel)
            prompt_paths[direction_id] = rel_str
            if path is not None:
                prompts[direction_id] = path.read_text(encoding="utf-8")
        profiles[item_id] = Profile(
            id=item_id,
            name=data.get("name", item_id),
            description=data.get("description", ""),
            prompts=prompts,
            formatters=dict(data.get("formatters", {})),
            temperature=float(data.get("temperature", 0.2)),
            prompt_paths=prompt_paths,
        )
    return profiles


def get_directions() -> list[Direction]:
    if not _DIRECTIONS:
        reload_config()
    return [d for d in _DIRECTIONS.values() if d.enabled]


def get_all_directions() -> list[Direction]:
    if not _DIRECTIONS:
        reload_config()
    return list(_DIRECTIONS.values())


def get_all_profiles() -> list[Profile]:
    if not _PROFILES:
        reload_config()
    return list(_PROFILES.values())


def get_all_formatters() -> list[FormatterDef]:
    if not _FORMATTERS:
        reload_config()
    return list(_FORMATTERS.values())


def get_direction(direction_id: str) -> Direction | None:
    if not _DIRECTIONS:
        reload_config()
    return _DIRECTIONS.get(direction_id)


def get_direction_label(direction_id: str) -> str:
    direction = get_direction(direction_id)
    return direction.label if direction else direction_id


def get_profile(profile_id: str) -> Profile | None:
    if not _PROFILES:
        reload_config()
    return _PROFILES.get(profile_id)


def get_profiles_for_direction(direction_id: str) -> list[Profile]:
    if not _PROFILES:
        reload_config()
    return [
        profile
        for profile in _PROFILES.values()
        if direction_id in profile.prompts
    ]


def resolve_active_profile_id(direction_id: str) -> str:
    active = settings.get_active_profiles()
    if direction_id in active:
        profile_id = active[direction_id]
        if profile_id in _PROFILES or get_profile(profile_id):
            return profile_id
    direction = get_direction(direction_id)
    if direction:
        return direction.default_profile
    return "detailed"


def get_prompt(direction_id: str, profile_id: str | None = None) -> str:
    if not _PROFILES:
        reload_config()
    pid = profile_id or resolve_active_profile_id(direction_id)
    profile = get_profile(pid)
    if profile is None:
        raise KeyError(f"Unknown profile: {pid}")
    prompt = profile.prompts.get(direction_id)
    if prompt is None:
        raise KeyError(f"Profile {pid} has no prompt for direction {direction_id}")
    return prompt


def get_formatter_id(direction_id: str, profile_id: str | None = None) -> str:
    pid = profile_id or resolve_active_profile_id(direction_id)
    profile = get_profile(pid)
    if profile is None:
        raise KeyError(f"Unknown profile: {pid}")
    formatter_id = profile.formatters.get(direction_id)
    if formatter_id is None:
        raise KeyError(f"Profile {pid} has no formatter for direction {direction_id}")
    return formatter_id


def get_formatter_def(formatter_id: str) -> FormatterDef | None:
    if not _FORMATTERS:
        reload_config()
    return _FORMATTERS.get(formatter_id)


def get_formatter(direction_id: str, profile_id: str | None = None):
    formatter_id = get_formatter_id(direction_id, profile_id)
    formatter_def = get_formatter_def(formatter_id)
    if formatter_def is None:
        raise KeyError(f"Unknown formatter: {formatter_id}")
    return get_formatter_callable(formatter_def.engine, formatter_def.rules)


reload_config()
