import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TranslationRecord:
    id: int
    created_at: str
    direction: str
    source_text: str
    result_text: str
    model: str


def _db_path() -> Path:
    from quicklingo.paths import user_data_dir

    return user_data_dir() / "history.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def _create_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS translations (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            direction   TEXT NOT NULL,
            source_text TEXT NOT NULL,
            result_text TEXT NOT NULL,
            model       TEXT NOT NULL
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
            model       TEXT NOT NULL
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


def init_db() -> None:
    # Future: this table will feed Anki deck generation and word frequency stats.
    with _connect() as conn:
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='translations'"
        ).fetchone()
        if row is None:
            _create_table(conn)
        elif row[0] and "CHECK" in row[0].upper():
            _migrate_remove_direction_check(conn)


def _validate_direction(direction: str) -> None:
    from quicklingo.config.loader import get_direction

    if get_direction(direction) is None:
        raise ValueError(f"Unknown translation direction: {direction}")


def save_translation(
    direction: str,
    source_text: str,
    result_text: str,
    model: str,
) -> int:
    _validate_direction(direction)
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO translations (direction, source_text, result_text, model)
            VALUES (?, ?, ?, ?)
            """,
            (direction, source_text, result_text, model),
        )
        return cursor.lastrowid or 0


def get_recent(limit: int = 50) -> list[TranslationRecord]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, created_at, direction, source_text, result_text, model
            FROM translations
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [_row_to_record(row) for row in rows]


def get_all(limit: int = 1000) -> list[TranslationRecord]:
    return get_recent(limit)


def get_stats() -> dict[str, int]:
    with _connect() as conn:
        total = conn.execute("SELECT COUNT(*) FROM translations").fetchone()[0]
        ua_en = conn.execute(
            "SELECT COUNT(*) FROM translations WHERE direction = 'ua-en'"
        ).fetchone()[0]
        en_ua = conn.execute(
            "SELECT COUNT(*) FROM translations WHERE direction = 'en-ua'"
        ).fetchone()[0]
    return {"total": total, "ua_en": ua_en, "en_ua": en_ua}


def clear_all() -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM translations")


def delete_by_id(record_id: int) -> bool:
    with _connect() as conn:
        cursor = conn.execute("DELETE FROM translations WHERE id = ?", (record_id,))
        return cursor.rowcount > 0


def _row_to_record(row: sqlite3.Row) -> TranslationRecord:
    return TranslationRecord(
        id=row["id"],
        created_at=row["created_at"],
        direction=row["direction"],
        source_text=row["source_text"],
        result_text=row["result_text"],
        model=row["model"],
    )
