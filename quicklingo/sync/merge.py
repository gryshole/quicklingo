from __future__ import annotations

import sqlite3
from collections.abc import Callable
from pathlib import Path

from quicklingo.db.connection import connection
from quicklingo.db.history_tags import set_translation_tags
from quicklingo.db.tombstones import is_tombstoned, record_deck_children_tombstones
from quicklingo.sync.keys import (
    card_entity_key,
    deck_entity_key,
    quiz_entity_key,
    translation_entity_key,
)
from quicklingo.sync.models import SyncMergeStats, _max_ts, _pick_side


def merge_remote_into_local(remote_path: Path) -> SyncMergeStats:
    stats = SyncMergeStats()
    with connection() as conn:
        conn.execute("ATTACH DATABASE ? AS remote", (str(remote_path),))
        try:
            stats.tombstones_merged = _merge_tombstones(conn)
            _prune_stale_tombstones(conn)
            stats.deletions_applied = _apply_tombstones(conn)
            translation_map = _merge_translations(conn, stats)
            _merge_tags(conn)
            deck_map = _merge_decks(conn, stats)
            card_map = _merge_cards(conn, stats, deck_map)
            _merge_quiz_questions(conn, stats, card_map, translation_map)
        finally:
            conn.commit()
            conn.execute("DETACH DATABASE remote")
    return stats


def _merge_tombstones(conn: sqlite3.Connection) -> int:
    rows = conn.execute(
        """
        SELECT entity_type, entity_key, deleted_at, device_id
        FROM remote.sync_tombstones
        """
    ).fetchall()
    merged = 0
    for row in rows:
        existing = conn.execute(
            """
            SELECT deleted_at FROM sync_tombstones
            WHERE entity_type = ? AND entity_key = ?
            """,
            (row["entity_type"], row["entity_key"]),
        ).fetchone()
        if existing and str(existing["deleted_at"] or "") >= str(row["deleted_at"] or ""):
            continue
        conn.execute(
            """
            INSERT INTO sync_tombstones (entity_type, entity_key, deleted_at, device_id)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(entity_type, entity_key) DO UPDATE SET
                deleted_at = excluded.deleted_at,
                device_id = excluded.device_id
            """,
            (row["entity_type"], row["entity_key"], row["deleted_at"], row["device_id"]),
        )
        merged += 1
    return merged


def _deck_ts(row: sqlite3.Row | None) -> str:
    if row is None:
        return ""
    return _max_ts(str(row["updated_at"] or ""), str(row["created_at"] or ""))


def _max_card_ts_for_deck(conn: sqlite3.Connection, schema: str, tag: str, direction: str) -> str:
    row = conn.execute(
        f"""
        SELECT MAX(lc.content_updated_at) AS ts
        FROM {schema}.learning_cards lc
        JOIN {schema}.learning_decks ld ON ld.id = lc.deck_id
        WHERE ld.tag = ? AND ld.direction = ?
        """,
        (tag, direction),
    ).fetchone()
    return str(row["ts"] or "") if row else ""


def _content_ts_card(conn: sqlite3.Connection, entity_key: str) -> str:
    if not entity_key.startswith("card:"):
        return ""
    sync_id = entity_key[5:]
    row = conn.execute(
        """
        SELECT content_updated_at FROM learning_cards WHERE sync_id = ?
        """,
        (sync_id,),
    ).fetchone()
    remote = conn.execute(
        """
        SELECT content_updated_at FROM remote.learning_cards WHERE sync_id = ?
        """,
        (sync_id,),
    ).fetchone()
    return _max_ts(
        str(row["content_updated_at"] if row else ""),
        str(remote["content_updated_at"] if remote else ""),
    )


