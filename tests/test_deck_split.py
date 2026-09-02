from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from quicklingo.db import connection as db_connection
from quicklingo.db.history_schema import init_db
from quicklingo.db.learning import create_deck, get_card, list_cards, upsert_card
from quicklingo.db.learning_models import LearningCard, LearningDeck
from quicklingo.learning.deck_split.move_cards import move_cards_to_deck
from quicklingo.learning.deck_split.parse import match_fronts_to_card_ids, parse_deck_split_response
from quicklingo.learning.deck_split.prompts import build_deck_split_user_message, get_deck_split_system_prompt
from quicklingo.learning.quiz.distractor_deck import QUIZ_DISTRACTOR_DECK_TAG


class DeckSplitParseTests(unittest.TestCase):
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

    def test_load_json_rejects_empty_response(self) -> None:
        with self.assertRaisesRegex(ValueError, "empty response"):
            parse_deck_split_response(
                "",
                deck_id=1,
                source_tag="tv",
                direction="en-ua",
            )

    def test_load_json_rejects_garbage_without_corpus_salvage(self) -> None:
        with self.assertRaisesRegex(ValueError, "deck-split JSON"):
            parse_deck_split_response(
                "not json at all",
                deck_id=1,
                source_tag="tv",
                direction="en-ua",
            )

    def test_parse_options_and_match_fronts(self) -> None:
        raw = """
        {
          "summary": "Mixed themes.",
          "options": [
            {
              "id": "a",
              "title": "Politics",
              "tag": "tv-politics",
              "deck_name": "TV politics",
              "rationale": "Government words.",
              "fronts": ["compliance", "traitor"]
            }
          ]
        }
        """
        with patch("quicklingo.learning.deck_split.parse.get_feature", return_value={
            "min_deck_cards": 25,
            "max_options": 4,
            "min_subgroup_cards": 2,
            "split_prompt_template": "",
        }):
            deck = create_deck("TV", "tv", "en-ua", source="ai")
            upsert_card(deck.id, front="compliance", back="згодність")
            upsert_card(deck.id, front="traitor", back="зрадник")
            result = parse_deck_split_response(
                raw,
                deck_id=deck.id,
                source_tag="tv",
                direction="en-ua",
            )
            self.assertEqual(result.summary, "Mixed themes.")
            self.assertEqual(len(result.options), 1)
            self.assertEqual(len(result.options[0].card_ids), 2)

    def test_match_fronts_to_card_ids(self) -> None:
        deck = create_deck("TV", "tv", "en-ua", source="ai")
        cid = upsert_card(deck.id, front="barn", back="сарай")
        ids, unmatched = match_fronts_to_card_ids(deck.id, ["barn", "missing"])
        self.assertEqual(ids, [cid])
        self.assertEqual(unmatched, ["missing"])


class DeckSplitPromptTests(unittest.TestCase):
    def test_system_prompt_en_ua_direction(self) -> None:
        with patch(
            "quicklingo.learning.deck_split.prompts.get_feature",
            return_value={
                "max_options": 3,
                "min_subgroup_cards": 10,
                "split_prompt_template": "",
            },
        ):
            prompt = get_deck_split_system_prompt("en-ua")
        self.assertIn('"summary"', prompt)
        self.assertNotIn("{max_options}", prompt)
        self.assertNotIn("{cards_description}", prompt)
        self.assertIn("0 to 3 split options", prompt)
        self.assertIn("at least 10 words", prompt)
        self.assertIn("English on the learning side (front)", prompt)
        self.assertIn('"front" field (English)', prompt)
        self.assertIn("character-exact", prompt)
        self.assertIn("exactly ONE option", prompt)
        self.assertIn("HARD limit", prompt)
        self.assertNotIn("TV series", prompt)

    def test_system_prompt_ua_en_direction(self) -> None:
        with patch(
            "quicklingo.learning.deck_split.prompts.get_feature",
            return_value={
                "max_options": 4,
                "min_subgroup_cards": 8,
                "split_prompt_template": "",
            },
        ):
            prompt = get_deck_split_system_prompt("ua-en")
        self.assertIn("Ukrainian on the learning side (front)", prompt)
        self.assertIn('"front" field (Ukrainian)', prompt)


