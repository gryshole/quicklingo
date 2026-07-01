from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta

from quicklingo.db.connection import connection, get_connection


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
    hint: str = ""
    notes: str = ""
    image_path: str = ""
    image_prompt: str = ""
    phonetic: str = ""
    audio_path: str = ""
    card_type: str = "basic"
    priority: int = 3
    source_record_id: int | None = None
    ease: float = 2.5
    interval_days: int = 0
    next_review_date: str = ""
    last_reviewed: str = ""
    fsrs_state: str = ""


_CARD_COLUMNS = (
    "id, deck_id, front, back, context, hint, notes, image_path, image_prompt, "
    "phonetic, audio_path, card_type, priority, source_record_id, ease, "
    "interval_days, next_review_date, last_reviewed, fsrs_state"
)

_CARD_SELECT = f"""
    SELECT {_CARD_COLUMNS}
    FROM learning_cards
"""


def _learning_card_columns(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("PRAGMA table_info(learning_cards)").fetchall()
    return {row["name"] for row in rows}


def _migrate_learning_columns(conn: sqlite3.Connection) -> None:
    cols = _learning_card_columns(conn)
    additions = {
        "fsrs_state": "TEXT NOT NULL DEFAULT ''",
        "hint": "TEXT NOT NULL DEFAULT ''",
        "notes": "TEXT NOT NULL DEFAULT ''",
        "image_path": "TEXT NOT NULL DEFAULT ''",
        "image_prompt": "TEXT NOT NULL DEFAULT ''",
        "phonetic": "TEXT NOT NULL DEFAULT ''",
        "audio_path": "TEXT NOT NULL DEFAULT ''",
        "card_type": "TEXT NOT NULL DEFAULT 'basic'",
    }
    for name, ddl in additions.items():
        if name not in cols:
            conn.execute(f"ALTER TABLE learning_cards ADD COLUMN {name} {ddl}")


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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS review_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_id INTEGER NOT NULL,
                reviewed_at TEXT NOT NULL DEFAULT (datetime('now')),
                rating INTEGER NOT NULL,
                mode TEXT NOT NULL DEFAULT 'flip',
                was_correct INTEGER,
                response_ms INTEGER,
                FOREIGN KEY (card_id) REFERENCES learning_cards(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_review_logs_card
            ON review_logs(card_id)
            """
        )
        _migrate_learning_columns(conn)


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


def get_card(card_id: int) -> LearningCard | None:
    with connection() as conn:
        row = conn.execute(
            f"{_CARD_SELECT} WHERE id = ?",
            (card_id,),
        ).fetchone()
    return _row_to_card(row) if row else None


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


def list_cards_by_ids(card_ids: list[int]) -> list[LearningCard]:
    if not card_ids:
        return []
    placeholders = ",".join("?" * len(card_ids))
    with connection() as conn:
        rows = conn.execute(
            f"{_CARD_SELECT} WHERE id IN ({placeholders}) ORDER BY id ASC",
            card_ids,
        ).fetchall()
    return [_row_to_card(row) for row in rows]


def list_struggled_cards_today(deck_id: int) -> list[LearningCard]:
    today = date.today().isoformat()
    with connection() as conn:
        rows = conn.execute(
            f"""
            {_CARD_SELECT}
            WHERE deck_id = ?
              AND id IN (
                SELECT DISTINCT r.card_id
                FROM review_logs r
                INNER JOIN learning_cards lc ON lc.id = r.card_id
                WHERE lc.deck_id = ?
                  AND date(r.reviewed_at) = ?
                  AND r.rating IN (1, 2)
                  AND r.mode != 'cram'
              )
            ORDER BY priority DESC, id ASC
            """,
            (deck_id, deck_id, today),
        ).fetchall()
    return [_row_to_card(row) for row in rows]


def list_reviewed_card_ids_today(deck_id: int) -> list[int]:
    today = date.today().isoformat()
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT r.card_id, MIN(r.reviewed_at) AS first_at
            FROM review_logs r
            INNER JOIN learning_cards lc ON lc.id = r.card_id
            WHERE lc.deck_id = ?
              AND date(r.reviewed_at) = ?
              AND r.mode != 'cram'
            GROUP BY r.card_id
            ORDER BY first_at, r.card_id
            """,
            (deck_id, today),
        ).fetchall()
    return [int(row["card_id"]) for row in rows]


def list_reviewed_cards_today(deck_id: int) -> list[LearningCard]:
    card_ids = list_reviewed_card_ids_today(deck_id)
    if not card_ids:
        return []
    order = {card_id: index for index, card_id in enumerate(card_ids)}
    cards = list_cards_by_ids(card_ids)
    cards.sort(key=lambda card: order.get(card.id, len(card_ids)))
    return cards


def upsert_card(
    deck_id: int,
    *,
    front: str,
    back: str,
    context: str = "",
    hint: str = "",
    notes: str = "",
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
                SET back = ?, context = ?, hint = ?, notes = ?, priority = ?, source_record_id = ?
                WHERE id = ?
                """,
                (back, context, hint, notes, priority, source_record_id, existing["id"]),
            )
            return int(existing["id"])
        today = date.today().isoformat()
        cursor = conn.execute(
            """
            INSERT INTO learning_cards
                (deck_id, front, back, context, hint, notes, priority, source_record_id, next_review_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (deck_id, front.strip(), back.strip(), context, hint, notes, priority, source_record_id, today),
        )
        return cursor.lastrowid or 0


def _optional_str(card: dict[str, object], key: str) -> str:
    value = card.get(key, "")
    return str(value).strip() if value is not None else ""


def batch_upsert_cards(
    deck_id: int,
    cards: list[dict[str, object]],
) -> list[int]:
    """Insert or update many cards in one transaction. Returns affected card ids."""
    if not cards:
        return []
    today = date.today().isoformat()
    card_ids: list[int] = []
    with connection() as conn:
        for card in cards:
            front = str(card.get("front", "")).strip()
            back = str(card.get("back", "")).strip()
            if not front or not back:
                continue
            context = _optional_str(card, "context")
            hint = _optional_str(card, "hint")
            notes = _optional_str(card, "notes")
            image_prompt = _optional_str(card, "image_prompt")
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
                card_id = int(existing["id"])
                existing_row = conn.execute(
                    "SELECT hint, notes FROM learning_cards WHERE id = ?",
                    (card_id,),
                ).fetchone()
                if existing_row:
                    if not hint:
                        hint = existing_row["hint"] or ""
                    if not notes:
                        notes = existing_row["notes"] or ""
                conn.execute(
                    """
                    UPDATE learning_cards
                    SET back = ?, context = ?, hint = ?, notes = ?, image_prompt = ?,
                        priority = ?, source_record_id = ?
                    WHERE id = ?
                    """,
                    (back, context, hint, notes, image_prompt, priority, source_record_id, card_id),
                )
            else:
                cursor = conn.execute(
                    """
                    INSERT INTO learning_cards
                        (deck_id, front, back, context, hint, notes, image_prompt,
                         priority, source_record_id, next_review_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        deck_id,
                        front,
                        back,
                        context,
                        hint,
                        notes,
                        image_prompt,
                        priority,
                        source_record_id,
                        today,
                    ),
                )
                card_id = int(cursor.lastrowid or 0)
            card_ids.append(card_id)
    return card_ids


def backfill_card_fields(deck_id: int) -> int:
    """Re-sanitize hint/context/notes on existing cards (fix spoilers, remove boilerplate)."""
    from quicklingo.db.history_repository import get_source_text
    from quicklingo.learning.card_prompt import enrich_card_fields

    deck = get_deck(deck_id)
    direction = deck.direction if deck else "ua-en"
    updated = 0
    for card in list_cards(deck_id):
        source_text = ""
        if card.source_record_id is not None:
            source_text = get_source_text(card.source_record_id)
        enriched = enrich_card_fields(
            {
                "front": card.front,
                "back": card.back,
                "context": card.context,
                "hint": card.hint,
                "notes": card.notes,
            },
            direction=direction,
            source_text=source_text,
        )
        new_hint = str(enriched.get("hint", "")).strip()
        new_context = str(enriched.get("context", "")).strip()
        new_notes = str(enriched.get("notes", "")).strip()
        if (
            new_hint == card.hint
            and new_context == card.context
            and new_notes == card.notes
        ):
            continue
        update_card(
            card.id,
            hint=new_hint,
            context=new_context,
            notes=new_notes,
        )
        updated += 1
    return updated


def update_card(
    card_id: int,
    *,
    front: str | None = None,
    back: str | None = None,
    context: str | None = None,
    hint: str | None = None,
    notes: str | None = None,
    priority: int | None = None,
    image_path: str | None = None,
    image_prompt: str | None = None,
    phonetic: str | None = None,
    audio_path: str | None = None,
) -> bool:
    fields: list[str] = []
    params: list[object] = []
    updates = {
        "front": front,
        "back": back,
        "context": context,
        "hint": hint,
        "notes": notes,
        "priority": priority,
        "image_path": image_path,
        "image_prompt": image_prompt,
        "phonetic": phonetic,
        "audio_path": audio_path,
    }
    for column, value in updates.items():
        if value is None:
            continue
        if column in ("front", "back"):
            value = str(value).strip()
        fields.append(f"{column} = ?")
        params.append(value)
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


def count_cards(deck_id: int) -> int:
    row = get_connection().execute(
        "SELECT COUNT(*) AS cnt FROM learning_cards WHERE deck_id = ?",
        (deck_id,),
    ).fetchone()
    return int(row["cnt"])


def delete_deck(deck_id: int) -> bool:
    with connection() as conn:
        cursor = conn.execute("DELETE FROM learning_decks WHERE id = ?", (deck_id,))
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


def insert_review_log(
    card_id: int,
    *,
    rating: int,
    mode: str = "flip",
    was_correct: bool | None = None,
    response_ms: int | None = None,
) -> None:
    with connection() as conn:
        conn.execute(
            """
            INSERT INTO review_logs (card_id, rating, mode, was_correct, response_ms)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                card_id,
                rating,
                mode,
                None if was_correct is None else int(was_correct),
                response_ms,
            ),
        )


def record_review(
    card_id: int,
    *,
    again: bool | None = None,
    fsrs_rating=None,
    mode: str = "flip",
    was_correct: bool | None = None,
    response_ms: int | None = None,
) -> None:
    from quicklingo.features import is_enabled

    if fsrs_rating is not None:
        rating_value = int(getattr(fsrs_rating, "value", fsrs_rating))
    else:
        rating_value = 1 if again else 3
    insert_review_log(
        card_id,
        rating=rating_value,
        mode=mode,
        was_correct=was_correct,
        response_ms=response_ms,
    )
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
    keys = row.keys()
    return LearningCard(
        id=row["id"],
        deck_id=row["deck_id"],
        front=row["front"],
        back=row["back"],
        context=row["context"] or "",
        hint=row["hint"] if "hint" in keys else "",
        notes=row["notes"] if "notes" in keys else "",
        image_path=row["image_path"] if "image_path" in keys else "",
        image_prompt=row["image_prompt"] if "image_prompt" in keys else "",
        phonetic=row["phonetic"] if "phonetic" in keys else "",
        audio_path=row["audio_path"] if "audio_path" in keys else "",
        card_type=row["card_type"] if "card_type" in keys else "basic",
        priority=int(row["priority"]),
        source_record_id=row["source_record_id"],
        ease=float(row["ease"]),
        interval_days=int(row["interval_days"]),
        next_review_date=row["next_review_date"] or "",
        last_reviewed=row["last_reviewed"] or "",
        fsrs_state=row["fsrs_state"] or "",
    )
