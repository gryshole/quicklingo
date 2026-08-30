from __future__ import annotations

from quicklingo import settings as app_settings
from quicklingo.db.connection import connection, fetch_all, in_placeholders, scalar_int
from quicklingo.db.learning_models import (
    QuizCoverageStats,
    QuizQuestionRecord,
    QuizQuestionRow,
    QUIZ_QUESTION_TYPES,
    _parse_choices_pool,
    _row_to_quiz_question,
    _row_to_quiz_question_row,
    _serialize_choices_pool,
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
    placeholders = in_placeholders(len(card_ids))
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


_QUIZ_QUESTION_JOIN_SELECT = """
    SELECT q.id, q.card_id, q.question_type, q.prompt_text, q.example_sentence,
           q.choices_pool, q.correct_english, q.status, q.model_id, q.prompt_version,
           q.created_at, q.updated_at,
           c.front AS card_front, c.back AS card_back, c.deck_id AS deck_id,
           d.name AS deck_name
    FROM quiz_questions q
    JOIN learning_cards c ON c.id = q.card_id
    JOIN learning_decks d ON d.id = c.deck_id
"""


def list_quiz_questions(
    deck_id: int,
    *,
    question_type: str | None = None,
    status: str | None = None,
    search: str | None = None,
) -> list[QuizQuestionRow]:
    query = _QUIZ_QUESTION_JOIN_SELECT + " WHERE c.deck_id = ?"
    params: list[object] = [deck_id]
    if question_type:
        query += " AND q.question_type = ?"
        params.append(question_type)
    if status and status != "all":
        query += " AND q.status = ?"
        params.append(status)
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        query += " AND (q.prompt_text LIKE ? OR q.correct_english LIKE ? OR c.front LIKE ?)"
        params.extend([pattern, pattern, pattern])
    query += " ORDER BY q.updated_at DESC, q.id DESC"
    with connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_quiz_question_row(row) for row in rows]


def get_quiz_question_by_id(question_id: int) -> QuizQuestionRow | None:
    query = _QUIZ_QUESTION_JOIN_SELECT + " WHERE q.id = ?"
    with connection() as conn:
        row = conn.execute(query, (question_id,)).fetchone()
    return _row_to_quiz_question_row(row) if row else None


def count_active_quiz_questions(card_id: int) -> int:
    return scalar_int(
        """
        SELECT COUNT(*) AS cnt FROM quiz_questions
        WHERE card_id = ? AND status = 'active'
        """,
        (card_id,),
    )


def card_has_full_quiz_coverage(card_id: int) -> bool:
    return count_active_quiz_questions(card_id) >= len(QUIZ_QUESTION_TYPES)


def delete_quiz_questions_for_card(card_id: int) -> None:
    from quicklingo import settings as app_settings
    from quicklingo.db.tombstones import record_quiz_question_delete

    with connection() as conn:
        card = conn.execute(
            "SELECT sync_id FROM learning_cards WHERE id = ?",
            (card_id,),
        ).fetchone()
        sync_id = str(card["sync_id"] or "") if card else ""
        questions = conn.execute(
            "SELECT question_type FROM quiz_questions WHERE card_id = ?",
            (card_id,),
        ).fetchall()
        device_id = app_settings.get_sync_device_id()
        for question in questions:
            record_quiz_question_delete(
                card_sync_id=sync_id,
                question_type=str(question["question_type"]),
                device_id=device_id,
                conn=conn,
            )
        conn.execute("DELETE FROM quiz_questions WHERE card_id = ?", (card_id,))


def list_recent_quiz_question_types(card_id: int, *, limit: int = 10) -> list[str]:
    rows = fetch_all(
        """
        SELECT question_type FROM quiz_logs
        WHERE card_id = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (card_id, max(1, limit)),
    )
    return [str(row["question_type"]) for row in rows]
