from __future__ import annotations

import sqlite3

from quicklingo.config.loader import resolve_learning_direction
from quicklingo.db.history_tags import apply_translation_tag_changes
from quicklingo.learning.text_normalize import normalize_source


def find_translation_id_for_card(
    conn: sqlite3.Connection,
    *,
    source_record_id: int | None,
    front: str,
    deck_direction: str,
) -> int | None:
    if source_record_id is not None:
        row = conn.execute(
            "SELECT id FROM translations WHERE id = ?",
            (source_record_id,),
        ).fetchone()
        if row is not None:
            return int(row["id"])

    normalized = normalize_source(front)
    if not normalized:
        return None
    kind = resolve_learning_direction(deck_direction)

    for column in ("source_text", "result_text"):
        rows = conn.execute(
            f"""
            SELECT id, direction
            FROM translations
            WHERE lower(trim({column})) = ?
            ORDER BY id DESC
            """,
            (normalized,),
        ).fetchall()
        for row in rows:
            if resolve_learning_direction(str(row["direction"])) == kind:
                return int(row["id"])
    return None


def sync_history_tags_for_card_move(
    conn: sqlite3.Connection,
    *,
    source_record_id: int | None,
    front: str,
    deck_direction: str,
    source_tag: str,
    target_tag: str,
) -> bool:
    """Mirror deck move in translation history tags (create target tag if needed)."""
    translation_id = find_translation_id_for_card(
        conn,
        source_record_id=source_record_id,
        front=front,
        deck_direction=deck_direction,
    )
    if translation_id is None:
        return False

    remove: list[str] = []
    src = (source_tag or "").strip()
    tgt = (target_tag or "").strip()
    if src and tgt and src.lower() != tgt.lower():
        remove.append(src)

    return apply_translation_tag_changes(
        conn,
        translation_id,
        add=[tgt] if tgt else None,
        remove=remove or None,
    )
