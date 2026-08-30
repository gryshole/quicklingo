from __future__ import annotations

import sqlite3

from quicklingo.db.connection import connection
from quicklingo.db.tombstones import clear_deck_tombstone


def _learning_card_columns(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("PRAGMA table_info(learning_cards)").fetchall()
    return {row["name"] for row in rows}


def _learning_deck_columns(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("PRAGMA table_info(learning_decks)").fetchall()
    return {row["name"] for row in rows}


def _migrate_deck_columns(conn: sqlite3.Connection) -> None:
    cols = _learning_deck_columns(conn)
    if "source" not in cols:
        conn.execute("ALTER TABLE learning_decks ADD COLUMN source TEXT NOT NULL DEFAULT 'corpus'")
    _dedupe_learning_decks(conn)
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_learning_decks_tag_direction
        ON learning_decks(tag, direction)
        """
    )


def _dedupe_learning_decks(conn: sqlite3.Connection) -> None:
    duplicates = conn.execute(
        """
        SELECT tag, direction, COUNT(*) AS cnt
        FROM learning_decks
        GROUP BY tag, direction
        HAVING COUNT(*) > 1
        """
    ).fetchall()
    for row in duplicates:
        tag = str(row["tag"] or "")
        direction = str(row["direction"] or "")
        keep = conn.execute(
            """
            SELECT id FROM learning_decks
            WHERE tag = ? AND direction = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (tag, direction),
        ).fetchone()
        if keep is None:
            continue
        keep_id = int(keep["id"])
        losers = conn.execute(
            """
            SELECT id FROM learning_decks
            WHERE tag = ? AND direction = ? AND id != ?
            """,
            (tag, direction, keep_id),
        ).fetchall()
        for loser in losers:
            loser_id = int(loser["id"])
            conn.execute(
                "UPDATE learning_cards SET deck_id = ? WHERE deck_id = ?",
                (keep_id, loser_id),
            )
            conn.execute("DELETE FROM learning_decks WHERE id = ?", (loser_id,))


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