def _content_ts_deck(conn: sqlite3.Connection, entity_key: str) -> str:
    if not entity_key.startswith("deck:"):
        return ""
    tag_direction = entity_key[5:].split("|", 1)
    if len(tag_direction) != 2:
        return ""
    tag, direction = tag_direction
    row = conn.execute(
        """
        SELECT updated_at, created_at FROM learning_decks
        WHERE tag = ? AND direction = ?
        ORDER BY id DESC LIMIT 1
        """,
        (tag, direction),
    ).fetchone()
    remote = conn.execute(
        """
        SELECT updated_at, created_at FROM remote.learning_decks
        WHERE tag = ? AND direction = ?
        ORDER BY id DESC LIMIT 1
        """,
        (tag, direction),
    ).fetchone()
    deck_ts = _max_ts(_deck_ts(row), _deck_ts(remote))
    card_ts = _max_ts(
        _max_card_ts_for_deck(conn, "main", tag, direction),
        _max_card_ts_for_deck(conn, "remote", tag, direction),
    )
    return _max_ts(deck_ts, card_ts)


def _content_ts_quiz_question(conn: sqlite3.Connection, entity_key: str) -> str:
    if not entity_key.startswith("quiz:"):
        return ""
    parts = entity_key[5:].split("|", 1)
    if len(parts) != 2:
        return ""
    card_sync_id, question_type = parts
    row = conn.execute(
        """
        SELECT qq.updated_at AS updated_at
        FROM quiz_questions qq
        JOIN learning_cards lc ON lc.id = qq.card_id
        WHERE lc.sync_id = ? AND qq.question_type = ?
        ORDER BY qq.id DESC LIMIT 1
        """,
        (card_sync_id, question_type),
    ).fetchone()
    remote = conn.execute(
        """
        SELECT qq.updated_at AS updated_at
        FROM remote.quiz_questions qq
        JOIN remote.learning_cards lc ON lc.id = qq.card_id
        WHERE lc.sync_id = ? AND qq.question_type = ?
        ORDER BY qq.id DESC LIMIT 1
        """,
        (card_sync_id, question_type),
    ).fetchone()
    return _max_ts(
        str(row["updated_at"] if row else ""),
        str(remote["updated_at"] if remote else ""),
    )


def _content_ts_translation(conn: sqlite3.Connection, entity_key: str) -> str:
    if not entity_key.startswith("translation:"):
        return ""
    parts = entity_key[len("translation:") :].split("|", 2)
    if len(parts) != 3:
        return ""
    content_hash, direction, profile_id = parts
    row = conn.execute(
        """
        SELECT updated_at FROM translations
        WHERE content_hash = ? AND direction = ? AND profile_id = ?
        ORDER BY id DESC LIMIT 1
        """,
        (content_hash, direction, profile_id),
    ).fetchone()
    remote = conn.execute(
        """
        SELECT updated_at FROM remote.translations
        WHERE content_hash = ? AND direction = ? AND profile_id = ?
        ORDER BY id DESC LIMIT 1
        """,
        (content_hash, direction, profile_id),
    ).fetchone()
    return _max_ts(
        str(row["updated_at"] if row else ""),
        str(remote["updated_at"] if remote else ""),
    )


_CONTENT_TS_HANDLERS: dict[str, Callable[[sqlite3.Connection, str], str]] = {
    "card": _content_ts_card,
    "deck": _content_ts_deck,
    "quiz_question": _content_ts_quiz_question,
    "translation": _content_ts_translation,
}


def _content_ts_for_tombstone(conn: sqlite3.Connection, entity_type: str, entity_key: str) -> str:
    handler = _CONTENT_TS_HANDLERS.get(entity_type)
    return handler(conn, entity_key) if handler else ""


def _prune_stale_tombstones(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        "SELECT entity_type, entity_key, deleted_at FROM sync_tombstones"
    ).fetchall()
    for row in rows:
        content_ts = _content_ts_for_tombstone(conn, row["entity_type"], row["entity_key"])
        if content_ts and content_ts >= str(row["deleted_at"] or ""):
            conn.execute(
                """
                DELETE FROM sync_tombstones
                WHERE entity_type = ? AND entity_key = ?
                """,
                (row["entity_type"], row["entity_key"]),
            )


