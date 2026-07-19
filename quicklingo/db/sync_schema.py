from __future__ import annotations

import sqlite3
import uuid

from quicklingo.db.connection import connection


def init_sync_schema() -> None:
    with connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sync_tombstones (
                entity_type TEXT NOT NULL,
                entity_key TEXT NOT NULL,
                deleted_at TEXT NOT NULL,
                device_id TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (entity_type, entity_key)
            )
            """
        )
        _migrate_translation_columns(conn)
        _migrate_deck_columns(conn)
        _migrate_card_columns(conn)


def _migrate_translation_columns(conn: sqlite3.Connection) -> None:
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(translations)").fetchall()}
    if "updated_at" not in cols:
        conn.execute(
            "ALTER TABLE translations ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''"
        )
        conn.execute(
            """
            UPDATE translations
            SET updated_at = COALESCE(NULLIF(created_at, ''), datetime('now'))
            WHERE updated_at = ''
            """
        )


def _migrate_deck_columns(conn: sqlite3.Connection) -> None:
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(learning_decks)").fetchall()}
    if "updated_at" not in cols:
        conn.execute(
            "ALTER TABLE learning_decks ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''"
        )
        conn.execute(
            """
            UPDATE learning_decks
            SET updated_at = COALESCE(NULLIF(created_at, ''), datetime('now'))
            WHERE updated_at = ''
            """
        )


def _migrate_card_columns(conn: sqlite3.Connection) -> None:
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(learning_cards)").fetchall()}
    if "sync_id" not in cols:
        conn.execute("ALTER TABLE learning_cards ADD COLUMN sync_id TEXT NOT NULL DEFAULT ''")
    if "content_updated_at" not in cols:
        conn.execute(
            "ALTER TABLE learning_cards ADD COLUMN content_updated_at TEXT NOT NULL DEFAULT ''"
        )
    if "srs_updated_at" not in cols:
        conn.execute(
            "ALTER TABLE learning_cards ADD COLUMN srs_updated_at TEXT NOT NULL DEFAULT ''"
        )
    rows = conn.execute(
        "SELECT id FROM learning_cards WHERE sync_id = '' OR sync_id IS NULL"
    ).fetchall()
    for row in rows:
        conn.execute(
            "UPDATE learning_cards SET sync_id = ? WHERE id = ?",
            (str(uuid.uuid4()), int(row["id"])),
        )
    conn.execute(
        """
        UPDATE learning_cards
        SET content_updated_at = datetime('now')
        WHERE content_updated_at = '' OR content_updated_at IS NULL
        """
    )
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_learning_cards_sync_id
        ON learning_cards(sync_id)
        WHERE sync_id != ''
        """
    )


def touch_translation_updated_at(conn: sqlite3.Connection, record_id: int) -> None:
    conn.execute(
        "UPDATE translations SET updated_at = datetime('now') WHERE id = ?",
        (record_id,),
    )


def touch_card_content_updated_at(conn: sqlite3.Connection, card_id: int) -> None:
    conn.execute(
        "UPDATE learning_cards SET content_updated_at = datetime('now') WHERE id = ?",
        (card_id,),
    )


def touch_card_srs_updated_at(conn: sqlite3.Connection, card_id: int) -> None:
    conn.execute(
        "UPDATE learning_cards SET srs_updated_at = datetime('now') WHERE id = ?",
        (card_id,),
    )


def new_card_sync_id() -> str:
    return str(uuid.uuid4())
