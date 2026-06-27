import csv
import hashlib
import io
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
    profile_id: str = ""
    content_hash: str = ""
    is_starred: bool = False
    tags: str = ""


def parse_tags(raw: str) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def format_tags(tags: list[str]) -> str:
    cleaned = []
    seen: set[str] = set()
    for tag in tags:
        value = tag.strip()
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(value)
    return ", ".join(cleaned)


def _db_path() -> Path:
    from quicklingo.paths import user_data_dir

    return user_data_dir() / "history.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def make_content_hash(source_text: str, direction: str, profile_id: str) -> str:
    normalized = " ".join(source_text.split())
    payload = f"{direction}\0{profile_id}\0{normalized}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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


def init_db() -> None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='translations'"
        ).fetchone()
        if row is None:
            _create_table(conn)
        elif row[0] and "CHECK" in row[0].upper():
            _migrate_remove_direction_check(conn)
        _migrate_columns(conn)
        _setup_fts(conn)
    from quicklingo.db.learning import init_learning_tables

    init_learning_tables()


def _validate_direction(direction: str) -> None:
    from quicklingo.config.loader import get_direction

    if get_direction(direction) is None:
        raise ValueError(f"Unknown translation direction: {direction}")


def save_translation(
    direction: str,
    source_text: str,
    result_text: str,
    model: str,
    *,
    profile_id: str = "",
    content_hash: str = "",
) -> int:
    _validate_direction(direction)
    if not content_hash:
        content_hash = make_content_hash(source_text, direction, profile_id)
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO translations
                (direction, source_text, result_text, model, profile_id, content_hash)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (direction, source_text, result_text, model, profile_id, content_hash),
        )
        return cursor.lastrowid or 0


def find_cached(
    direction: str,
    source_text: str,
    profile_id: str,
    *,
    ttl_days: int,
) -> str | None:
    content_hash = make_content_hash(source_text, direction, profile_id)
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT result_text
            FROM translations
            WHERE content_hash = ?
              AND direction = ?
              AND created_at >= datetime('now', ?)
            ORDER BY id DESC
            LIMIT 1
            """,
            (content_hash, direction, f"-{max(1, ttl_days)} days"),
        ).fetchone()
    return row["result_text"] if row else None


def search_records(
    *,
    query: str = "",
    direction: str | None = None,
    model: str | None = None,
    tag: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    starred_only: bool = False,
    limit: int = 1000,
) -> list[TranslationRecord]:
    clauses = ["1=1"]
    params: list[object] = []

    if direction:
        clauses.append("t.direction = ?")
        params.append(direction)

    if model:
        clauses.append("t.model = ?")
        params.append(model)

    if tag:
        clauses.append(
            "(t.tags = ? OR t.tags LIKE ? || ',%' OR t.tags LIKE '%,' || ? OR t.tags LIKE '%,' || ? || ',%')"
        )
        params.extend([tag, tag, tag, tag])

    if date_from:
        clauses.append("date(t.created_at) >= date(?)")
        params.append(date_from)

    if date_to:
        clauses.append("date(t.created_at) <= date(?)")
        params.append(date_to)

    if starred_only:
        clauses.append("t.is_starred = 1")

    if query.strip():
        clauses.append(
            "t.id IN (SELECT rowid FROM translations_fts WHERE translations_fts MATCH ?)"
        )
        params.append(_fts_query(query.strip()))

    sql = f"""
        SELECT t.id, t.created_at, t.direction, t.source_text, t.result_text,
               t.model, t.profile_id, t.content_hash, t.is_starred, t.tags
        FROM translations t
        WHERE {' AND '.join(clauses)}
        ORDER BY t.id DESC
        LIMIT ?
    """
    params.append(limit)

    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_record(row) for row in rows]


def _fts_query(text: str) -> str:
    tokens = []
    for token in text.split():
        cleaned = "".join(ch for ch in token if ch.isalnum() or ch in ("_", "-"))
        if cleaned:
            tokens.append(f'"{cleaned}"*')
    return " AND ".join(tokens) if tokens else '""'


def get_recent(limit: int = 50) -> list[TranslationRecord]:
    return search_records(limit=limit)


def get_all(limit: int = 1000) -> list[TranslationRecord]:
    return search_records(limit=limit)


def get_stats() -> dict[str, int]:
    with _connect() as conn:
        total = conn.execute("SELECT COUNT(*) FROM translations").fetchone()[0]
        by_direction = conn.execute(
            """
            SELECT direction, COUNT(*) AS cnt
            FROM translations
            GROUP BY direction
            ORDER BY direction
            """
        ).fetchall()
    stats = {"total": total, "ua_en": 0, "en_ua": 0}
    for row in by_direction:
        stats[row["direction"]] = row["cnt"]
        if row["direction"] == "ua-en":
            stats["ua_en"] = row["cnt"]
        elif row["direction"] == "en-ua":
            stats["en_ua"] = row["cnt"]
    return stats


def get_direction_counts() -> dict[str, int]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT direction, COUNT(*) AS cnt
            FROM translations
            GROUP BY direction
            ORDER BY direction
            """
        ).fetchall()
    return {row["direction"]: row["cnt"] for row in rows}