def _apply_tombstones(conn: sqlite3.Connection) -> int:
    applied = 0
    rows = conn.execute(
        "SELECT entity_type, entity_key, device_id FROM sync_tombstones"
    ).fetchall()
    for row in rows:
        entity_type = row["entity_type"]
        entity_key = row["entity_key"]
        device_id = str(row["device_id"] or "")
        if entity_type == "deck" and entity_key.startswith("deck:"):
            tag_direction = entity_key[5:].split("|", 1)
            if len(tag_direction) != 2:
                continue
            tag, direction = tag_direction
            decks = conn.execute(
                """
                SELECT id FROM learning_decks
                WHERE tag = ? AND direction = ?
                ORDER BY id ASC
                """,
                (tag, direction),
            ).fetchall()
            for deck in decks:
                deck_id = int(deck["id"])
                record_deck_children_tombstones(conn, deck_id, device_id=device_id)
                conn.execute("DELETE FROM learning_cards WHERE deck_id = ?", (deck_id,))
                conn.execute("DELETE FROM learning_decks WHERE id = ?", (deck_id,))
                applied += 1
        elif entity_type == "card" and entity_key.startswith("card:"):
            sync_id = entity_key[5:]
            card = conn.execute(
                "SELECT id FROM learning_cards WHERE sync_id = ?",
                (sync_id,),
            ).fetchone()
            if card:
                conn.execute("DELETE FROM learning_cards WHERE id = ?", (int(card["id"]),))
                applied += 1
        elif entity_type == "quiz_question" and entity_key.startswith("quiz:"):
            rest = entity_key[5:]
            parts = rest.split("|", 1)
            if len(parts) != 2:
                continue
            card_sync_id, question_type = parts
            cursor = conn.execute(
                """
                DELETE FROM quiz_questions
                WHERE question_type = ?
                  AND card_id IN (
                      SELECT id FROM learning_cards WHERE sync_id = ?
                  )
                """,
                (question_type, card_sync_id),
            )
            applied += cursor.rowcount
        elif entity_type == "translation" and entity_key.startswith("translation:"):
            parts = entity_key[len("translation:") :].split("|", 2)
            if len(parts) != 3:
                continue
            content_hash, direction, profile_id = parts
            cursor = conn.execute(
                """
                DELETE FROM translations
                WHERE content_hash = ? AND direction = ? AND profile_id = ?
                """,
                (content_hash, direction, profile_id),
            )
            applied += cursor.rowcount
    return applied


