from __future__ import annotations

import sqlite3
import tempfile
import unittest
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from quicklingo.db import connection as db_connection
from quicklingo.db.history_schema import init_db
from quicklingo.db.learning import (
    create_deck,
    delete_quiz_questions_for_card,
    list_decks,
    upsert_card,
    upsert_quiz_question,
)
from quicklingo.db.tombstones import record_card_delete, record_deck_delete
from quicklingo.sync.merge import _apply_tombstones, compute_upload_stats, merge_remote_into_local
from quicklingo.sync.snapshot import create_snapshot


class SyncMergeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmpdir.name) / "history.db"
        self._patch = patch.object(db_connection, "db_path", return_value=self._db_path)
        self._patch.start()
        db_connection.close_all()
        init_db()

    def tearDown(self) -> None:
        db_connection.close_all()
        self._patch.stop()
        self._tmpdir.cleanup()

    @contextmanager
    def _open_remote(self, path: Path) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _remote_from_local(self) -> Path:
        remote = Path(self._tmpdir.name) / "remote.snapshot.db"
        create_snapshot(remote)
        return remote

    def test_merge_adds_remote_card(self) -> None:
        deck = create_deck("Work", "sync-test", "ua-en")
        remote = self._remote_from_local()
        with self._open_remote(remote) as conn:
            conn.execute(
                """
                INSERT INTO learning_cards (
                    deck_id, front, back, context, hint, notes, priority,
                    next_review_date, sync_id, content_updated_at
                )
                VALUES (?, 'remote', 'віддалено', '', '', '', 3, '2026-01-01',
                        'card-sync-1', '2026-01-02T10:00:00+00:00')
                """,
                (deck.id,),
            )
            conn.commit()

        stats = merge_remote_into_local(remote)
        self.assertEqual(stats.cards_added, 1)
        with db_connection.connection() as conn:
            row = conn.execute(
                "SELECT front, back FROM learning_cards WHERE sync_id = ?",
                ("card-sync-1",),
            ).fetchone()
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["front"], "remote")

    def test_tombstone_prevents_card_return(self) -> None:
        deck = create_deck("Work", "sync-test", "ua-en")
        card_id = upsert_card(deck.id, front="hello", back="привіт")
        with db_connection.connection() as conn:
            sync_id = conn.execute(
                "SELECT sync_id FROM learning_cards WHERE id = ?",
                (card_id,),
            ).fetchone()["sync_id"]
            record_card_delete(card_id, device_id="device-a", conn=conn)
            conn.execute("DELETE FROM learning_cards WHERE id = ?", (card_id,))

        remote = self._remote_from_local()
        with self._open_remote(remote) as conn:
            conn.execute(
                """
                INSERT INTO learning_cards (
                    deck_id, front, back, context, hint, notes, priority,
                    next_review_date, sync_id, content_updated_at
                )
                VALUES (?, 'hello', 'привіт', '', '', '', 3, '2026-01-01', ?, '2026-01-01')
                """,
                (deck.id, sync_id),
            )
            conn.commit()

        stats = merge_remote_into_local(remote)
        self.assertEqual(stats.cards_added, 0)
        with db_connection.connection() as conn:
            count = conn.execute(
                "SELECT COUNT(*) AS cnt FROM learning_cards WHERE sync_id = ?",
                (sync_id,),
            ).fetchone()["cnt"]
        self.assertEqual(count, 0)

    def test_lww_remote_wins_on_content(self) -> None:
        deck = create_deck("Work", "sync-test", "ua-en")
        card_id = upsert_card(deck.id, front="hello", back="local")
        with db_connection.connection() as conn:
            sync_id = conn.execute(
                "SELECT sync_id FROM learning_cards WHERE id = ?",
                (card_id,),
            ).fetchone()["sync_id"]
            conn.execute(
                """
                UPDATE learning_cards
                SET content_updated_at = '2026-01-01T00:00:00+00:00'
                WHERE id = ?
                """,
                (card_id,),
            )

        remote = self._remote_from_local()
        with self._open_remote(remote) as conn:
            conn.execute(
                """
                UPDATE learning_cards
                SET back = 'remote', content_updated_at = '2026-01-02T00:00:00+00:00'
                WHERE sync_id = ?
                """,
                (sync_id,),
            )
            conn.commit()

        stats = merge_remote_into_local(remote)
        self.assertGreaterEqual(stats.cards_updated, 1)
        with db_connection.connection() as conn:
            back = conn.execute(
                "SELECT back FROM learning_cards WHERE sync_id = ?",
                (sync_id,),
            ).fetchone()["back"]
        self.assertEqual(back, "remote")

    def test_upload_stats_counts_all_without_remote(self) -> None:
        deck = create_deck("Work", "sync-test", "ua-en")
        upsert_card(deck.id, front="hello", back="привіт")
        local = Path(self._tmpdir.name) / "local.snapshot.db"
        create_snapshot(local)

        stats = compute_upload_stats(local, None)
        self.assertEqual(stats.decks_added, 1)
        self.assertEqual(stats.cards_added, 1)

    def test_upload_stats_counts_new_local_card(self) -> None:
        deck = create_deck("Work", "sync-test", "ua-en")
        remote = self._remote_from_local()
        upsert_card(deck.id, front="new", back="новий")
        local = Path(self._tmpdir.name) / "local.snapshot.db"
        create_snapshot(local)

        stats = compute_upload_stats(local, remote)
        self.assertEqual(stats.cards_added, 1)

    def test_recreate_deck_clears_tombstone_and_survives_sync(self) -> None:
        deck = create_deck("TV", "tv", "en-ua")
        old_card_id = upsert_card(deck.id, front="reckless", back="безрозсудний")
        with db_connection.connection() as conn:
            old_sync_id = conn.execute(
                "SELECT sync_id FROM learning_cards WHERE id = ?",
                (old_card_id,),
            ).fetchone()["sync_id"]
            record_deck_delete(deck.id, device_id="device-a", conn=conn)
            conn.execute("DELETE FROM learning_cards WHERE deck_id = ?", (deck.id,))
            conn.execute("DELETE FROM learning_decks WHERE id = ?", (deck.id,))

        remote = self._remote_from_local()
        recreated = create_deck("TV", "tv", "en-ua")
        upsert_card(recreated.id, front="apple", back="яблуко")

        merge_remote_into_local(remote)
        decks = list_decks()
        self.assertEqual(len(decks), 1)
        self.assertEqual(decks[0].tag, "tv")
        with db_connection.connection() as conn:
            fronts = [
                row["front"]
                for row in conn.execute(
                    "SELECT front FROM learning_cards WHERE deck_id = ? ORDER BY id",
                    (decks[0].id,),
                ).fetchall()
            ]
            tomb = conn.execute(
                """
                SELECT 1 FROM sync_tombstones
                WHERE entity_type = 'deck' AND entity_key = 'deck:tv|en-ua'
                """
            ).fetchone()
            old_card = conn.execute(
                "SELECT 1 FROM learning_cards WHERE sync_id = ?",
                (old_sync_id,),
            ).fetchone()
        self.assertIsNone(tomb)
        self.assertIsNone(old_card)
        self.assertEqual(fronts, ["apple"])

    def test_newer_local_cards_beat_remote_deck_tombstone(self) -> None:
        """A deleted on remote; B still has newer cards — deck must survive merge."""
        deck = create_deck("TV", "tv", "en-ua")
        old_id = upsert_card(deck.id, front="old", back="старе")
        new_id = upsert_card(deck.id, front="new", back="нове")
        with db_connection.connection() as conn:
            old_sync = conn.execute(
                "SELECT sync_id FROM learning_cards WHERE id = ?",
                (old_id,),
            ).fetchone()["sync_id"]
            conn.execute(
                """
                UPDATE learning_cards
                SET content_updated_at = '2026-01-01T00:00:00'
                WHERE id = ?
                """,
                (old_id,),
            )
            conn.execute(
                """
                UPDATE learning_cards
                SET content_updated_at = '2026-01-03T00:00:00'
                WHERE id = ?
                """,
                (new_id,),
            )
            conn.execute(
                """
                UPDATE learning_decks
                SET updated_at = '2026-01-01T00:00:00'
                WHERE id = ?
                """,
                (deck.id,),
            )

        remote = self._remote_from_local()
        with self._open_remote(remote) as conn:
            conn.execute("DELETE FROM learning_cards")
            conn.execute("DELETE FROM learning_decks")
            conn.execute(
                """
                INSERT INTO sync_tombstones (entity_type, entity_key, deleted_at, device_id)
                VALUES ('deck', 'deck:tv|en-ua', '2026-01-02 00:00:00', 'device-a')
                """
            )
            conn.execute(
                """
                INSERT INTO sync_tombstones (entity_type, entity_key, deleted_at, device_id)
                VALUES (?, ?, '2026-01-02 00:00:00', 'device-a')
                """,
                ("card", f"card:{old_sync}"),
            )
            conn.commit()

        merge_remote_into_local(remote)
        decks = list_decks()
        self.assertEqual(len(decks), 1)
        with db_connection.connection() as conn:
            fronts = [
                row["front"]
                for row in conn.execute(
                    "SELECT front FROM learning_cards WHERE deck_id = ? ORDER BY front",
                    (decks[0].id,),
                ).fetchall()
            ]
            deck_tomb = conn.execute(
                """
                SELECT 1 FROM sync_tombstones
                WHERE entity_type = 'deck' AND entity_key = 'deck:tv|en-ua'
                """
            ).fetchone()
        self.assertIsNone(deck_tomb)
        self.assertEqual(fronts, ["new"])

    def test_apply_deck_tombstone_deletes_cards_even_if_fk_off(self) -> None:
        deck = create_deck("TV", "tv", "en-ua")
        upsert_card(deck.id, front="orphan-me", back="x")
        with db_connection.connection() as conn:
            conn.execute("PRAGMA foreign_keys=OFF")
            conn.execute(
                """
                INSERT INTO sync_tombstones (entity_type, entity_key, deleted_at, device_id)
                VALUES ('deck', 'deck:tv|en-ua', datetime('now'), 'device-a')
                """
            )
            applied = _apply_tombstones(conn)
            orphans = conn.execute(
                """
                SELECT COUNT(*) AS cnt FROM learning_cards
                WHERE deck_id NOT IN (SELECT id FROM learning_decks)
                """
            ).fetchone()["cnt"]
            decks = conn.execute("SELECT COUNT(*) AS cnt FROM learning_decks").fetchone()["cnt"]
        self.assertGreaterEqual(applied, 1)
        self.assertEqual(orphans, 0)
        self.assertEqual(decks, 0)

    def test_create_deck_same_tag_is_upsert(self) -> None:
        first = create_deck("One", "same", "ua-en")
        second = create_deck("Two", "same", "ua-en")
        self.assertEqual(first.id, second.id)
        decks = list_decks()
        self.assertEqual(len(decks), 1)
        self.assertEqual(decks[0].name, "Two")

    def test_quiz_delete_tombstone_blocks_remote_return(self) -> None:
        deck = create_deck("Work", "quiz-tag", "ua-en")
        card_id = upsert_card(deck.id, front="hello", back="привіт")
        upsert_quiz_question(
            card_id=card_id,
            question_type="fill_blank",
            prompt_text="___",
            example_sentence="",
            choices_pool=["hello", "world"],
            correct_english="hello",
        )
        with db_connection.connection() as conn:
            conn.execute(
                """
                UPDATE quiz_questions
                SET updated_at = '2026-01-01 00:00:00', created_at = '2026-01-01 00:00:00'
                WHERE card_id = ?
                """,
                (card_id,),
            )
        remote = self._remote_from_local()
        delete_quiz_questions_for_card(card_id)

        merge_remote_into_local(remote)
        with db_connection.connection() as conn:
            count = conn.execute(
                "SELECT COUNT(*) AS cnt FROM quiz_questions WHERE card_id = ?",
                (card_id,),
            ).fetchone()["cnt"]
            tomb = conn.execute(
                """
                SELECT 1 FROM sync_tombstones
                WHERE entity_type = 'quiz_question'
                """
            ).fetchone()
        self.assertIsNotNone(tomb)
        self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
