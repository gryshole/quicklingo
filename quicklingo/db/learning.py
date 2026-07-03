from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta

from quicklingo.db.connection import connection, get_connection

QUIZ_QUESTION_TYPES = ("fill_blank", "definition_match", "translation_recall")


@dataclass
class LearningDeck:
    id: int
    name: str
    tag: str
    direction: str
    created_at: str
    analysis_summary: str = ""
    source: str = "corpus"


@dataclass
class QuizQuestionRecord:
    id: int
    card_id: int
    question_type: str
    prompt_text: str
    example_sentence: str
    choices_pool: list[str]
    correct_english: str
    status: str
    model_id: str
    prompt_version: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class QuizCoverageStats:
    eligible: int
    ready: int
    missing_any: int
    missing_by_type: dict[str, int]


@dataclass(frozen=True)
class GlobalQuizCoverageStats:
    decks_total: int
    decks_complete: int
    decks_incomplete: int


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
    quiz_distractors: str = ""


_CARD_COLUMNS = (
    "id, deck_id, front, back, context, hint, notes, image_path, image_prompt, "
    "phonetic, audio_path, card_type, priority, source_record_id, ease, "
    "interval_days, next_review_date, last_reviewed, fsrs_state, quiz_distractors"
)

_CARD_SELECT = f"""
    SELECT {_CARD_COLUMNS}
    FROM learning_cards
"""