def _merge_translations(conn: sqlite3.Connection, stats: SyncMergeStats) -> dict[int, int]:
    id_map: dict[int, int] = {}
    rows = conn.execute(
        """
        SELECT id, created_at, direction, source_text, result_text, model, profile_id,
               content_hash, is_starred, updated_at
        FROM remote.translations
        ORDER BY id ASC
        """
    ).fetchall()
    for row in rows:
        key = translation_entity_key(
            str(row["content_hash"] or ""),
            str(row["direction"] or ""),
            str(row["profile_id"] or ""),
        )
        if is_tombstoned(conn, "translation", key):
            continue
        local = conn.execute(
            """
            SELECT id, is_starred, updated_at
            FROM translations
            WHERE content_hash = ? AND direction = ? AND profile_id = ?
            ORDER BY id DESC LIMIT 1
            """,
            (row["content_hash"], row["direction"], row["profile_id"]),
        ).fetchone()
        if local is None:
            cursor = conn.execute(
                """
                INSERT INTO translations (
                    created_at, direction, source_text, result_text, model,
                    profile_id, content_hash, is_starred, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["created_at"],
                    row["direction"],
                    row["source_text"],
                    row["result_text"],
                    row["model"],
                    row["profile_id"],
                    row["content_hash"],
                    row["is_starred"],
                    row["updated_at"] or row["created_at"],
                ),
            )
            local_id = int(cursor.lastrowid or 0)
            id_map[int(row["id"])] = local_id
            stats.translations_added += 1
            _copy_translation_tags(conn, int(row["id"]), local_id, winner="remote")
            continue
        local_id = int(local["id"])
        id_map[int(row["id"])] = local_id
        winner = _pick_side(str(local["updated_at"] or ""), str(row["updated_at"] or ""))
        if winner == "remote":
            conn.execute(
                """
                UPDATE translations
                SET is_starred = ?, updated_at = ?
                WHERE id = ?
                """,
                (row["is_starred"], row["updated_at"] or row["created_at"], local_id),
            )
            _copy_translation_tags(conn, int(row["id"]), local_id, winner="remote")
    return id_map


def _copy_translation_tags(
    conn: sqlite3.Connection,
    remote_id: int,
    local_id: int,
    *,
    winner: str,
) -> None:
    if winner != "remote":
        return
    rows = conn.execute(
        """
        SELECT tg.name
        FROM remote.translation_tags tt
        JOIN remote.tags tg ON tg.id = tt.tag_id
        WHERE tt.translation_id = ?
        ORDER BY lower(trim(tg.name))
        """,
        (remote_id,),
    ).fetchall()
    names = [str(row["name"]) for row in rows]
    set_translation_tags(conn, local_id, names)


def _merge_tags(conn: sqlite3.Connection) -> None:
    rows = conn.execute("SELECT name FROM remote.tags").fetchall()
    for row in rows:
        name = str(row["name"] or "").strip()
        if not name:
            continue
        conn.execute(
            "INSERT OR IGNORE INTO tags (name) VALUES (?)",
            (name,),
        )


def _merge_decks(conn: sqlite3.Connection, stats: SyncMergeStats) -> dict[tuple[str, str], int]:
    deck_map: dict[tuple[str, str], int] = {}
    rows = conn.execute(
        """
        SELECT id, name, tag, direction, created_at, analysis_summary, source, updated_at
        FROM remote.learning_decks
        ORDER BY id ASC
        """
    ).fetchall()
    for row in rows:
        tag = str(row["tag"] or "")
        direction = str(row["direction"] or "")
        key = deck_entity_key(tag, direction)
        if is_tombstoned(conn, "deck", key):
            continue
        local = conn.execute(
            """
            SELECT id, name, analysis_summary, updated_at
            FROM learning_decks
            WHERE tag = ? AND direction = ?
            ORDER BY id DESC LIMIT 1
            """,
            (tag, direction),
        ).fetchone()
        if local is None:
            cursor = conn.execute(
                """
                INSERT INTO learning_decks (
                    name, tag, direction, created_at, analysis_summary, source, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["name"],
                    tag,
                    direction,
                    row["created_at"],
                    row["analysis_summary"],
                    row["source"],
                    row["updated_at"] or row["created_at"],
                ),
            )
            deck_map[(tag, direction)] = int(cursor.lastrowid or 0)
            stats.decks_added += 1
            continue
        local_id = int(local["id"])
        deck_map[(tag, direction)] = local_id
        if _pick_side(str(local["updated_at"] or ""), str(row["updated_at"] or "")) == "remote":
            conn.execute(
                """
                UPDATE learning_decks
                SET name = ?, analysis_summary = ?, updated_at = ?
                WHERE id = ?
                """,
                (row["name"], row["analysis_summary"], row["updated_at"], local_id),
            )
    return deck_map


