from __future__ import annotations

import json
from pathlib import Path

from quicklingo.paths import user_data_dir

_GLOSSARY_FILE = "glossary.json"


def _path() -> Path:
    return user_data_dir() / _GLOSSARY_FILE


def _load_raw() -> dict:
    path = _path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def get_terms(direction: str) -> list[tuple[str, str]]:
    data = _load_raw()
    entries = data.get(direction, [])
    if not isinstance(entries, list):
        return []
    result: list[tuple[str, str]] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        source = item.get("source", "")
        target = item.get("target", "")
        if isinstance(source, str) and isinstance(target, str) and source.strip() and target.strip():
            result.append((source.strip(), target.strip()))
    return result


def get_all() -> dict[str, list[dict[str, str]]]:
    data = _load_raw()
    result: dict[str, list[dict[str, str]]] = {}
    for direction, entries in data.items():
        if not isinstance(direction, str) or not isinstance(entries, list):
            continue
        cleaned: list[dict[str, str]] = []
        for item in entries:
            if not isinstance(item, dict):
                continue
            source = item.get("source", "")
            target = item.get("target", "")
            if isinstance(source, str) and isinstance(target, str):
                cleaned.append({"source": source, "target": target})
        result[direction] = cleaned
    return result


def save_all(data: dict[str, list[dict[str, str]]]) -> None:
    _path().write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def format_for_prompt(direction: str) -> str:
    terms = get_terms(direction)
    if not terms:
        return ""
    lines = [f"- {src} → {tgt}" for src, tgt in terms]
    return "Use these glossary terms when applicable:\n" + "\n".join(lines)
