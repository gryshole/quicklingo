from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from quicklingo.db import connection as db_connection
from quicklingo.db.history_repository import save_translation, search_records
from quicklingo.db.history_schema import init_db
from quicklingo.db.learning import create_deck, upsert_card
from quicklingo.learning.deck_corpus import pending_corpus_records
from quicklingo.learning.deck_split.move_cards import move_cards_to_deck


class DeckCorpusCoverageTests(unittest.TestCase):
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

    def test_pending_excludes_cards_moved_to_another_deck(self) -> None:
        record_id = save_translation(
            "en-ua",
            "martyr",
            "мученик",
            "test",
            tags=["tv"],
        )
        tv_deck = create_deck("TV", "tv", "en-ua")
        card_id = upsert_card(
            tv_deck.id,
            front="martyr",
            back="мученик",
            source_record_id=record_id,
        )
        move_cards_to_deck([card_id], "law-conflict", "en-ua")

        records = search_records(direction="en-ua", tag="tv", learning_kind=True)
        pending = pending_corpus_records(records, tag="tv", direction="en-ua")

        self.assertEqual(len(records), 0)
        self.assertEqual(pending, [])
        law_records = search_records(
            direction="en-ua", tag="law-conflict", learning_kind=True
        )
        self.assertEqual(len(law_records), 1)

    def test_pending_keeps_uncovered_records_in_same_tag(self) -> None:
        save_translation("en-ua", "apple", "яблуко", "test", tags=["tv"])
        save_translation("en-ua", "banana", "банан", "test", tags=["tv"])
        tv_deck = create_deck("TV", "tv", "en-ua")
        upsert_card(tv_deck.id, front="apple", back="яблуко")

        records = search_records(direction="en-ua", tag="tv", learning_kind=True)
        pending = pending_corpus_records(records, tag="tv", direction="en-ua")

        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].source_text, "banana")
