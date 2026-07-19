from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from quicklingo import settings
from quicklingo.config.json_io import read_json
from quicklingo.config.loader import reload_config
from quicklingo.config.validation import (
    ValidationError,
    check_direction_deletable,
    check_profile_deletable,
    prompt_path,
    validate_id,
)
from quicklingo.paths import user_config_dir


def _root() -> Path:
    return user_config_dir()


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    _atomic_write(path, text)


def _read_json_file(path: Path) -> dict[str, Any]:
    return read_json(path)


def _entity_path(subdir: str, entity_id: str) -> Path:
    return _root() / subdir / f"{entity_id}.json"


def _save_entity_json(
    subdir: str,
    entity_id: str,
    data: dict[str, Any],
    *,
    old_id: str | None = None,
) -> None:
    path = _entity_path(subdir, entity_id)
    if old_id and old_id != entity_id:
        old_path = _entity_path(subdir, old_id)
        if old_path.exists() and old_path != path:
            old_path.unlink(missing_ok=True)
    _atomic_write_json(path, data)
    reload_config()


# --- Directions ---


def save_direction(
    *,
    id: str,
    label: str,
    source_lang: str,
    target_lang: str,
    default_profile: str,
    enabled: bool,
    old_id: str | None = None,
) -> None:
    validate_id(id)
    if not label.strip():
        raise ValidationError("validation.empty_direction_label")
    validate_id(default_profile, field="ID")

    if old_id and old_id != id:
        validate_id(old_id)
        _rename_direction(old_id, id)

    data = {
        "id": id,
        "label": label.strip(),
        "source_lang": source_lang.strip(),
        "target_lang": target_lang.strip(),
        "default_profile": default_profile,
        "enabled": enabled,
    }
    _save_entity_json("directions", id, data, old_id=old_id)


def delete_direction(direction_id: str) -> None:
    validate_id(direction_id)
    from quicklingo.config.loader import get_all_directions

    check_direction_deletable(direction_id)

    path = _entity_path("directions", direction_id)
    if path.is_file():
        path.unlink()

    active = settings.get_active_profiles()
    if direction_id in active:
        active = {k: v for k, v in active.items() if k != direction_id}
        settings.save_active_profiles(active)

    ui_model, ui_dir = settings.get_ui_preferences()
    if ui_dir == direction_id:
        remaining = [
            d.id
            for d in get_all_directions()
            if d.id != direction_id and d.enabled
        ]
        if remaining:
            settings.save_ui_preferences(ui_model or "", remaining[0])

    reload_config()


def _rename_direction(old_id: str, new_id: str) -> None:
    for profile_path in (_root() / "profiles").glob("*.json"):
        data = _read_json_file(profile_path)
        changed = False
        prompts = dict(data.get("prompts", {}))
        formatters = dict(data.get("formatters", {}))
        if old_id in prompts:
            prompts[new_id] = prompts.pop(old_id)
            old_prompt = _root() / prompts[new_id]
            new_rel = prompt_path(data.get("id", profile_path.stem), new_id)
            new_prompt = _root() / new_rel
            if old_prompt.is_file():
                new_prompt.parent.mkdir(parents=True, exist_ok=True)
                if old_prompt != new_prompt:
                    old_prompt.replace(new_prompt)
                    prompts[new_id] = new_rel
            changed = True
        if old_id in formatters:
            formatters[new_id] = formatters.pop(old_id)
            changed = True
        if changed:
            data["prompts"] = prompts
            data["formatters"] = formatters
            _atomic_write_json(profile_path, data)

    active = settings.get_active_profiles()
    if old_id in active:
        active[new_id] = active.pop(old_id)
        settings.save_active_profiles(active)

    ui_model, ui_dir = settings.get_ui_preferences()
    if ui_dir == old_id:
        settings.save_ui_preferences(ui_model or "", new_id)


# --- Profiles ---


