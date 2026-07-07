from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from unittest.mock import patch

from quicklingo.db import connection as db_connection
from quicklingo.db.history_schema import init_db
from quicklingo.db.learning import create_deck, upsert_card
from quicklingo.db.tombstones import record_card_delete
from quicklingo.sync.merge import compute_upload_stats, merge_remote_into_local
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


if __name__ == "__main__":
    unittest.main()