def _merge_cards(
    conn: sqlite3.Connection,
    stats: SyncMergeStats,
    deck_map: dict[tuple[str, str], int],
) -> dict[str, int]:
    sync_map: dict[str, int] = {}
    rows = conn.execute(
        """
        SELECT lc.*, ld.tag, ld.direction
        FROM remote.learning_cards lc
        JOIN remote.learning_decks ld ON ld.id = lc.deck_id
        ORDER BY lc.id ASC
        """
    ).fetchall()
    for row in rows:
        sync_id = str(row["sync_id"] or "")
        if not sync_id:
            continue
        if is_tombstoned(conn, "card", card_entity_key(sync_id)):
            continue
        tag = str(row["tag"] or "")
        direction = str(row["direction"] or "")
        deck_id = deck_map.get((tag, direction))
        if deck_id is None:
            deck = conn.execute(
                "SELECT id FROM learning_decks WHERE tag = ? AND direction = ?",
                (tag, direction),
            ).fetchone()
            if not deck:
                continue
            deck_id = int(deck["id"])
        local = conn.execute(
            """
            SELECT id, front, back, context, hint, notes, priority, phonetic, image_prompt,
                   quiz_distractors, ease, interval_days, next_review_date, last_reviewed,
                   fsrs_state, content_updated_at, srs_updated_at, audio_path, image_path
            FROM learning_cards WHERE sync_id = ?
            """,
            (sync_id,),
        ).fetchone()
        if local is None:
            cursor = conn.execute(
                """
                INSERT INTO learning_cards (
                    deck_id, front, back, context, hint, notes, priority, source_record_id,
                    ease, interval_days, next_review_date, last_reviewed, fsrs_state,
                    image_path, image_prompt, phonetic, audio_path, card_type, quiz_distractors,
                    sync_id, content_updated_at, srs_updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, '', ?, ?, '', ?, ?, ?, ?, ?)
                """,
                (
                    deck_id,
                    row["front"],
                    row["back"],
                    row["context"],
                    row["hint"],
                    row["notes"],
                    row["priority"],
                    row["ease"],
                    row["interval_days"],
                    row["next_review_date"],
                    row["last_reviewed"],
                    row["fsrs_state"],
                    row["image_prompt"],
                    row["phonetic"],
                    row["card_type"],
                    row["quiz_distractors"],
                    sync_id,
                    row["content_updated_at"] or "",
                    row["srs_updated_at"] or "",
                ),
            )
            sync_map[sync_id] = int(cursor.lastrowid or 0)
            stats.cards_added += 1
            continue
        local_id = int(local["id"])
        sync_map[sync_id] = local_id
        content_winner = _pick_side(
            str(local["content_updated_at"] or ""),
            str(row["content_updated_at"] or ""),
        )
        srs_winner = _pick_side(
            str(local["srs_updated_at"] or ""),
            str(row["srs_updated_at"] or ""),
        )
        if content_winner == "remote":
            conn.execute(
                """
                UPDATE learning_cards
                SET front = ?, back = ?, context = ?, hint = ?, notes = ?, priority = ?,
                    phonetic = ?, image_prompt = ?, quiz_distractors = ?,
                    content_updated_at = ?
                WHERE id = ?
                """,
                (
                    row["front"],
                    row["back"],
                    row["context"],
                    row["hint"],
                    row["notes"],
                    row["priority"],
                    row["phonetic"],
                    row["image_prompt"],
                    row["quiz_distractors"],
                    row["content_updated_at"],
                    local_id,
                ),
            )
            stats.cards_updated += 1
        if srs_winner == "remote":
            conn.execute(
                """
                UPDATE learning_cards
                SET ease = ?, interval_days = ?, next_review_date = ?, last_reviewed = ?,
                    fsrs_state = ?, srs_updated_at = ?
                WHERE id = ?
                """,
                (
                    row["ease"],
                    row["interval_days"],
                    row["next_review_date"],
                    row["last_reviewed"],
                    row["fsrs_state"],
                    row["srs_updated_at"],
                    local_id,
                ),
            )
    return sync_map


