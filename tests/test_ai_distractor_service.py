from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from quicklingo.learning.ai_deck.models import AiDeckParams
from quicklingo.learning.corpus_analysis import CorpusCandidate
from quicklingo.learning.quiz.ai_distractor_service import (
    AiDistractorService,
    _RateLimitStopped,
    _prepare_distractor_cards_batch,
)
from quicklingo.providers.registry import ModelEntry


class AiDistractorServiceRateLimitTests(unittest.IsolatedAsyncioTestCase):
    async def test_rate_limit_splits_batch_before_retry(self) -> None:
        service = AiDistractorService()
        batch = [
            CorpusCandidate("a", "", 1, "ai_word_list", 3),
            CorpusCandidate("b", "", 2, "ai_word_list", 3),
        ]
        params = AiDeckParams(
            tag="__quiz-distractors",
            level="B1",
            topic_key="everyday",
            custom_topic="",
            lexicon_type="any",
            word_count=2,
            direction="ua-en",
            merge_existing=True,
        )
        model_entry = ModelEntry(
            model_id="test",
            display_name="test",
            provider=MagicMock(),
            api_provider="test",
        )

        call_sizes: list[int] = []

        async def fake_request(
            batch_arg: list[CorpusCandidate],
            _params: AiDeckParams,
            _model_entry: ModelEntry,
            *,
            cancel_flag=None,
        ) -> list[dict]:
            call_sizes.append(len(batch_arg))
            if len(batch_arg) > 1:
                raise _RateLimitStopped(5)
            return [{"front": "uk", "back": batch_arg[0].source_text or batch_arg[0].result_text}]

        with patch.object(service, "_request_batch", side_effect=fake_request):
            cards = await service._analyze_batch_with_rate_limit_retry(
                batch,
                params,
                model_entry,
                cancel_flag=None,
            )

        self.assertEqual(call_sizes, [2, 1, 1])
        self.assertEqual(len(cards), 2)


class DistractorCardPrepareTests(unittest.TestCase):
    def test_prepare_batch_uses_quiz_word_when_ai_back_differs(self) -> None:
        batch = [
            CorpusCandidate("", "problem", 1, "ai_word_list", 3),
            CorpusCandidate("", "strong point", 2, "ai_word_list", 3),
        ]
        cards = [
            {
                "front": "проблема",
                "back": "the problem",
                "hint": "іменник · issue",
                "notes": "Definition: a difficulty",
                "context": ["The problem is serious.", "We solved the problem.", "That problem remains."],
            },
            {
                "front": "сильна сторона",
                "back": "a strong suit",
                "hint": "іменник · skill",
                "notes": "Definition: a personal strength",
                "context": [
                    "Cooking is my strong suit.",
                    "Patience is a strong suit for teachers.",
                    "Public speaking became her strong suit.",
                ],
            },
        ]

        prepared = _prepare_distractor_cards_batch(cards, batch, "ua-en", "ua-en")

        self.assertEqual(len(prepared), 2)
        self.assertEqual(prepared[0]["back"], "problem")
        self.assertEqual(prepared[1]["back"], "strong point")

    def test_prepare_batch_pairs_by_index_when_synonym_back(self) -> None:
        batch = [CorpusCandidate("", "advantage", 1, "ai_word_list", 3)]
        cards = [
            {
                "front": "перевага",
                "back": "benefit",
                "hint": "іменник · edge",
                "notes": "Definition: a favorable condition",
                "context": [
                    "Speed is an advantage in sports.",
                    "They used every advantage they had.",
                    "Home advantage helped the team.",
                ],
            }
        ]

        prepared = _prepare_distractor_cards_batch(cards, batch, "ua-en", "ua-en")

        self.assertEqual(len(prepared), 1)
        self.assertEqual(prepared[0]["back"], "advantage")


if __name__ == "__main__":
    unittest.main()