def _learning_card_columns(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("PRAGMA table_info(learning_cards)").fetchall()
    return {row["name"] for row in rows}


def _learning_deck_columns(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("PRAGMA table_info(learning_decks)").fetchall()
    return {row["name"] for row in rows}


def _migrate_deck_columns(conn: sqlite3.Connection) -> None:
    cols = _learning_deck_columns(conn)
    if "source" not in cols:
        conn.execute(
            "ALTER TABLE learning_decks ADD COLUMN source TEXT NOT NULL DEFAULT 'corpus'"
        )


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
        "quiz_distractors": "TEXT NOT NULL DEFAULT ''",
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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS quiz_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_id INTEGER,
                answered_at TEXT NOT NULL DEFAULT (datetime('now')),
                question_type TEXT NOT NULL,
                selected TEXT NOT NULL,
                correct INTEGER NOT NULL,
                response_ms INTEGER,
                FOREIGN KEY (card_id) REFERENCES learning_cards(id) ON DELETE SET NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_quiz_logs_date
            ON quiz_logs(date(answered_at))
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_quiz_logs_card
            ON quiz_logs(card_id)
            """
        )
        _migrate_deck_columns(conn)
        _migrate_learning_columns(conn)
        _migrate_quiz_questions(conn)
        _migrate_quiz_logs_columns(conn)


def _quiz_logs_columns(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("PRAGMA table_info(quiz_logs)").fetchall()
    return {row["name"] for row in rows}


def _migrate_quiz_questions(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS quiz_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_id INTEGER NOT NULL,
            question_type TEXT NOT NULL,
            prompt_text TEXT NOT NULL,
            example_sentence TEXT NOT NULL DEFAULT '',
            choices_pool TEXT NOT NULL,
            correct_english TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            model_id TEXT NOT NULL DEFAULT '',
            prompt_version TEXT NOT NULL DEFAULT 'v1',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (card_id) REFERENCES learning_cards(id) ON DELETE CASCADE,
            UNIQUE(card_id, question_type)
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_quiz_questions_card
        ON quiz_questions(card_id)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_quiz_questions_status
        ON quiz_questions(status)
        """
    )


def _migrate_quiz_logs_columns(conn: sqlite3.Connection) -> None:
    cols = _quiz_logs_columns(conn)
    if "question_id" not in cols:
        conn.execute("ALTER TABLE quiz_logs ADD COLUMN question_id INTEGER")
    if "choices_shown" not in cols:
        conn.execute("ALTER TABLE quiz_logs ADD COLUMN choices_shown TEXT NOT NULL DEFAULT ''")


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
        cursor = conn.execute(
            """
            INSERT INTO learning_decks (name, tag, direction, source)
            VALUES (?, ?, ?, 'corpus')
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
    with connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO learning_decks (name, tag, direction, source)
            VALUES (?, ?, ?, ?)
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
            "UPDATE learning_decks SET analysis_summary = ? WHERE id = ?",
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


def get_deck(deck_id: int) -> LearningDeck | None:
    with connection() as conn:
        row = conn.execute(
            f"{_DECK_SELECT} WHERE id = ?",
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
            quiz_distractors = _optional_str(card, "quiz_distractors")
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
                        quiz_distractors = ?, priority = ?, source_record_id = ?
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
                        card_id,
                    ),
                )
            else:
                cursor = conn.execute(
                    """
                    INSERT INTO learning_cards
                        (deck_id, front, back, context, hint, notes, image_prompt,
                         quiz_distractors, priority, source_record_id, next_review_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        "quiz_distractors": quiz_distractors,
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


def insert_quiz_log(
    *,
    card_id: int | None,
    question_type: str,
    selected: str,
    correct: bool,
    response_ms: int | None = None,
    question_id: int | None = None,
    choices_shown: str = "",
) -> None:
    with connection() as conn:
        conn.execute(
            """
            INSERT INTO quiz_logs (
                card_id, question_type, selected, correct, response_ms,
                question_id, choices_shown
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                card_id,
                question_type,
                selected,
                int(correct),
                response_ms,
                question_id,
                choices_shown,
            ),
        )


def batch_insert_quiz_logs(entries: list[dict[str, object]]) -> None:
    if not entries:
        return
    with connection() as conn:
        conn.executemany(
            """
            INSERT INTO quiz_logs (
                card_id, question_type, selected, correct, response_ms,
                question_id, choices_shown
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    entry.get("card_id"),
                    str(entry.get("question_type", "")),
                    str(entry.get("selected", "")),
                    int(bool(entry.get("correct"))),
                    entry.get("response_ms"),
                    entry.get("question_id"),
                    str(entry.get("choices_shown", "")),
                )
                for entry in entries
            ],
        )


def _parse_choices_pool(raw: str) -> list[str]:
    text = (raw or "").strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [" ".join(str(item).split()).strip() for item in parsed if str(item).strip()]


def _serialize_choices_pool(items: list[str]) -> str:
    cleaned = [" ".join(str(item).split()).strip() for item in items if str(item).strip()]
    return json.dumps(cleaned, ensure_ascii=False)


def _row_to_quiz_question(row: sqlite3.Row) -> QuizQuestionRecord:
    return QuizQuestionRecord(
        id=int(row["id"]),
        card_id=int(row["card_id"]),
        question_type=str(row["question_type"]),
        prompt_text=str(row["prompt_text"] or ""),
        example_sentence=str(row["example_sentence"] or ""),
        choices_pool=_parse_choices_pool(str(row["choices_pool"] or "")),
        correct_english=str(row["correct_english"] or ""),
        status=str(row["status"] or "active"),
        model_id=str(row["model_id"] or ""),
        prompt_version=str(row["prompt_version"] or "v1"),
        created_at=str(row["created_at"] or ""),
        updated_at=str(row["updated_at"] or ""),
    )


def upsert_quiz_question(
    *,
    card_id: int,
    question_type: str,
    prompt_text: str,
    example_sentence: str,
    choices_pool: list[str],
    correct_english: str,
    status: str = "active",
    model_id: str = "",
    prompt_version: str = "v1",
) -> int:
    payload = _serialize_choices_pool(choices_pool)
    with connection() as conn:
        conn.execute(
            """
            INSERT INTO quiz_questions (
                card_id, question_type, prompt_text, example_sentence,
                choices_pool, correct_english, status, model_id, prompt_version,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(card_id, question_type) DO UPDATE SET
                prompt_text = excluded.prompt_text,
                example_sentence = excluded.example_sentence,
                choices_pool = excluded.choices_pool,
                correct_english = excluded.correct_english,
                status = excluded.status,
                model_id = excluded.model_id,
                prompt_version = excluded.prompt_version,
                updated_at = datetime('now')
            """,
            (
                card_id,
                question_type,
                prompt_text.strip(),
                example_sentence.strip(),
                payload,
                correct_english.strip(),
                status,
                model_id,
                prompt_version,
            ),
        )
        row = conn.execute(
            """
            SELECT id FROM quiz_questions
            WHERE card_id = ? AND question_type = ?
            """,
            (card_id, question_type),
        ).fetchone()
    return int(row["id"]) if row else 0


def get_quiz_question(card_id: int, question_type: str) -> QuizQuestionRecord | None:
    with connection() as conn:
        row = conn.execute(
            """
            SELECT id, card_id, question_type, prompt_text, example_sentence,
                   choices_pool, correct_english, status, model_id, prompt_version,
                   created_at, updated_at
            FROM quiz_questions
            WHERE card_id = ? AND question_type = ?
            """,
            (card_id, question_type),
        ).fetchone()
    return _row_to_quiz_question(row) if row else None


def list_quiz_questions_for_cards(
    card_ids: list[int],
    *,
    status: str = "active",
) -> list[QuizQuestionRecord]:
    if not card_ids:
        return []
    placeholders = ",".join("?" for _ in card_ids)
    params: list[object] = list(card_ids)
    query = f"""
        SELECT id, card_id, question_type, prompt_text, example_sentence,
               choices_pool, correct_english, status, model_id, prompt_version,
               created_at, updated_at
        FROM quiz_questions
        WHERE card_id IN ({placeholders})
    """
    if status:
        query += " AND status = ?"
        params.append(status)
    with connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_quiz_question(row) for row in rows]


def count_active_quiz_questions(card_id: int) -> int:
    with connection() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS cnt FROM quiz_questions
            WHERE card_id = ? AND status = 'active'
            """,
            (card_id,),
        ).fetchone()
    return int(row["cnt"]) if row else 0


def card_has_full_quiz_coverage(card_id: int) -> bool:
    return count_active_quiz_questions(card_id) >= len(QUIZ_QUESTION_TYPES)


def delete_quiz_questions_for_card(card_id: int) -> None:
    with connection() as conn:
        conn.execute("DELETE FROM quiz_questions WHERE card_id = ?", (card_id,))


def list_recent_quiz_question_types(card_id: int, *, limit: int = 10) -> list[str]:
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT question_type FROM quiz_logs
            WHERE card_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (card_id, max(1, limit)),
        ).fetchall()
    return [str(row["question_type"]) for row in rows]


def get_quiz_coverage(deck_id: int) -> QuizCoverageStats:
    from quicklingo.config.loader import resolve_learning_direction
    from quicklingo.learning.quiz.eligibility import is_quiz_eligible
    from quicklingo.learning.quiz.normalize import card_to_quiz_word

    deck = get_deck(deck_id)
    if deck is None:
        return QuizCoverageStats(eligible=0, ready=0, missing_any=0, missing_by_type={})

    kind = resolve_learning_direction(deck.direction)
    if kind not in ("ua-en", "en-ua"):
        return QuizCoverageStats(eligible=0, ready=0, missing_any=0, missing_by_type={})

    eligible_ids: set[int] = set()
    ready = 0
    missing_by_type = {qtype: 0 for qtype in QUIZ_QUESTION_TYPES}

    for card in list_cards(deck_id):
        word = card_to_quiz_word(card, deck.direction)
        if not is_quiz_eligible(card, word):
            continue
        eligible_ids.add(card.id)
        active_types: set[str] = set()
        with connection() as conn:
            rows = conn.execute(
                """
                SELECT question_type FROM quiz_questions
                WHERE card_id = ? AND status = 'active'
                """,
                (card.id,),
            ).fetchall()
        active_types = {str(row["question_type"]) for row in rows}
        if len(active_types) >= len(QUIZ_QUESTION_TYPES):
            ready += 1
        else:
            for qtype in QUIZ_QUESTION_TYPES:
                if qtype not in active_types:
                    missing_by_type[qtype] += 1

    eligible = len(eligible_ids)
    return QuizCoverageStats(
        eligible=eligible,
        ready=ready,
        missing_any=max(0, eligible - ready),
        missing_by_type=missing_by_type,
    )


def count_failed_quiz_questions_for_deck(deck_id: int) -> int:
    with connection() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM quiz_questions qq
            INNER JOIN learning_cards c ON c.id = qq.card_id
            WHERE c.deck_id = ? AND qq.status = 'failed'
            """,
            (deck_id,),
        ).fetchone()
    return int(row["cnt"]) if row else 0


