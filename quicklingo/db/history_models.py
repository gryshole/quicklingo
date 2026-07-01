from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass

from quicklingo.learning.text_normalize import normalize_for_hash


@dataclass
class TranslationRecord:
    id: int
    created_at: str
    direction: str
    source_text: str
    result_text: str
    model: str
    profile_id: str = ""
    content_hash: str = ""
    is_starred: bool = False
    tags: str = ""


def parse_tags(raw: str) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def normalize_tag_names(tags: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        value = tag.strip()
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(value)
    return cleaned


def format_tags(tags: list[str]) -> str:
    return ", ".join(normalize_tag_names(tags))


def make_content_hash(source_text: str, direction: str, profile_id: str) -> str:
    normalized = normalize_for_hash(source_text)
    payload = f"{direction}\0{profile_id}\0{normalized}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def row_to_record(row: sqlite3.Row) -> TranslationRecord:
    return TranslationRecord(
        id=row["id"],
        created_at=row["created_at"],
        direction=row["direction"],
        source_text=row["source_text"],
        result_text=row["result_text"],
        model=row["model"],
        profile_id=row["profile_id"],
        content_hash=row["content_hash"],
        is_starred=bool(row["is_starred"]),
        tags=row["tags"] or "",
    )
