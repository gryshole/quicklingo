from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from quicklingo.db import connection as db_connection
from quicklingo.db.history_schema import init_db
from quicklingo.db.learning import create_deck, get_or_create_distractor_deck, upsert_card, upsert_quiz_question
from quicklingo.db.learning_cards import batch_upsert_cards, list_cards
from quicklingo.learning.quiz.aggregator import list_quiz_eligible_decks
from quicklingo.learning.quiz.choice_lookup import lookup_english_metadata
from quicklingo.learning.quiz.distractor_deck import (
    QUIZ_DISTRACTOR_CARD_TYPE,
    QUIZ_DISTRACTOR_DECK_TAG,
    filter_user_decks,
    is_quiz_distractor_deck,
)
from quicklingo.learning.quiz.distractor_words import collect_missing_distractor_words


class QuizDistractorDeckTests(unittest.TestCase):
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

    def test_collect_missing_distractor_words_skips_existing_cards(self) -> None:
        main = create_deck("Farm", "farm", "ua-en", source="ai")
        card_id = upsert_card(main.id, front="plough-uk", back="plow", notes="Definition: farming tool")
        upsert_quiz_question(
            card_id=card_id,
            question_type="translation_recall",
            prompt_text="plough-uk",
            example_sentence="",
            choices_pool=["plow", "barn", "fence"],
            correct_english="plow",
            status="active",
        )
        missing = collect_missing_distractor_words(main.id)
        self.assertEqual(sorted(missing), ["barn", "fence"])

        upsert_card(main.id, front="shed", back="barn", notes="Definition: shed")
        missing_after = collect_missing_distractor_words(main.id)
        self.assertEqual(missing_after, ["fence"])

    def test_collect_missing_treats_article_variants_as_covered(self) -> None:
        main = create_deck("Legal", "legal", "ua-en", source="ai")
        card_id = upsert_card(main.id, front="питання", back="issue", notes="Definition: topic")
        upsert_quiz_question(
            card_id=card_id,
            question_type="translation_recall",
            prompt_text="питання",
            example_sentence="",
            choices_pool=["the problem", "issue", "risk"],
            correct_english="issue",
            status="active",
        )
        distractor = get_or_create_distractor_deck("ua-en")
        upsert_card(distractor.id, front="проблема", back="problem", notes="Definition: difficulty")

        missing = collect_missing_distractor_words(main.id)

        self.assertEqual(missing, ["risk"])
        self.assertIsNotNone(lookup_english_metadata("the problem", "ua-en"))

    def test_distractor_deck_hidden_from_quiz_eligible_decks(self) -> None:
        create_deck("Hidden", QUIZ_DISTRACTOR_DECK_TAG, "ua-en", source="quiz_distractor")
        create_deck("Visible", "farm", "ua-en", source="ai")
        eligible_tags = {deck.tag for deck in list_quiz_eligible_decks()}
        self.assertNotIn(QUIZ_DISTRACTOR_DECK_TAG, eligible_tags)
        self.assertIn("farm", eligible_tags)

    def test_lookup_prefers_main_deck_over_distractor_deck(self) -> None:
        main = create_deck("Farm", "farm-lookup", "ua-en", source="ai")
        distractor = get_or_create_distractor_deck("ua-en")
        upsert_card(main.id, front="main-barn", back="barn", notes="Definition: main barn")
        upsert_card(distractor.id, front="alt-barn", back="barn", notes="Definition: distractor barn")
        meta = lookup_english_metadata("barn", "ua-en")
        self.assertIsNotNone(meta)
        assert meta is not None
        self.assertFalse(meta.from_distractor_deck)
        self.assertEqual(meta.definition, "main barn")

    def test_filter_user_decks(self) -> None:
        hidden = create_deck("Hidden", QUIZ_DISTRACTOR_DECK_TAG, "ua-en", source="quiz_distractor")
        visible = create_deck("Farm", "farm-filter", "ua-en", source="ai")
        filtered = filter_user_decks([hidden, visible])
        self.assertEqual(len(filtered), 1)
        self.assertTrue(is_quiz_distractor_deck(hidden))
        self.assertFalse(is_quiz_distractor_deck(visible))

    def test_batch_upsert_distractor_cards_dedupe_by_english_not_front(self) -> None:
        distractor = create_deck(
            "Distractors",
            QUIZ_DISTRACTOR_DECK_TAG,
            "ua-en",
            source="quiz_distractor",
        )
        batch_upsert_cards(
            distractor.id,
            [
                {
                    "front": "проблема",
                    "back": "the problem",
                    "hint": "problem hint",
                    "notes": "Definition: difficulty",
                    "card_type": QUIZ_DISTRACTOR_CARD_TYPE,
                }
            ],
        )
        batch_upsert_cards(
            distractor.id,
            [
                {
                    "front": "проблема",
                    "back": "issue",
                    "hint": "issue hint",
                    "notes": "Definition: topic",
                    "card_type": QUIZ_DISTRACTOR_CARD_TYPE,
                }
            ],
        )

        cards = list_cards(distractor.id)
        backs = sorted(card.back for card in cards)
        self.assertEqual(backs, ["issue", "the problem"])