def get_global_quiz_coverage() -> GlobalQuizCoverageStats:
    from quicklingo.config.loader import resolve_learning_direction

    decks = list_decks()
    quiz_decks = [
        deck
        for deck in decks
        if resolve_learning_direction(deck.direction) in ("ua-en", "en-ua")
    ]
    complete = 0
    for deck in quiz_decks:
        stats = get_quiz_coverage(deck.id)
        if stats.eligible == 0 or stats.ready >= stats.eligible:
            complete += 1
    total = len(quiz_decks)
    return GlobalQuizCoverageStats(
        decks_total=total,
        decks_complete=complete,
        decks_incomplete=max(0, total - complete),
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
    keys = row.keys()
    return LearningDeck(
        id=row["id"],
        name=row["name"],
        tag=row["tag"],
        direction=row["direction"],
        created_at=row["created_at"],
        analysis_summary=row["analysis_summary"] or "",
        source=row["source"] if "source" in keys else "corpus",
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
        quiz_distractors=row["quiz_distractors"] if "quiz_distractors" in keys else "",
    )


def list_quiz_english_words(
    *,
    pos_prefix: str | None = None,
    exclude: set[str] | None = None,
) -> list[str]:
    from quicklingo.config.loader import resolve_learning_direction
    from quicklingo.learning.card_prompt import hint_pos_matches
    from quicklingo.learning.review_queue import english_side_text

    exclude_lower = {word.lower() for word in (exclude or set())}
    seen: set[str] = set()
    results: list[str] = []
    for deck in list_decks():
        if resolve_learning_direction(deck.direction) not in ("ua-en", "en-ua"):
            continue
        for card in list_cards(deck.id):
            english = english_side_text(card, deck.direction).strip()
            key = english.lower()
            if not english or key in exclude_lower or key in seen:
                continue
            if pos_prefix and not hint_pos_matches(card.hint, pos_prefix):
                continue
            seen.add(key)
            results.append(english)
    return results