def _merge_quiz_questions(
    conn: sqlite3.Connection,
    stats: SyncMergeStats,
    card_map: dict[str, int],
    translation_map: dict[int, int],
) -> None:
    rows = conn.execute(
        """
        SELECT qq.*, lc.sync_id
        FROM remote.quiz_questions qq
        JOIN remote.learning_cards lc ON lc.id = qq.card_id
        ORDER BY qq.id ASC
        """
    ).fetchall()
    for row in rows:
        sync_id = str(row["sync_id"] or "")
        question_type = str(row["question_type"] or "")
        if not sync_id:
            continue
        key = quiz_entity_key(sync_id, question_type)
        if is_tombstoned(conn, "quiz_question", key):
            continue
        local_card_id = card_map.get(sync_id)
        if local_card_id is None:
            found = conn.execute(
                "SELECT id FROM learning_cards WHERE sync_id = ?",
                (sync_id,),
            ).fetchone()
            if not found:
                continue
            local_card_id = int(found["id"])
        local = conn.execute(
            """
            SELECT id, updated_at FROM quiz_questions
            WHERE card_id = ? AND question_type = ?
            """,
            (local_card_id, question_type),
        ).fetchone()
        payload = (
            row["prompt_text"],
            row["example_sentence"],
            row["choices_pool"],
            row["correct_english"],
            row["status"],
            row["model_id"],
            row["prompt_version"],
            row["updated_at"],
        )
        if local is None:
            conn.execute(
                """
                INSERT INTO quiz_questions (
                    card_id, question_type, prompt_text, example_sentence, choices_pool,
                    correct_english, status, model_id, prompt_version, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    local_card_id,
                    question_type,
                    *payload[:-1],
                    row["created_at"],
                    payload[-1],
                ),
            )
            stats.quiz_added += 1
            continue
        if _pick_side(str(local["updated_at"] or ""), str(row["updated_at"] or "")) == "remote":
            conn.execute(
                """
                UPDATE quiz_questions
                SET prompt_text = ?, example_sentence = ?, choices_pool = ?,
                    correct_english = ?, status = ?, model_id = ?, prompt_version = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (*payload, int(local["id"])),
            )
            stats.quiz_updated += 1


def compute_upload_stats(local_path: Path, remote_path: Path | None) -> SyncMergeStats:
    """Count entities in the local snapshot that are new or newer vs remote."""
    conn = sqlite3.connect(local_path)
    conn.row_factory = sqlite3.Row
    try:
        if remote_path is None or not remote_path.is_file():
            return _count_uploadable_in_local(conn)
        conn.execute("ATTACH DATABASE ? AS remote", (str(remote_path),))
        try:
            stats = SyncMergeStats()
            _diff_upload_translations(conn, stats)
            _diff_upload_decks(conn, stats)
            _diff_upload_cards(conn, stats)
            _diff_upload_quiz(conn, stats)
            return stats
        finally:
            conn.execute("DETACH DATABASE remote")
    finally:
        conn.close()


def _count_uploadable_in_local(conn: sqlite3.Connection) -> SyncMergeStats:
    stats = SyncMergeStats()
    for row in conn.execute(
        """
        SELECT content_hash, direction, profile_id
        FROM translations
        """
    ).fetchall():
        key = translation_entity_key(
            str(row["content_hash"] or ""),
            str(row["direction"] or ""),
            str(row["profile_id"] or ""),
        )
        if not is_tombstoned(conn, "translation", key):
            stats.translations_added += 1

    for row in conn.execute(
        "SELECT tag, direction FROM learning_decks"
    ).fetchall():
        key = deck_entity_key(str(row["tag"] or ""), str(row["direction"] or ""))
        if not is_tombstoned(conn, "deck", key):
            stats.decks_added += 1

    for row in conn.execute("SELECT sync_id FROM learning_cards").fetchall():
        sync_id = str(row["sync_id"] or "")
        if not sync_id:
            continue
        if not is_tombstoned(conn, "card", card_entity_key(sync_id)):
            stats.cards_added += 1

    for row in conn.execute(
        """
        SELECT lc.sync_id, qq.question_type
        FROM quiz_questions qq
        JOIN learning_cards lc ON lc.id = qq.card_id
        """
    ).fetchall():
        sync_id = str(row["sync_id"] or "")
        question_type = str(row["question_type"] or "")
        if not sync_id:
            continue
        key = quiz_entity_key(sync_id, question_type)
        if not is_tombstoned(conn, "quiz_question", key):
            stats.quiz_added += 1
    return stats


