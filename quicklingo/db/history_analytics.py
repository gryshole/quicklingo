from __future__ import annotations

from datetime import date, timedelta

from quicklingo.db.connection import get_connection
from quicklingo.db.history_models import parse_tags


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
        if row["direction"] == "ua-en":
            stats["ua_en"] = row["cnt"]
        elif row["direction"] == "en-ua":
            stats["en_ua"] = row["cnt"]
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
