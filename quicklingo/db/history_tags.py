from __future__ import annotations

import sqlite3

from quicklingo.db.history_models import normalize_tag_names, parse_tags
from quicklingo.db.sync_schema import touch_translation_updated_at


def cleanup_orphan_tags(conn: sqlite3.Connection) -> None:
    """Remove tag links to deleted translations and unused tag rows."""
    conn.execute(
        """
        DELETE FROM translation_tags
        WHERE translation_id NOT IN (SELECT id FROM translations)
        """
    )
    conn.execute(
        """
        DELETE FROM tags
        WHERE id NOT IN (SELECT DISTINCT tag_id FROM translation_tags)
        """
    )


def init_tag_tables(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tags (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_tags_name_lower
        ON tags(lower(trim(name)))
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS translation_tags (
            translation_id INTEGER NOT NULL,
            tag_id         INTEGER NOT NULL,
            PRIMARY KEY (translation_id, tag_id),
            FOREIGN KEY (translation_id) REFERENCES translations(id) ON DELETE CASCADE,
            FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_translation_tags_tag
        ON translation_tags(tag_id)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_translation_tags_translation
        ON translation_tags(translation_id)
        """
    )


def migrate_legacy_tags_column(conn: sqlite3.Connection) -> None:
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(translations)").fetchall()}
    if "tags" not in cols:
        return
    rows = conn.execute(
        "SELECT id, tags FROM translations WHERE tags != ''"
    ).fetchall()
    for row in rows:
        tag_names = parse_tags(row["tags"])
        if tag_names:
            set_translation_tags(conn, int(row["id"]), tag_names)
    conn.execute("UPDATE translations SET tags = '' WHERE tags != ''")


def get_or_create_tag_id(conn: sqlite3.Connection, name: str) -> int:
    cleaned = name.strip()
    if not cleaned:
        raise ValueError("empty tag name")
    row = conn.execute(
        "SELECT id FROM tags WHERE lower(trim(name)) = lower(?)",
        (cleaned,),
    ).fetchone()
    if row:
        return int(row["id"])
    cursor = conn.execute("INSERT INTO tags (name) VALUES (?)", (cleaned,))
    return int(cursor.lastrowid or 0)


def get_translation_tag_names(conn: sqlite3.Connection, translation_id: int) -> list[str]:
    rows = conn.execute(
        """
        SELECT tg.name
        FROM translation_tags tt
        JOIN tags tg ON tg.id = tt.tag_id
        WHERE tt.translation_id = ?
        ORDER BY lower(tg.name), tg.name
        """,
        (translation_id,),
    ).fetchall()
    return [str(row["name"]) for row in rows]


def set_translation_tags(
    conn: sqlite3.Connection,
    translation_id: int,
    tag_names: list[str],
) -> None:
    normalized = normalize_tag_names(tag_names)
    conn.execute(
        "DELETE FROM translation_tags WHERE translation_id = ?",
        (translation_id,),
    )
    for name in normalized:
        tag_id = get_or_create_tag_id(conn, name)
        conn.execute(
            """
            INSERT OR IGNORE INTO translation_tags (translation_id, tag_id)
            VALUES (?, ?)
            """,
            (translation_id, tag_id),
        )
    conn.execute(
        "UPDATE translations SET tags = '' WHERE id = ?",
        (translation_id,),
    )


def apply_translation_tag_changes(
    conn: sqlite3.Connection,
    translation_id: int,
    *,
    add: list[str] | None = None,
    remove: list[str] | None = None,
) -> bool:
    """Add/remove history tags on one translation. Returns True if tags changed."""
    add_tags = add or []
    remove_set = {tag.strip().lower() for tag in remove or [] if tag.strip()}
    current = get_translation_tag_names(conn, translation_id)
    if add_tags:
        current = normalize_tag_names(current + add_tags)
    if remove_set:
        current = [tag for tag in current if tag.lower() not in remove_set]
    new_tags = normalize_tag_names(current)
    if new_tags == get_translation_tag_names(conn, translation_id):
        return False
    set_translation_tags(conn, translation_id, new_tags)
    touch_translation_updated_at(conn, translation_id)
    return True


def tags_subquery_sql() -> str:
    return """
        (
            SELECT GROUP_CONCAT(tg.name, ', ')
            FROM translation_tags tt
            JOIN tags tg ON tg.id = tt.tag_id
            WHERE tt.translation_id = t.id
        )
    """