def _diff_upload_translations(conn: sqlite3.Connection, stats: SyncMergeStats) -> None:
    rows = conn.execute(
        """
        SELECT content_hash, direction, profile_id, updated_at, created_at
        FROM translations
        ORDER BY id ASC
        """
    ).fetchall()
    for row in rows:
        key = translation_entity_key(
            str(row["content_hash"] or ""),
            str(row["direction"] or ""),
            str(row["profile_id"] or ""),
        )
        if is_tombstoned(conn, "translation", key):
            continue
        remote = conn.execute(
            """
            SELECT updated_at FROM remote.translations
            WHERE content_hash = ? AND direction = ? AND profile_id = ?
            ORDER BY id DESC LIMIT 1
            """,
            (row["content_hash"], row["direction"], row["profile_id"]),
        ).fetchone()
        if remote is None:
            stats.translations_added += 1


def _diff_upload_decks(conn: sqlite3.Connection, stats: SyncMergeStats) -> None:
    rows = conn.execute(
        """
        SELECT tag, direction, updated_at, created_at
        FROM learning_decks
        ORDER BY id ASC
        """
    ).fetchall()
    for row in rows:
        tag = str(row["tag"] or "")
        direction = str(row["direction"] or "")
        key = deck_entity_key(tag, direction)
        if is_tombstoned(conn, "deck", key):
            continue
        remote = conn.execute(
            """
            SELECT updated_at FROM remote.learning_decks
            WHERE tag = ? AND direction = ?
            ORDER BY id DESC LIMIT 1
            """,
            (tag, direction),
        ).fetchone()
        if remote is None:
            stats.decks_added += 1


def _diff_upload_cards(conn: sqlite3.Connection, stats: SyncMergeStats) -> None:
    rows = conn.execute(
        """
        SELECT sync_id, content_updated_at, srs_updated_at
        FROM learning_cards
        ORDER BY id ASC
        """
    ).fetchall()
    for row in rows:
        sync_id = str(row["sync_id"] or "")
        if not sync_id:
            continue
        if is_tombstoned(conn, "card", card_entity_key(sync_id)):
            continue
        remote = conn.execute(
            """
            SELECT content_updated_at, srs_updated_at
            FROM remote.learning_cards
            WHERE sync_id = ?
            """,
            (sync_id,),
        ).fetchone()
        if remote is None:
            stats.cards_added += 1
            continue
        local_content = str(row["content_updated_at"] or "")
        remote_content = str(remote["content_updated_at"] or "")
        local_srs = str(row["srs_updated_at"] or "")
        remote_srs = str(remote["srs_updated_at"] or "")
        if local_content > remote_content or local_srs > remote_srs:
            stats.cards_updated += 1


def _diff_upload_quiz(conn: sqlite3.Connection, stats: SyncMergeStats) -> None:
    rows = conn.execute(
        """
        SELECT lc.sync_id, qq.question_type, qq.updated_at, qq.created_at
        FROM quiz_questions qq
        JOIN learning_cards lc ON lc.id = qq.card_id
        ORDER BY qq.id ASC
        """
    ).fetchall()
    for row in rows:
        sync_id = str(row["sync_id"] or "")
        question_type = str(row["question_type"] or "")
        if not sync_id:
            continue
        key = quiz_entity_key(sync_id, question_type)
        if is_tombstoned(conn, "quiz_question", key):
            continue
        remote = conn.execute(
            """
            SELECT qq.updated_at
            FROM remote.quiz_questions qq
            JOIN remote.learning_cards lc ON lc.id = qq.card_id
            WHERE lc.sync_id = ? AND qq.question_type = ?
            """,
            (sync_id, question_type),
        ).fetchone()
        if remote is None:
            stats.quiz_added += 1
            continue
        if str(row["updated_at"] or "") > str(remote["updated_at"] or ""):
            stats.quiz_updated += 1
