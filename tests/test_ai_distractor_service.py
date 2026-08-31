from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from quicklingo.learning.ai_deck.models import AiDeckParams
from quicklingo.learning.corpus_analysis import CorpusCandidate
from quicklingo.learning.quiz.ai_distractor_service import AiDistractorService, _RateLimitStopped
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
                retry_on_rate_limit=False,
                rate_limit_padding_sec=0,
                rate_limit_wait_cb=None,
                progress_cb=None,
            )

        self.assertEqual(call_sizes, [2, 1, 1])
        self.assertEqual(len(cards), 2)


if __name__ == "__main__":
    unittest.main()
