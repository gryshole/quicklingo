from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from quicklingo.db import connection as db_connection
from quicklingo.db.history_schema import init_db
from quicklingo.db.learning import (
    create_deck,
    get_card,
    get_or_create_distractor_deck,
    list_cards,
    upsert_card,
)
from quicklingo.db.learning_cards import batch_upsert_cards
from quicklingo.learning.quiz.distractor_deck import QUIZ_DISTRACTOR_CARD_TYPE
from quicklingo.learning.quiz.distractor_transfer import transfer_distractor_cards


class DistractorTransferTests(unittest.TestCase):
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

    def _add_distractor(self, direction: str, front: str, back: str) -> int:
        deck = get_or_create_distractor_deck(direction)
        ids = batch_upsert_cards(
            deck.id,
            [
                {
                    "front": front,
                    "back": back,
                    "card_type": QUIZ_DISTRACTOR_CARD_TYPE,
                }
            ],
        )
        return ids[0]

    def test_move_new_card_to_target_deck(self) -> None:
        card_id = self._add_distractor("ua-en", "barn", "сарай")
        distractor_deck = get_or_create_distractor_deck("ua-en")
        result = transfer_distractor_cards([card_id], "farm", "ua-en")
        self.assertEqual(result.moved, 1)
        self.assertEqual(result.merged, 0)
        self.assertEqual(result.skipped, 0)
        self.assertEqual(len(list_cards(distractor_deck.id)), 0)
        target = create_deck("Farm", "farm", "ua-en", source="ai")
        cards = list_cards(target.id)
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0].front, "barn")
        self.assertEqual(cards[0].card_type, "basic")
        self.assertTrue(cards[0].next_review_date)

    def test_merge_duplicate_and_remove_distractor(self) -> None:
        target = create_deck("Farm", "farm", "ua-en", source="ai")
        upsert_card(target.id, front="fence", back="")
        card_id = self._add_distractor("ua-en", "fence", "паркан")
        distractor_deck = get_or_create_distractor_deck("ua-en")
        result = transfer_distractor_cards([card_id], "farm", "ua-en")
        self.assertEqual(result.moved, 0)
        self.assertEqual(result.merged, 1)
        self.assertEqual(len(list_cards(distractor_deck.id)), 0)
        cards = list_cards(target.id)
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0].back, "паркан")
        self.assertIsNone(get_card(card_id))

    def test_rejects_distractor_tag(self) -> None:
        card_id = self._add_distractor("ua-en", "barn", "сарай")
        result = transfer_distractor_cards([card_id], "__quiz-distractors", "ua-en")
        self.assertEqual(result.skipped, 1)
        self.assertEqual(result.moved, 0)

    def test_skips_wrong_direction(self) -> None:
        card_id = self._add_distractor("ua-en", "barn", "сарай")
        result = transfer_distractor_cards([card_id], "farm", "en-ua")
        self.assertEqual(result.skipped, 1)
        self.assertEqual(result.moved, 0)
