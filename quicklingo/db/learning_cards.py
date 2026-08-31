from __future__ import annotations

import sqlite3
from datetime import date

from quicklingo import settings as app_settings
from quicklingo.db.connection import connection, fetch_all, in_placeholders, scalar_int
from quicklingo.db.learning_decks import get_deck
from quicklingo.db.learning_models import LearningCard, _CARD_SELECT, _row_to_card
from quicklingo.db.sync_schema import new_card_sync_id
from quicklingo.db.tombstones import record_card_delete
from quicklingo.learning.text_normalize import normalize_source


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
    placeholders = in_placeholders(len(card_ids))
    rows = fetch_all(
        f"{_CARD_SELECT} WHERE id IN ({placeholders}) ORDER BY id ASC",
        card_ids,
    )
    return [_row_to_card(row) for row in rows]


def get_card_review_stats(card_ids: list[int]) -> dict[int, dict[str, int | str]]:
    if not card_ids:
        return {}
    placeholders = in_placeholders(len(card_ids))
    stats: dict[int, dict[str, int | str]] = {
        card_id: {"review_count": 0, "last_rating": 0, "quiz_correct": 0, "quiz_total": 0}
        for card_id in card_ids
    }
    with connection() as conn:
        for row in conn.execute(
            f"""
            SELECT card_id, COUNT(*) AS cnt
            FROM review_logs
            WHERE card_id IN ({placeholders}) AND mode != 'cram'
            GROUP BY card_id
            """,
            card_ids,
        ).fetchall():
            stats[int(row["card_id"])]["review_count"] = int(row["cnt"])
        for row in conn.execute(
            f"""
            SELECT r.card_id, r.rating
            FROM review_logs r
            INNER JOIN (
                SELECT card_id, MAX(reviewed_at) AS max_at
                FROM review_logs
                WHERE card_id IN ({placeholders}) AND mode != 'cram'
                GROUP BY card_id
            ) latest ON latest.card_id = r.card_id AND latest.max_at = r.reviewed_at
            """,
            card_ids,
        ).fetchall():
            stats[int(row["card_id"])]["last_rating"] = int(row["rating"])
        for row in conn.execute(
            f"""
            SELECT card_id,
                   SUM(CASE WHEN correct = 1 THEN 1 ELSE 0 END) AS correct,
                   COUNT(*) AS total
            FROM quiz_logs
            WHERE card_id IN ({placeholders})
            GROUP BY card_id
            """,
            card_ids,
        ).fetchall():
            entry = stats[int(row["card_id"])]
            entry["quiz_correct"] = int(row["correct"] or 0)
            entry["quiz_total"] = int(row["total"] or 0)
    return stats


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
    normalized_front = normalize_source(front)
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
                SET back = ?, context = ?, hint = ?, notes = ?, priority = ?, source_record_id = ?,
                    content_updated_at = datetime('now')
                WHERE id = ?
                """,
                (back, context, hint, notes, priority, source_record_id, existing["id"]),
            )
            return int(existing["id"])
        today = date.today().isoformat()
        sync_id = new_card_sync_id()
        cursor = conn.execute(
            """
            INSERT INTO learning_cards
                (deck_id, front, back, context, hint, notes, priority, source_record_id,
                 next_review_date, sync_id, content_updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                deck_id,
                front.strip(),
                back.strip(),
                context,
                hint,
                notes,
                priority,
                source_record_id,
                today,
                sync_id,
            ),
        )
        return cursor.lastrowid or 0


def _optional_str(card: dict[str, object], key: str) -> str:
    value = card.get(key, "")
    return str(value).strip() if value is not None else ""


def _distractor_english_side(front: str, back: str, kind: str) -> str:
    return back if kind == "ua-en" else front


def _load_distractor_id_by_english_key(
    conn: sqlite3.Connection,
    deck_id: int,
    kind: str,
) -> dict[str, int]:
    from quicklingo.learning.quiz.distractor_deck import QUIZ_DISTRACTOR_CARD_TYPE
    from quicklingo.learning.quiz.normalize import normalize_english_quiz_key

    rows = conn.execute(
        """
        SELECT id, front, back FROM learning_cards
        WHERE deck_id = ? AND card_type = ?
        """,
        (deck_id, QUIZ_DISTRACTOR_CARD_TYPE),
    ).fetchall()
    index: dict[str, int] = {}
    for row in rows:
        english = _distractor_english_side(row["front"], row["back"], kind)
        key = normalize_english_quiz_key(english)
        if key and key not in index:
            index[key] = int(row["id"])
    return index