def get_distinct_models() -> list[str]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT model
            FROM translations
            WHERE model != ''
            ORDER BY model
            """
        ).fetchall()
    return [row["model"] for row in rows]


def get_daily_counts(days: int = 30) -> list[tuple[str, int]]:
    from datetime import date, timedelta

    days = max(1, days)
    end = date.today()
    start = end - timedelta(days=days - 1)
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT date(created_at) AS day, COUNT(*) AS cnt
            FROM translations
            WHERE date(created_at) >= ? AND date(created_at) <= ?
            GROUP BY date(created_at)
            """,
            (start.isoformat(), end.isoformat()),
        ).fetchall()
    by_day = {row["day"]: int(row["cnt"]) for row in rows}
    result: list[tuple[str, int]] = []
    cursor = start
    while cursor <= end:
        key = cursor.isoformat()
        result.append((key, by_day.get(key, 0)))
        cursor += timedelta(days=1)
    return result


def get_model_counts() -> list[tuple[str, int]]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT model, COUNT(*) AS cnt
            FROM translations
            WHERE model != ''
            GROUP BY model
            ORDER BY cnt DESC, model ASC
            """
        ).fetchall()
    return [(row["model"], int(row["cnt"])) for row in rows]


def get_recent_for_context(
    direction: str,
    *,
    limit: int = 3,
    exclude_source: str | None = None,
) -> list[tuple[str, str]]:
    records = search_records(direction=direction, limit=max(1, limit) + 5)
    pairs: list[tuple[str, str]] = []
    normalized_exclude = " ".join(exclude_source.split()) if exclude_source else None
    for record in records:
        source = record.source_text.strip()
        if not source:
            continue
        if normalized_exclude and " ".join(source.split()) == normalized_exclude:
            continue
        pairs.append((source, record.result_text.strip()))
        if len(pairs) >= limit:
            break
    return pairs


def clear_all() -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM translations")


def delete_by_id(record_id: int) -> bool:
    with _connect() as conn:
        cursor = conn.execute("DELETE FROM translations WHERE id = ?", (record_id,))
        return cursor.rowcount > 0


def set_starred(record_id: int, starred: bool) -> bool:
    with _connect() as conn:
        cursor = conn.execute(
            "UPDATE translations SET is_starred = ? WHERE id = ?",
            (1 if starred else 0, record_id),
        )
        return cursor.rowcount > 0


def set_tags(record_id: int, tags: list[str]) -> bool:
    value = format_tags(tags)
    with _connect() as conn:
        cursor = conn.execute(
            "UPDATE translations SET tags = ? WHERE id = ?",
            (value, record_id),
        )
        return cursor.rowcount > 0


def bulk_apply_tags(
    record_ids: list[int],
    *,
    add: list[str] | None = None,
    remove: list[str] | None = None,
    replace: list[str] | None = None,
) -> int:
    if not record_ids:
        return 0
    add_tags = add or []
    remove_tags = {tag.strip().lower() for tag in remove or [] if tag.strip()}
    updated = 0
    with _connect() as conn:
        for record_id in record_ids:
            row = conn.execute(
                "SELECT tags FROM translations WHERE id = ?",
                (record_id,),
            ).fetchone()
            if not row:
                continue
            if replace is not None:
                new_tags = format_tags(replace)
            else:
                current = parse_tags(row["tags"])
                if add_tags:
                    current = parse_tags(format_tags(current + add_tags))
                if remove_tags:
                    current = [tag for tag in current if tag.lower() not in remove_tags]
                new_tags = format_tags(current)
            if new_tags == (row["tags"] or ""):
                continue
            conn.execute(
                "UPDATE translations SET tags = ? WHERE id = ?",
                (new_tags, record_id),
            )
            updated += 1
    return updated


def get_distinct_tags() -> list[str]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT tags FROM translations WHERE tags != ''"
        ).fetchall()
    found: set[str] = set()
    result: list[str] = []
    for row in rows:
        for tag in parse_tags(row["tags"]):
            key = tag.lower()
            if key not in found:
                found.add(key)
                result.append(tag)
    return sorted(result, key=str.lower)


def export_csv(records: list[TranslationRecord] | None = None) -> str:
    rows = records if records is not None else get_all()
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(
        [
            "id",
            "created_at",
            "direction",
            "source_text",
            "result_text",
            "model",
            "profile_id",
            "is_starred",
            "tags",
        ]
    )
    for record in rows:
        writer.writerow(
            [
                record.id,
                record.created_at,
                record.direction,
                record.source_text,
                record.result_text,
                record.model,
                record.profile_id,
                "1" if record.is_starred else "0",
                record.tags,
            ]
        )
    return buffer.getvalue()


def _row_to_record(row: sqlite3.Row) -> TranslationRecord:
    keys = row.keys()
    return TranslationRecord(
        id=row["id"],
        created_at=row["created_at"],
        direction=row["direction"],
        source_text=row["source_text"],
        result_text=row["result_text"],
        model=row["model"],
        profile_id=row["profile_id"] if "profile_id" in keys else "",
        content_hash=row["content_hash"] if "content_hash" in keys else "",
        is_starred=bool(row["is_starred"]) if "is_starred" in keys else False,
        tags=row["tags"] if "tags" in keys else "",
    )
