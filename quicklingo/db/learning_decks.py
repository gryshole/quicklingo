from __future__ import annotations

from quicklingo.db.connection import connection
from quicklingo.db.learning_models import LearningDeck, _row_to_deck
from quicklingo.db.tombstones import clear_deck_tombstone, record_deck_delete

_DECK_SELECT = """
    SELECT id, name, tag, direction, created_at, analysis_summary, source
    FROM learning_decks
"""


def get_or_create_deck(name: str, tag: str, direction: str) -> LearningDeck:
    with connection() as conn:
        row = conn.execute(
            f"""
            {_DECK_SELECT}
            WHERE tag = ? AND direction = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (tag, direction),
        ).fetchone()
        if row:
            return _row_to_deck(row)
        clear_deck_tombstone(tag, direction, conn=conn)
        cursor = conn.execute(
            """
            INSERT INTO learning_decks (name, tag, direction, source, updated_at)
            VALUES (?, ?, ?, 'corpus', datetime('now'))
            """,
            (name, tag, direction),
        )
        deck_id = cursor.lastrowid or 0
        row = conn.execute(
            f"{_DECK_SELECT} WHERE id = ?",
            (deck_id,),
        ).fetchone()
    return _row_to_deck(row)


def find_deck_by_tag(tag: str, direction: str) -> LearningDeck | None:
    with connection() as conn:
        row = conn.execute(
            f"""
            {_DECK_SELECT}
            WHERE tag = ? AND direction = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (tag, direction),
        ).fetchone()
    return _row_to_deck(row) if row else None


def create_deck(
    name: str,
    tag: str,
    direction: str,
    *,
    source: str = "ai",
) -> LearningDeck:
    """Create or revive a deck. Sync identity is tag|direction (not display name)."""
    with connection() as conn:
        clear_deck_tombstone(tag, direction, conn=conn)
        existing = conn.execute(
            f"""
            {_DECK_SELECT}
            WHERE tag = ? AND direction = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (tag, direction),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE learning_decks
                SET name = ?, source = ?, updated_at = datetime('now')
                WHERE id = ?
                """,
                (name, source, int(existing["id"])),
            )
            row = conn.execute(
                f"{_DECK_SELECT} WHERE id = ?",
                (int(existing["id"]),),
            ).fetchone()
            return _row_to_deck(row)
        cursor = conn.execute(
            """
            INSERT INTO learning_decks (name, tag, direction, source, updated_at)
            VALUES (?, ?, ?, ?, datetime('now'))
            """,
            (name, tag, direction, source),
        )
        deck_id = cursor.lastrowid or 0
        row = conn.execute(
            f"{_DECK_SELECT} WHERE id = ?",
            (deck_id,),
        ).fetchone()
    return _row_to_deck(row)


def update_deck_summary(deck_id: int, summary: str) -> None:
    with connection() as conn:
        conn.execute(
            "UPDATE learning_decks SET analysis_summary = ?, updated_at = datetime('now') WHERE id = ?",
            (summary, deck_id),
        )


def list_decks() -> list[LearningDeck]:
    with connection() as conn:
        rows = conn.execute(
            f"""
            {_DECK_SELECT}
            ORDER BY id DESC
            """
        ).fetchall()
    return [_row_to_deck(row) for row in rows]


def get_or_create_distractor_deck(direction: str) -> LearningDeck:
    from quicklingo.i18n import tr
    from quicklingo.learning.quiz.distractor_deck import (
        QUIZ_DISTRACTOR_DECK_SOURCE,
        QUIZ_DISTRACTOR_DECK_TAG,
    )

    name = tr("learning.quiz_distractor_deck_name")
    return create_deck(
        name=name,
        tag=QUIZ_DISTRACTOR_DECK_TAG,
        direction=direction,
        source=QUIZ_DISTRACTOR_DECK_SOURCE,
    )


def get_deck(deck_id: int) -> LearningDeck | None:
    with connection() as conn:
        row = conn.execute(
            f"{_DECK_SELECT} WHERE id = ?",
            (deck_id,),
        ).fetchone()
    return _row_to_deck(row) if row else None