def batch_upsert_cards(
    deck_id: int,
    cards: list[dict[str, object]],
) -> list[int]:
    """Insert or update many cards in one transaction. Returns affected card ids."""
    if not cards:
        return []
    from quicklingo.config.loader import resolve_learning_direction

    today = date.today().isoformat()
    card_ids: list[int] = []
    deck = get_deck(deck_id)
    kind = resolve_learning_direction(deck.direction) if deck else "ua-en"
    with connection() as conn:
        distractor_ids_by_key: dict[str, int] | None = None
        for card in cards:
            front = str(card.get("front", "")).strip()
            back = str(card.get("back", "")).strip()
            if not front or not back:
                continue
            context = _optional_str(card, "context")
            hint = _optional_str(card, "hint")
            notes = _optional_str(card, "notes")
            image_prompt = _optional_str(card, "image_prompt")
            quiz_distractors = _optional_str(card, "quiz_distractors")
            card_type = _optional_str(card, "card_type") or "basic"
            next_review = card.get("next_review_date")
            if next_review is not None:
                next_review_date = str(next_review).strip()
            elif card_type == "quiz_distractor":
                from quicklingo.learning.quiz.distractor_deck import NO_REVIEW_SCHEDULE_DATE

                next_review_date = NO_REVIEW_SCHEDULE_DATE
            else:
                next_review_date = today
            priority = int(card.get("priority", 3))
            source_record_id = card.get("source_record_id")
            try:
                source_record_id = int(source_record_id) if source_record_id is not None else None
            except (TypeError, ValueError):
                source_record_id = None
            existing = None
            if card_type == "quiz_distractor":
                from quicklingo.learning.quiz.normalize import normalize_english_quiz_key

                if distractor_ids_by_key is None:
                    distractor_ids_by_key = _load_distractor_id_by_english_key(
                        conn, deck_id, kind
                    )
                english_key = normalize_english_quiz_key(
                    _distractor_english_side(front, back, kind)
                )
                if english_key:
                    existing_id = distractor_ids_by_key.get(english_key)
                    if existing_id is not None:
                        existing = {"id": existing_id}
            else:
                normalized_front = normalize_source(front)
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
                    "SELECT hint, notes, quiz_distractors FROM learning_cards WHERE id = ?",
                    (card_id,),
                ).fetchone()
                if existing_row:
                    if not hint:
                        hint = existing_row["hint"] or ""
                    if not notes:
                        notes = existing_row["notes"] or ""
                    if not quiz_distractors:
                        quiz_distractors = existing_row["quiz_distractors"] or ""
                conn.execute(
                    """
                    UPDATE learning_cards
                    SET back = ?, context = ?, hint = ?, notes = ?, image_prompt = ?,
                        quiz_distractors = ?, priority = ?, source_record_id = ?,
                        card_type = ?, next_review_date = ?,
                        content_updated_at = datetime('now')
                    WHERE id = ?
                    """,
                    (
                        back,
                        context,
                        hint,
                        notes,
                        image_prompt,
                        quiz_distractors,
                        priority,
                        source_record_id,
                        card_type,
                        next_review_date,
                        card_id,
                    ),
                )
            else:
                sync_id = new_card_sync_id()
                cursor = conn.execute(
                    """
                    INSERT INTO learning_cards
                        (deck_id, front, back, context, hint, notes, image_prompt,
                         quiz_distractors, priority, source_record_id, next_review_date,
                         card_type, sync_id, content_updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                    """,
                    (
                        deck_id,
                        front,
                        back,
                        context,
                        hint,
                        notes,
                        image_prompt,
                        quiz_distractors,
                        priority,
                        source_record_id,
                        next_review_date,
                        card_type,
                        sync_id,
                    ),
                )
                card_id = int(cursor.lastrowid or 0)
                if card_type == "quiz_distractor" and distractor_ids_by_key is not None:
                    from quicklingo.learning.quiz.normalize import normalize_english_quiz_key

                    english_key = normalize_english_quiz_key(
                        _distractor_english_side(front, back, kind)
                    )
                    if english_key:
                        distractor_ids_by_key[english_key] = card_id
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
                "quiz_distractors": card.quiz_distractors,
            },
            direction=direction,
            source_text=source_text,
        )
        new_hint = str(enriched.get("hint", "")).strip()
        new_context = str(enriched.get("context", "")).strip()
        new_notes = str(enriched.get("notes", "")).strip()
        new_quiz_distractors = str(enriched.get("quiz_distractors", "")).strip()
        if (
            new_hint == card.hint
            and new_context == card.context
            and new_notes == card.notes
            and new_quiz_distractors == card.quiz_distractors
        ):
            continue
        update_card(
            card.id,
            hint=new_hint,
            context=new_context,
            notes=new_notes,
            quiz_distractors=new_quiz_distractors,
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
    quiz_distractors: str | None = None,
) -> bool:
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
        "quiz_distractors": quiz_distractors,
    }
    content_fields = {
        "front",
        "back",
        "context",
        "hint",
        "notes",
        "priority",
        "phonetic",
        "image_prompt",
        "quiz_distractors",
    }
    fields: list[str] = []
    params: list[object] = []
    touches_content = False
    for column, value in updates.items():
        if value is None:
            continue
        if column in ("front", "back"):
            value = str(value).strip()
        if column in content_fields:
            touches_content = True
        fields.append(f"{column} = ?")
        params.append(value)
    if not fields:
        return False
    if touches_content:
        fields.append("content_updated_at = datetime('now')")
    params.append(card_id)
    with connection() as conn:
        cursor = conn.execute(
            f"UPDATE learning_cards SET {', '.join(fields)} WHERE id = ?",
            params,
        )
        return cursor.rowcount > 0


def delete_card(card_id: int) -> bool:
    with connection() as conn:
        record_card_delete(card_id, device_id=app_settings.get_sync_device_id(), conn=conn)
        cursor = conn.execute("DELETE FROM learning_cards WHERE id = ?", (card_id,))
        return cursor.rowcount > 0


def count_cards(deck_id: int) -> int:
    return scalar_int(
        "SELECT COUNT(*) AS cnt FROM learning_cards WHERE deck_id = ?",
        (deck_id,),
    )


def delete_deck(deck_id: int) -> bool:
    with connection() as conn:
        record_deck_delete(deck_id, device_id=app_settings.get_sync_device_id(), conn=conn)
        cursor = conn.execute("DELETE FROM learning_decks WHERE id = ?", (deck_id,))
        return cursor.rowcount > 0
