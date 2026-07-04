from __future__ import annotations

from datetime import date, timedelta

from quicklingo.config.loader import resolve_learning_direction
from quicklingo.db.connection import get_connection


def get_translation_stats() -> dict[str, int]:
    """Single-query stats: total, ua_en, en_ua, and per-direction keys."""
    conn = get_connection()
    total = conn.execute("SELECT COUNT(*) FROM translations").fetchone()[0]
    by_direction = conn.execute(
        """
        SELECT direction, COUNT(*) AS cnt
        FROM translations
        GROUP BY direction
        ORDER BY direction
        """
    ).fetchall()
    stats: dict[str, int] = {"total": total, "ua_en": 0, "en_ua": 0}
    for row in by_direction:
        stats[row["direction"]] = row["cnt"]
        kind = resolve_learning_direction(row["direction"])
        if kind == "ua-en":
            stats["ua_en"] += row["cnt"]
        elif kind == "en-ua":
            stats["en_ua"] += row["cnt"]
    return stats


def get_stats() -> dict[str, int]:
    return get_translation_stats()


def get_direction_counts() -> dict[str, int]:
    stats = get_translation_stats()
    return {
        key: value
        for key, value in stats.items()
        if key not in ("total", "ua_en", "en_ua")
    }


def get_distinct_models() -> list[str]:
    rows = get_connection().execute(
        """
        SELECT DISTINCT model
        FROM translations
        WHERE model != ''
        ORDER BY model
        """
    ).fetchall()
    return [row["model"] for row in rows]


def get_daily_counts(days: int = 30) -> list[tuple[str, int]]:
    days = max(1, days)
    end = date.today()
    start = end - timedelta(days=days - 1)
    rows = get_connection().execute(
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
    rows = get_connection().execute(
        """
        SELECT model, COUNT(*) AS cnt
        FROM translations
        WHERE model != ''
        GROUP BY model
        ORDER BY cnt DESC, model ASC
        """
    ).fetchall()
    return [(row["model"], int(row["cnt"])) for row in rows]


def get_distinct_tags() -> list[str]:
    rows = get_connection().execute(
        """
        SELECT MIN(tg.name) AS name
        FROM tags tg
        INNER JOIN translation_tags tt ON tt.tag_id = tg.id
        INNER JOIN translations t ON t.id = tt.translation_id
        GROUP BY lower(trim(tg.name))
        ORDER BY lower(trim(tg.name))
        """
    ).fetchall()
    return [str(row["name"]) for row in rows]


def directions_for_learning_kind(direction_id: str) -> list[str]:
    kind = resolve_learning_direction(direction_id)
    ids: set[str] = {kind, direction_id.strip()}
    from quicklingo.config.loader import get_all_directions

    for direction in get_all_directions():
        if resolve_learning_direction(direction.id) == kind:
            ids.add(direction.id)
    rows = get_connection().execute(
        "SELECT DISTINCT direction FROM translations"
    ).fetchall()
    for row in rows:
        stored = str(row["direction"])
        if resolve_learning_direction(stored) == kind:
            ids.add(stored)
    return sorted(ids)


def _direction_filter_clause(
    direction: str | None,
    *,
    learning_kind: bool = False,
) -> tuple[str, list[object]]:
    if not direction:
        return "", []
    if not learning_kind:
        return "t.direction = ?", [direction]
    ids = directions_for_learning_kind(direction)
    if len(ids) == 1:
        return "t.direction = ?", [ids[0]]
    placeholders = ",".join("?" * len(ids))
    return f"t.direction IN ({placeholders})", list(ids)


def count_corpus_records(*, direction: str, learning_kind: bool = True) -> int:
    clause, params = _direction_filter_clause(direction, learning_kind=learning_kind)
    if not clause:
        return 0
    row = get_connection().execute(
        f"""
        SELECT COUNT(*) AS cnt
        FROM translations t
        WHERE {clause}
        """,
        params,
    ).fetchone()
    return int(row["cnt"] or 0)


def count_untagged(*, direction: str | None = None, learning_kind: bool = False) -> int:
    clause, params = _direction_filter_clause(direction, learning_kind=learning_kind)
    where = ["NOT EXISTS (SELECT 1 FROM translation_tags tt WHERE tt.translation_id = t.id)"]
    if clause:
        where.append(clause)
    row = get_connection().execute(
        f"""
        SELECT COUNT(*) AS cnt
        FROM translations t
        WHERE {' AND '.join(where)}
        """,
        params,
    ).fetchone()
    return int(row["cnt"] or 0)


def get_tag_counts(*, direction: str | None = None, learning_kind: bool = False) -> list[tuple[str, int]]:
    clause, params = _direction_filter_clause(direction, learning_kind=learning_kind)
    extra = f" AND {clause}" if clause else ""
    rows = get_connection().execute(
        f"""
        SELECT MIN(tg.name) AS name, COUNT(DISTINCT t.id) AS cnt
        FROM tags tg
        INNER JOIN translation_tags tt ON tt.tag_id = tg.id
        INNER JOIN translations t ON t.id = tt.translation_id
        WHERE 1=1{extra}
        GROUP BY lower(trim(tg.name))
        ORDER BY lower(trim(tg.name))
        """,
        params,
    ).fetchall()
    return [(str(row["name"]), int(row["cnt"])) for row in rows]
