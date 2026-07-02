from __future__ import annotations

import json
import re

_STRING_ITEM_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _extract_json_array(text: str) -> str:
    start = text.find("[")
    end = text.rfind("]")
    if start >= 0 and end > start:
        return text[start : end + 1]
    return text


def _salvage_string_array(text: str) -> list[str]:
    items = [_unescape_json_string(match.group(1)) for match in _STRING_ITEM_RE.finditer(text)]
    return [item.strip() for item in items if item.strip()]


def _unescape_json_string(value: str) -> str:
    try:
        return json.loads(f'"{value}"')
    except json.JSONDecodeError:
        return value.replace('\\"', '"')


def parse_word_list_response(raw: str, *, expected_count: int | None = None) -> list[str]:
    text = _extract_json_array(_strip_code_fence(raw))
    words: list[str] = []
    try:
        data = json.loads(text)
        if isinstance(data, list):
            words = [str(item).strip() for item in data if str(item).strip()]
    except json.JSONDecodeError:
        words = _salvage_string_array(text)
    if not words:
        raise ValueError("no words parsed")
    seen: set[str] = set()
    unique: list[str] = []
    for word in words:
        key = word.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(word)
    if expected_count is not None and len(unique) < max(1, expected_count // 2):
        raise ValueError("too few words parsed")
    return unique
