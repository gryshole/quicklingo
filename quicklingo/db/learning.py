from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta

from quicklingo.db.connection import connection


@dataclass
class LearningDeck:
    id: int
    name: str
    tag: str
    direction: str
    created_at: str
    analysis_summary: str = ""


@dataclass
class LearningCard:
    id: int
    deck_id: int
    front: str
    back: str
    context: str = ""
    priority: int = 3
    source_record_id: int | None = None
    ease: float = 2.5
    interval_days: int = 0
    next_review_date: str = ""
    last_reviewed: str = ""
    fsrs_state: str = ""


def _learning_card_columns(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("PRAGMA table_info(learning_cards)").fetchall()
    return {row["name"] for row in rows}


def _migrate_learning_columns(conn: sqlite3.Connection) -> None:
    cols = _learning_card_columns(conn)
    if "fsrs_state" not in cols:
        conn.execute(
            "ALTER TABLE learning_cards ADD COLUMN fsrs_state TEXT NOT NULL DEFAULT ''"
        )


def init_learning_tables() -> None:
    with connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS learning_decks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                tag TEXT NOT NULL DEFAULT '',
                direction TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                analysis_summary TEXT NOT NULL DEFAULT ''
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS learning_cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                deck_id INTEGER NOT NULL,
                front TEXT NOT NULL,
                back TEXT NOT NULL,
                context TEXT NOT NULL DEFAULT '',
                priority INTEGER NOT NULL DEFAULT 3,
                source_record_id INTEGER,
                ease REAL NOT NULL DEFAULT 2.5,
                interval_days INTEGER NOT NULL DEFAULT 0,
                next_review_date TEXT NOT NULL DEFAULT '',
                last_reviewed TEXT NOT NULL DEFAULT '',
                fsrs_state TEXT NOT NULL DEFAULT '',
                FOREIGN KEY (deck_id) REFERENCES learning_decks(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_learning_cards_deck
            ON learning_cards(deck_id)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_learning_cards_review
            ON learning_cards(next_review_date)
            """
        )
        _migrate_learning_columns(conn)


_CARD_SELECT = """
    SELECT id, deck_id, front, back, context, priority, source_record_id,
           ease, interval_days, next_review_date, last_reviewed, fsrs_state
    FROM learning_cards
"""


def get_or_create_deck(name: str, tag: str, direction: str) -> LearningDeck:
    with connection() as conn:
        row = conn.execute(
            """
            SELECT id, name, tag, direction, created_at, analysis_summary
            FROM learning_decks
            WHERE tag = ? AND direction = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (tag, direction),
        ).fetchone()
        if row:
            return _row_to_deck(row)
        cursor = conn.execute(
            """
            INSERT INTO learning_decks (name, tag, direction)
            VALUES (?, ?, ?)
            """,
            (name, tag, direction),
        )
        deck_id = cursor.lastrowid or 0
        row = conn.execute(
            """
            SELECT id, name, tag, direction, created_at, analysis_summary
            FROM learning_decks WHERE id = ?
            """,
            (deck_id,),
        ).fetchone()
    return _row_to_deck(row)


def update_deck_summary(deck_id: int, summary: str) -> None:
    with connection() as conn:
        conn.execute(
            "UPDATE learning_decks SET analysis_summary = ? WHERE id = ?",
            (summary, deck_id),
        )


def list_decks() -> list[LearningDeck]:
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT id, name, tag, direction, created_at, analysis_summary
            FROM learning_decks
            ORDER BY id DESC
            """
        ).fetchall()
    return [_row_to_deck(row) for row in rows]


def get_deck(deck_id: int) -> LearningDeck | None:
    with connection() as conn:
        row = conn.execute(
            """
            SELECT id, name, tag, direction, created_at, analysis_summary
            FROM learning_decks WHERE id = ?
            """,
            (deck_id,),
        ).fetchone()
    return _row_to_deck(row) if row else None


def list_cards(deck_id: int) -> list[LearningCard]:
    with connection() as conn:
        rows = conn.execute(
            f"""
            {_CARD_SELECT}
            WHERE deck_id = ?
            ORDER BY priority DESC, id ASC
            """,
            (deck_id,),
        ).fetchall()
    return [_row_to_card(row) for row in rows]


def upsert_card(
    deck_id: int,
    *,
    front: str,
    back: str,
    context: str = "",
    priority: int = 3,
    source_record_id: int | None = None,
) -> int:
    normalized_front = " ".join(front.split()).lower()
    with connection() as conn:
        existing = conn.execute(
            """
            SELECT id FROM learning_cards
            WHERE deck_id = ? AND lower(trim(front)) = ?
            """,
            (deck_id, normalized_front),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE learning_cards
                SET back = ?, context = ?, priority = ?, source_record_id = ?
                WHERE id = ?
                """,
                (back, context, priority, source_record_id, existing["id"]),
            )
            return int(existing["id"])
        today = date.today().isoformat()
        cursor = conn.execute(
            """
            INSERT INTO learning_cards
                (deck_id, front, back, context, priority, source_record_id, next_review_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (deck_id, front.strip(), back.strip(), context, priority, source_record_id, today),
        )
        return cursor.lastrowid or 0


def batch_upsert_cards(
    deck_id: int,
    cards: list[dict[str, object]],
) -> int:
    """Insert or update many cards in one transaction."""
    if not cards:
        return 0
    today = date.today().isoformat()
    count = 0
    with connection() as conn:
        for card in cards:
            front = str(card.get("front", "")).strip()
            back = str(card.get("back", "")).strip()
            if not front or not back:
                continue
            context = str(card.get("context", ""))
            priority = int(card.get("priority", 3))
            source_record_id = card.get("source_record_id")
            try:
                source_record_id = int(source_record_id) if source_record_id is not None else None
            except (TypeError, ValueError):
                source_record_id = None
            normalized_front = " ".join(front.split()).lower()
            existing = conn.execute(
                """
                SELECT id FROM learning_cards
                WHERE deck_id = ? AND lower(trim(front)) = ?
                """,
                (deck_id, normalized_front),
            ).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE learning_cards
                    SET back = ?, context = ?, priority = ?, source_record_id = ?
                    WHERE id = ?
                    """,
                    (back, context, priority, source_record_id, existing["id"]),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO learning_cards
                        (deck_id, front, back, context, priority, source_record_id, next_review_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (deck_id, front, back, context, priority, source_record_id, today),
                )
            count += 1
    return count


def update_card(
    card_id: int,
    *,
    front: str | None = None,
    back: str | None = None,
    context: str | None = None,
    priority: int | None = None,
) -> bool:
    fields: list[str] = []
    params: list[object] = []
    if front is not None:
        fields.append("front = ?")
        params.append(front.strip())
    if back is not None:
        fields.append("back = ?")
        params.append(back.strip())
    if context is not None:
        fields.append("context = ?")
        params.append(context)
    if priority is not None:
        fields.append("priority = ?")
        params.append(priority)
    if not fields:
        return False
    params.append(card_id)
    with connection() as conn:
        cursor = conn.execute(
            f"UPDATE learning_cards SET {', '.join(fields)} WHERE id = ?",
            params,
        )
        return cursor.rowcount > 0


def delete_card(card_id: int) -> bool:
    with connection() as conn:
        cursor = conn.execute("DELETE FROM learning_cards WHERE id = ?", (card_id,))
        return cursor.rowcount > 0


def get_due_cards(deck_id: int, *, limit: int = 20) -> list[LearningCard]:
    today = date.today().isoformat()
    with connection() as conn:
        rows = conn.execute(
            f"""
            {_CARD_SELECT}
            WHERE deck_id = ?
              AND (next_review_date = '' OR next_review_date <= ?)
            ORDER BY priority DESC, next_review_date ASC, id ASC
            LIMIT ?
            """,
            (deck_id, today, limit),
        ).fetchall()
    return [_row_to_card(row) for row in rows]


def record_review(card_id: int, *, again: bool | None = None, fsrs_rating=None) -> None:
    from quicklingo.features import is_enabled

    if is_enabled("learning.srs_review") and fsrs_rating is not None:
        from quicklingo.learning.fsrs_review import apply_fsrs_review

        apply_fsrs_review(card_id, fsrs_rating)
        return
    _record_review_lite(card_id, again=bool(again))


def _record_review_lite(card_id: int, *, again: bool) -> None:
    today = date.today()
    today_str = today.isoformat()
    with connection() as conn:
        row = conn.execute(
            """
            SELECT interval_days FROM learning_cards WHERE id = ?
            """,
            (card_id,),
        ).fetchone()
        if not row:
            return
        interval = int(row["interval_days"])
        if again:
            new_interval = 1
        else:
            new_interval = min(30, max(1, interval * 2 if interval else 1))
        next_review = (today + timedelta(days=new_interval)).isoformat()
        conn.execute(
            """
            UPDATE learning_cards
            SET interval_days = ?, next_review_date = ?, last_reviewed = ?
            WHERE id = ?
            """,
            (new_interval, next_review, today_str, card_id),
        )


def _row_to_deck(row: sqlite3.Row) -> LearningDeck:
    return LearningDeck(
        id=row["id"],
        name=row["name"],
        tag=row["tag"],
        direction=row["direction"],
        created_at=row["created_at"],
        analysis_summary=row["analysis_summary"] or "",
    )


def _row_to_card(row: sqlite3.Row) -> LearningCard:
    return LearningCard(
        id=row["id"],
        deck_id=row["deck_id"],
        front=row["front"],
        back=row["back"],
        context=row["context"] or "",
        priority=int(row["priority"]),
        source_record_id=row["source_record_id"],
        ease=float(row["ease"]),
        interval_days=int(row["interval_days"]),
        next_review_date=row["next_review_date"] or "",
        last_reviewed=row["last_reviewed"] or "",
        fsrs_state=row["fsrs_state"] or "",
    )