class DeckSplitUserMessageTests(unittest.TestCase):
    def test_user_message_cards_only_front_and_back(self) -> None:
        deck = LearningDeck(
            id=1,
            name="TV",
            tag="tv",
            direction="en-ua",
            created_at="",
            analysis_summary="",
            source="ai",
        )
        card = LearningCard(
            id=1,
            deck_id=1,
            front="compliance",
            back="згодність",
            hint="іменник",
            notes="Definition: the act of following rules",
            context='["Example sentence."]',
        )
        raw = build_deck_split_user_message(deck, [card])
        payload = json.loads(raw)
        self.assertEqual(payload["cards"], [{"front": "compliance", "back": "згодність"}])


class MoveCardsTests(unittest.TestCase):
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

    def test_move_cards_to_new_deck(self) -> None:
        source = create_deck("TV", "tv", "en-ua", source="ai")
        card_id = upsert_card(source.id, front="barn", back="сарай")
        result = move_cards_to_deck([card_id], "tv-rural", "en-ua", deck_name="TV rural")
        self.assertEqual(result.moved, 1)
        self.assertEqual(result.skipped, 0)
        self.assertEqual(len(list_cards(source.id)), 0)
        from quicklingo.db.learning_decks import find_deck_by_tag

        target = find_deck_by_tag("tv-rural", "en-ua")
        self.assertIsNotNone(target)
        cards = list_cards(target.id)
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0].front, "barn")

    def test_skip_duplicate_front_in_target(self) -> None:
        source = create_deck("TV", "tv", "en-ua", source="ai")
        target = create_deck("TV2", "tv2", "en-ua", source="ai")
        upsert_card(target.id, front="barn", back="сарай")
        card_id = upsert_card(source.id, front="barn", back="інший")
        result = move_cards_to_deck([card_id], "tv2", "en-ua")
        self.assertEqual(result.moved, 0)
        self.assertEqual(result.skipped, 1)
        self.assertIsNotNone(get_card(card_id))

    def test_move_cards_bumps_content_updated_at(self) -> None:
        source = create_deck("TV", "tv", "en-ua", source="ai")
        card_id = upsert_card(source.id, front="barn", back="сарай")
        with db_connection.connection() as conn:
            before = conn.execute(
                "SELECT content_updated_at FROM learning_cards WHERE id = ?",
                (card_id,),
            ).fetchone()["content_updated_at"]
        move_cards_to_deck([card_id], "tv-rural", "en-ua", deck_name="TV rural")
        with db_connection.connection() as conn:
            after = conn.execute(
                "SELECT content_updated_at FROM learning_cards WHERE id = ?",
                (card_id,),
            ).fetchone()["content_updated_at"]
        self.assertNotEqual(before, after)

    def test_move_cards_updates_history_tags(self) -> None:
        from quicklingo.db.history_repository import save_translation
        from quicklingo.db.history_tags import get_translation_tag_names

        record_id = save_translation(
            "en-ua",
            "martyr",
            "мученик",
            "test",
            tags=["tv"],
        )
        source = create_deck("TV", "tv", "en-ua", source="ai")
        card_id = upsert_card(
            source.id,
            front="martyr",
            back="мученик",
            source_record_id=record_id,
        )
        move_cards_to_deck([card_id], "law-conflict", "en-ua", deck_name="law-conflict")

        with db_connection.connection() as conn:
            tags = get_translation_tag_names(conn, record_id)
        lowered = {tag.lower() for tag in tags}
        self.assertIn("law-conflict", lowered)
        self.assertNotIn("tv", lowered)

    def test_rejects_distractor_tag(self) -> None:
        source = create_deck("TV", "tv", "en-ua", source="ai")
        card_id = upsert_card(source.id, front="barn", back="сарай")
        result = move_cards_to_deck([card_id], QUIZ_DISTRACTOR_DECK_TAG, "en-ua")
        self.assertEqual(result.moved, 0)
        self.assertEqual(result.skipped, 1)
