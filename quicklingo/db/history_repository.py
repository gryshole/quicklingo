from __future__ import annotations

import csv
import io

from quicklingo.db.connection import connection, get_connection
from quicklingo.db.sync_schema import touch_translation_updated_at
from quicklingo.db.tombstones import record_all_translations_deleted, record_translation_delete
from quicklingo import settings as app_settings
from quicklingo.db.history_analytics import _direction_filter_clause
from quicklingo.db.history_models import (
    TranslationRecord,
    make_content_hash,
    normalize_tag_names,
    row_to_record,
)
from quicklingo.db.history_tags import (
    get_translation_tag_names,
    set_translation_tags,
    tags_subquery_sql,
)


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
    tags: list[str] | None = None,
) -> int:
    _validate_direction(direction)
    if not content_hash:
        content_hash = make_content_hash(source_text, direction, profile_id)
    with connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO translations
                (direction, source_text, result_text, model, profile_id, content_hash, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (direction, source_text, result_text, model, profile_id, content_hash),
        )
        record_id = int(cursor.lastrowid or 0)
        if tags:
            set_translation_tags(conn, record_id, tags)
    return record_id


def find_cached(
    direction: str,
    source_text: str,
    profile_id: str,
    *,
    ttl_days: int,
) -> str | None:
    content_hash = make_content_hash(source_text, direction, profile_id)
    row = get_connection().execute(
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


def _fts_query(text: str) -> str:
    tokens = []
    for token in text.split():
        cleaned = "".join(ch for ch in token if ch.isalnum() or ch in ("_", "-"))
        if cleaned:
            tokens.append(f'"{cleaned}"*')
    return " AND ".join(tokens) if tokens else '""'


def search_records(
    *,
    query: str = "",
    direction: str | None = None,
    model: str | None = None,
    tag: str | None = None,
    untagged_only: bool = False,
    date_from: str | None = None,
    date_to: str | None = None,
    starred_only: bool = False,
    limit: int = 1000,
    learning_kind: bool = False,
) -> list[TranslationRecord]:
    clauses = ["1=1"]
    params: list[object] = []

    if direction:
        dir_clause, dir_params = _direction_filter_clause(
            direction, learning_kind=learning_kind
        )
        if dir_clause:
            clauses.append(dir_clause)
            params.extend(dir_params)

    if model:
        clauses.append("t.model = ?")
        params.append(model)

    if untagged_only:
        clauses.append(
            """
            NOT EXISTS (
                SELECT 1
                FROM translation_tags tt
                WHERE tt.translation_id = t.id
            )
            """
        )
    elif tag:
        clauses.append(
            """
            EXISTS (
                SELECT 1
                FROM translation_tags tt
                JOIN tags tg ON tg.id = tt.tag_id
                WHERE tt.translation_id = t.id
                  AND lower(trim(tg.name)) = lower(trim(?))
            )
            """
        )
        params.append(tag)

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
               t.model, t.profile_id, t.content_hash, t.is_starred,
               COALESCE({tags_subquery_sql()}, '') AS tags
        FROM translations t
        WHERE {' AND '.join(clauses)}
        ORDER BY t.id DESC
        LIMIT ?
    """
    params.append(limit)
    rows = get_connection().execute(sql, params).fetchall()
    return [row_to_record(row) for row in rows]


def get_all(limit: int = 1000) -> list[TranslationRecord]:
    return search_records(limit=limit)


def get_recent_for_context(
    direction: str,
    *,
    limit: int = 3,
    exclude_source: str | None = None,
) -> list[tuple[str, str]]:
    fetch_limit = max(1, limit) + 5
    rows = get_connection().execute(
        """
        SELECT source_text, result_text
        FROM translations
        WHERE direction = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (direction, fetch_limit),
    ).fetchall()
    pairs: list[tuple[str, str]] = []
    normalized_exclude = " ".join(exclude_source.split()) if exclude_source else None
    for row in rows:
        source = row["source_text"].strip()
        if not source:
            continue
        if normalized_exclude and " ".join(source.split()) == normalized_exclude:
            continue
        pairs.append((source, row["result_text"].strip()))
        if len(pairs) >= limit:
            break
    return pairs


def clear_all() -> None:
    with connection() as conn:
        record_all_translations_deleted(device_id=app_settings.get_sync_device_id(), conn=conn)
        conn.execute("DELETE FROM translations")


def delete_by_id(record_id: int) -> bool:
    with connection() as conn:
        row = conn.execute(
            "SELECT content_hash, direction, profile_id FROM translations WHERE id = ?",
            (record_id,),
        ).fetchone()
        if row:
            record_translation_delete(
                content_hash=str(row["content_hash"] or ""),
                direction=str(row["direction"] or ""),
                profile_id=str(row["profile_id"] or ""),
                device_id=app_settings.get_sync_device_id(),
                conn=conn,
            )
        cursor = conn.execute("DELETE FROM translations WHERE id = ?", (record_id,))
    return cursor.rowcount > 0


def get_source_text(record_id: int) -> str:
    with connection() as conn:
        row = conn.execute(
            "SELECT source_text FROM translations WHERE id = ?",
            (record_id,),
        ).fetchone()
    if row is None:
        return ""
    return str(row["source_text"] or "").strip()


def set_starred(record_id: int, starred: bool) -> bool:
    with connection() as conn:
        cursor = conn.execute(
            "UPDATE translations SET is_starred = ?, updated_at = datetime('now') WHERE id = ?",
            (1 if starred else 0, record_id),
        )
    return cursor.rowcount > 0


def set_tags(record_id: int, tags: list[str]) -> bool:
    with connection() as conn:
        row = conn.execute(
            "SELECT id FROM translations WHERE id = ?",
            (record_id,),
        ).fetchone()
        if row is None:
            return False
        set_translation_tags(conn, record_id, tags)
        touch_translation_updated_at(conn, record_id)
    return True


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
    with connection() as conn:
        placeholders = ",".join("?" * len(record_ids))
        rows = conn.execute(
            f"SELECT id FROM translations WHERE id IN ({placeholders})",
            record_ids,
        ).fetchall()
        for row in rows:
            record_id = int(row["id"])
            if replace is not None:
                new_tags = normalize_tag_names(replace)
            else:
                current = get_translation_tag_names(conn, record_id)
                if add_tags:
                    current = normalize_tag_names(current + add_tags)
                if remove_tags:
                    current = [
                        tag for tag in current if tag.lower() not in remove_tags
                    ]
                new_tags = current
            before = get_translation_tag_names(conn, record_id)
            if before == new_tags:
                continue
            set_translation_tags(conn, record_id, new_tags)
            touch_translation_updated_at(conn, record_id)
            updated += 1
    return updated


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
