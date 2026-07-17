from __future__ import annotations

import sqlite3

from quicklingo.db.connection import connection, get_connection
from quicklingo.sync.keys import (
    card_entity_key,
    deck_entity_key,
    quiz_entity_key,
    translation_entity_key,
)


def record_tombstone(
    entity_type: str,
    entity_key: str,
    *,
    device_id: str,
    conn: sqlite3.Connection | None = None,
) -> None:
    if conn is None:
        with connection() as managed:
            _insert_tombstone(managed, entity_type, entity_key, device_id)
        return
    _insert_tombstone(conn, entity_type, entity_key, device_id)


def _insert_tombstone(
    conn: sqlite3.Connection,
    entity_type: str,
    entity_key: str,
    device_id: str,
) -> None:
    conn.execute(
        """
        INSERT INTO sync_tombstones (entity_type, entity_key, deleted_at, device_id)
        VALUES (?, ?, datetime('now'), ?)
        ON CONFLICT(entity_type, entity_key) DO UPDATE SET
            deleted_at = excluded.deleted_at,
            device_id = excluded.device_id
        """,
        (entity_type, entity_key, device_id),
    )


def record_deck_children_tombstones(
    conn: sqlite3.Connection,
    deck_id: int,
    *,
    device_id: str,
) -> None:
    """Tombstone cards and quiz rows for a deck without recording the deck itself."""
    cards = conn.execute(
        "SELECT id, sync_id FROM learning_cards WHERE deck_id = ?",
        (deck_id,),
    ).fetchall()
    for card in cards:
        sync_id = str(card["sync_id"] or "")
        if not sync_id:
            continue
        record_tombstone("card", card_entity_key(sync_id), device_id=device_id, conn=conn)
        questions = conn.execute(
            "SELECT question_type FROM quiz_questions WHERE card_id = ?",
            (int(card["id"]),),
        ).fetchall()
        for question in questions:
            record_tombstone(
                "quiz_question",
                quiz_entity_key(sync_id, str(question["question_type"])),
                device_id=device_id,
                conn=conn,
            )


def record_deck_delete(deck_id: int, *, device_id: str, conn: sqlite3.Connection | None = None) -> None:
    def _run(c: sqlite3.Connection) -> None:
        row = c.execute(
            "SELECT tag, direction FROM learning_decks WHERE id = ?",
            (deck_id,),
        ).fetchone()
        if not row:
            return
        record_tombstone("deck", deck_entity_key(row["tag"], row["direction"]), device_id=device_id, conn=c)
        record_deck_children_tombstones(c, deck_id, device_id=device_id)

    if conn is None:
        with connection() as managed:
            _run(managed)
    else:
        _run(conn)


def record_card_delete(card_id: int, *, device_id: str, conn: sqlite3.Connection | None = None) -> None:
    def _run(c: sqlite3.Connection) -> None:
        row = c.execute(
            "SELECT sync_id FROM learning_cards WHERE id = ?",
            (card_id,),
        ).fetchone()
        if not row:
            return
        sync_id = str(row["sync_id"] or "")
        if not sync_id:
            return
        record_tombstone("card", card_entity_key(sync_id), device_id=device_id, conn=c)
        questions = c.execute(
            "SELECT question_type FROM quiz_questions WHERE card_id = ?",
            (card_id,),
        ).fetchall()
        for question in questions:
            record_tombstone(
                "quiz_question",
                quiz_entity_key(sync_id, str(question["question_type"])),
                device_id=device_id,
                conn=c,
            )

    if conn is None:
        with connection() as managed:
            _run(managed)
    else:
        _run(conn)


def record_translation_delete(
    *,
    content_hash: str,
    direction: str,
    profile_id: str,
    device_id: str,
    conn: sqlite3.Connection | None = None,
) -> None:
    key = translation_entity_key(content_hash, direction, profile_id)
    record_tombstone("translation", key, device_id=device_id, conn=conn)


def record_all_translations_deleted(*, device_id: str, conn: sqlite3.Connection | None = None) -> None:
    def _run(c: sqlite3.Connection) -> None:
        rows = c.execute(
            "SELECT content_hash, direction, profile_id FROM translations"
        ).fetchall()
        for row in rows:
            record_translation_delete(
                content_hash=str(row["content_hash"] or ""),
                direction=str(row["direction"] or ""),
                profile_id=str(row["profile_id"] or ""),
                device_id=device_id,
                conn=c,
            )

    if conn is None:
        with connection() as managed:
            _run(managed)
    else:
        _run(conn)


def clear_tombstone(
    entity_type: str,
    entity_key: str,
    *,
    conn: sqlite3.Connection | None = None,
) -> None:
    if conn is None:
        with connection() as managed:
            managed.execute(
                """
                DELETE FROM sync_tombstones
                WHERE entity_type = ? AND entity_key = ?
                """,
                (entity_type, entity_key),
            )
        return
    conn.execute(
        """
        DELETE FROM sync_tombstones
        WHERE entity_type = ? AND entity_key = ?
        """,
        (entity_type, entity_key),
    )


def clear_deck_tombstone(
    tag: str,
    direction: str,
    *,
    conn: sqlite3.Connection | None = None,
) -> None:
    clear_tombstone("deck", deck_entity_key(tag, direction), conn=conn)


def record_quiz_question_delete(
    *,
    card_sync_id: str,
    question_type: str,
    device_id: str,
    conn: sqlite3.Connection | None = None,
) -> None:
    if not card_sync_id or not question_type:
        return
    record_tombstone(
        "quiz_question",
        quiz_entity_key(card_sync_id, question_type),
        device_id=device_id,
        conn=conn,
    )


def is_tombstoned(conn: sqlite3.Connection, entity_type: str, entity_key: str) -> bool:
    row = conn.execute(
        """
        SELECT 1 FROM sync_tombstones
        WHERE entity_type = ? AND entity_key = ?
        """,
        (entity_type, entity_key),
    ).fetchone()
    return row is not None


def list_tombstones(conn: sqlite3.Connection | None = None) -> list[sqlite3.Row]:
    if conn is None:
        return get_connection().execute(
            "SELECT entity_type, entity_key, deleted_at, device_id FROM sync_tombstones"
        ).fetchall()
    return conn.execute(
        "SELECT entity_type, entity_key, deleted_at, device_id FROM sync_tombstones"
    ).fetchall()
