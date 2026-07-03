from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass

from quicklingo.db import learning
from quicklingo.learning.card_prompt import serialize_context
from quicklingo.learning.quiz.card_eligibility_fix import (
    DEFAULT_FIX_EXAMPLES_SYSTEM,
    _template_examples,
    build_fix_examples_prompt,
    list_ineligible_cards,
    parse_examples_response,
    pick_quiz_eligible_examples,
)
from quicklingo.learning.quiz.eligibility import is_quiz_eligible
from quicklingo.learning.quiz.normalize import card_to_quiz_word
from quicklingo.logging.ai_requests import ai_request_scope, log_validation_retry
from quicklingo.providers.registry import ModelEntry

_MAX_RETRIES = 3


@dataclass(frozen=True)
class QuizCardFixResult:
    fixed: int
    failed: int
    total: int


class AiQuizCardFixService:
    async def fix_ineligible_for_deck(
        self,
        deck_id: int,
        model_entry: ModelEntry,
        *,
        progress_cb: Callable[[str], None] | None = None,
        cancel_flag: Callable[[], bool] | None = None,
    ) -> QuizCardFixResult:
        pending = list_ineligible_cards(deck_id)
        fixed = 0
        failed = 0
        total = len(pending)

        for index, item in enumerate(pending, start=1):
            if cancel_flag and cancel_flag():
                break
            if progress_cb:
                progress_cb(f"{index}/{total}: {item.word.english}")
            if await self._fix_card(item.card, item.word, deck_id, model_entry, cancel_flag=cancel_flag):
                fixed += 1
            else:
                failed += 1

        return QuizCardFixResult(fixed=fixed, failed=failed, total=total)

    async def _fix_card(
        self,
        card: learning.LearningCard,
        word,
        deck_id: int,
        model_entry: ModelEntry,
        *,
        cancel_flag: Callable[[], bool] | None = None,
    ) -> bool:
        deck = learning.get_deck(deck_id)
        if deck is None:
            return False
        direction = deck.direction

        for attempt in range(_MAX_RETRIES):
            if cancel_flag and cancel_flag():
                return False
            if attempt == 0:
                candidates = _template_examples(word.english)
            else:
                purpose = f"learning.quiz.fix_examples.retry{attempt}"
                with ai_request_scope(purpose):
                    raw = await model_entry.provider.complete(
                        DEFAULT_FIX_EXAMPLES_SYSTEM,
                        build_fix_examples_prompt(word),
                        model_entry.model_id,
                        temperature=0.35,
                    )
                candidates = parse_examples_response(raw)
            picked = pick_quiz_eligible_examples(word, candidates)
            if len(picked) < 3:
                if attempt > 0:
                    log_validation_retry(
                        purpose=purpose,
                        detail=f"card={word.english} eligible_examples={len(picked)}",
                    )
                await asyncio.sleep(0)
                continue
            context = serialize_context(picked, direction=direction)
            learning.update_card(card.id, context=context)
            updated = learning.get_card(card.id)
            if updated is None:
                return False
            if is_quiz_eligible(updated, card_to_quiz_word(updated, direction)):
                return True
        return False