def save_profile(
    *,
    id: str,
    name: str,
    description: str,
    temperature: float,
    direction_prompts: dict[str, str],
    direction_formatters: dict[str, str],
    old_id: str | None = None,
) -> None:
    validate_id(id)
    if not name.strip():
        raise ValidationError("validation.empty_profile_name")
    if not direction_prompts:
        raise ValidationError("validation.profile_need_direction")

    profile_id = id
    if old_id and old_id != id:
        validate_id(old_id)
        _rename_profile(old_id, id)
        profile_id = id

    prompts_map: dict[str, str] = {}
    for direction_id, body in direction_prompts.items():
        validate_id(direction_id, field="ID напрямку")
        rel = prompt_path(profile_id, direction_id)
        _atomic_write(_root() / rel, body if body.endswith("\n") else body + "\n")
        prompts_map[direction_id] = rel

    formatters_map: dict[str, str] = {}
    for direction_id, formatter_id in direction_formatters.items():
        validate_id(direction_id, field="ID напрямку")
        validate_id(formatter_id, field="ID форматера")
        formatters_map[direction_id] = formatter_id

    data = {
        "id": profile_id,
        "name": name.strip(),
        "description": description.strip(),
        "prompts": prompts_map,
        "formatters": formatters_map,
        "temperature": float(temperature),
    }
    path = _root() / "profiles" / f"{profile_id}.json"
    if old_id and old_id != profile_id:
        old_path = _root() / "profiles" / f"{old_id}.json"
        if old_path.exists() and old_path != path:
            old_path.unlink(missing_ok=True)
    _atomic_write_json(path, data)
    reload_config()


def delete_profile(profile_id: str) -> None:
    validate_id(profile_id)

    check_profile_deletable(profile_id)

    path = _root() / "profiles" / f"{profile_id}.json"
    if path.is_file():
        data = _read_json_file(path)
        for rel in data.get("prompts", {}).values():
            prompt_file = _root() / rel
            if prompt_file.is_file():
                prompt_file.unlink(missing_ok=True)
        path.unlink()

    active = settings.get_active_profiles()
    changed = False
    for direction_id, active_pid in list(active.items()):
        if active_pid == profile_id:
            from quicklingo.config.loader import get_all_directions as _dirs

            direction = next((d for d in _dirs() if d.id == direction_id), None)
            if direction:
                active[direction_id] = direction.default_profile
                changed = True
    if changed:
        settings.save_active_profiles(active)

    reload_config()


def _rename_profile(old_id: str, new_id: str) -> None:
    old_path = _root() / "profiles" / f"{old_id}.json"
    if not old_path.is_file():
        return
    data = _read_json_file(old_path)
    new_prompts: dict[str, str] = {}
    for direction_id, rel in data.get("prompts", {}).items():
        old_file = _root() / rel
        new_rel = prompt_path(new_id, direction_id)
        new_file = _root() / new_rel
        if old_file.is_file():
            new_file.parent.mkdir(parents=True, exist_ok=True)
            old_file.replace(new_file)
        new_prompts[direction_id] = new_rel
    data["id"] = new_id
    data["prompts"] = new_prompts
    _atomic_write_json(_root() / "profiles" / f"{new_id}.json", data)
    if old_id != new_id:
        old_path.unlink(missing_ok=True)

    for direction_path in (_root() / "directions").glob("*.json"):
        d = _read_json_file(direction_path)
        if d.get("default_profile") == old_id:
            d["default_profile"] = new_id
            _atomic_write_json(direction_path, d)

    active = settings.get_active_profiles()
    changed = False
    for direction_id, pid in active.items():
        if pid == old_id:
            active[direction_id] = new_id
            changed = True
    if changed:
        settings.save_active_profiles(active)


def read_prompt_body(profile_id: str, direction_id: str) -> str:
    path = _root() / prompt_path(profile_id, direction_id)
    if path.is_file():
        return path.read_text(encoding="utf-8")
    from quicklingo.config.loader import get_profile

    profile = get_profile(profile_id)
    if profile and direction_id in profile.prompts:
        return profile.prompts[direction_id]
    return ""
