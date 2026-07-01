from __future__ import annotations

import sqlite3

from quicklingo.db.connection import connection, get_connection


def init_db() -> None:
    with connection() as conn:
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='translations'"
        ).fetchone()
        if row is None:
            _create_table(conn)
        elif row[0] and "CHECK" in row[0].upper():
            _migrate_remove_direction_check(conn)
        _migrate_columns(conn)
        _setup_tag_tables(conn)
        _setup_fts(conn)
        _ensure_indexes(conn)
    from quicklingo.db.learning import init_learning_tables

    init_learning_tables()


def _create_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS translations (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            direction   TEXT NOT NULL,
            source_text TEXT NOT NULL,
            result_text TEXT NOT NULL,
            model       TEXT NOT NULL,
            profile_id  TEXT NOT NULL DEFAULT '',
            content_hash TEXT NOT NULL DEFAULT '',
            is_starred  INTEGER NOT NULL DEFAULT 0
        )
        """
    )


def _migrate_remove_direction_check(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE translations_new (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            direction   TEXT NOT NULL,
            source_text TEXT NOT NULL,
            result_text TEXT NOT NULL,
            model       TEXT NOT NULL,
            profile_id  TEXT NOT NULL DEFAULT '',
            content_hash TEXT NOT NULL DEFAULT '',
            is_starred  INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    conn.execute(
        """
        INSERT INTO translations_new
            (id, created_at, direction, source_text, result_text, model)
        SELECT id, created_at, direction, source_text, result_text, model
        FROM translations
        """
    )
    conn.execute("DROP TABLE translations")
    conn.execute("ALTER TABLE translations_new RENAME TO translations")


def _column_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("PRAGMA table_info(translations)").fetchall()
    return {row["name"] for row in rows}


def _migrate_columns(conn: sqlite3.Connection) -> None:
    cols = _column_names(conn)
    if "profile_id" not in cols:
        conn.execute(
            "ALTER TABLE translations ADD COLUMN profile_id TEXT NOT NULL DEFAULT ''"
        )
    if "content_hash" not in cols:
        conn.execute(
            "ALTER TABLE translations ADD COLUMN content_hash TEXT NOT NULL DEFAULT ''"
        )
    if "is_starred" not in cols:
        conn.execute(
            "ALTER TABLE translations ADD COLUMN is_starred INTEGER NOT NULL DEFAULT 0"
        )
    if "tags" not in cols:
        conn.execute(
            "ALTER TABLE translations ADD COLUMN tags TEXT NOT NULL DEFAULT ''"
        )


def _setup_tag_tables(conn: sqlite3.Connection) -> None:
    from quicklingo.db.history_tags import (
        cleanup_orphan_tags,
        init_tag_tables,
        migrate_legacy_tags_column,
    )

    init_tag_tables(conn)
    migrate_legacy_tags_column(conn)
    cleanup_orphan_tags(conn)


def _ensure_indexes(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_translations_cache
        ON translations(content_hash, direction, created_at DESC)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_translations_direction_id
        ON translations(direction, id DESC)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_translations_created_at
        ON translations(created_at)
        """
    )


def _setup_fts(conn: sqlite3.Connection) -> None:
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='translations_fts'"
    ).fetchone()
    if exists:
        return
    conn.execute(
        """
        CREATE VIRTUAL TABLE translations_fts USING fts5(
            source_text,
            result_text,
            content='translations',
            content_rowid='id'
        )
        """
    )
    conn.execute(
        """
        INSERT INTO translations_fts(rowid, source_text, result_text)
        SELECT id, source_text, result_text FROM translations
        """
    )
    conn.execute(
        """
        CREATE TRIGGER translations_ai AFTER INSERT ON translations BEGIN
            INSERT INTO translations_fts(rowid, source_text, result_text)
            VALUES (new.id, new.source_text, new.result_text);
        END
        """
    )
    conn.execute(
        """
        CREATE TRIGGER translations_ad AFTER DELETE ON translations BEGIN
            INSERT INTO translations_fts(translations_fts, rowid, source_text, result_text)
            VALUES ('delete', old.id, old.source_text, old.result_text);
        END
        """
    )
    conn.execute(
        """
        CREATE TRIGGER translations_au AFTER UPDATE ON translations BEGIN
            INSERT INTO translations_fts(translations_fts, rowid, source_text, result_text)
            VALUES ('delete', old.id, old.source_text, old.result_text);
            INSERT INTO translations_fts(rowid, source_text, result_text)
            VALUES (new.id, new.source_text, new.result_text);
        END
        """
    )
