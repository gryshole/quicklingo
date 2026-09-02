from __future__ import annotations

from collections.abc import Callable

from quicklingo.db import learning
from quicklingo.i18n.translator import TranslatableError
from quicklingo.learning.deck_split.models import DeckSplitAnalysisResult
from quicklingo.learning.deck_split.parse import parse_deck_split_response
from quicklingo.learning.deck_split.prompts import (
    build_deck_split_user_message,
    get_deck_split_system_prompt,
)
from quicklingo.logging.ai_requests import ai_request_scope
from quicklingo.providers.registry import ModelEntry

_RATE_LIMIT_KEYS = frozenset(
    {
        "errors.api_rate_limit",
        "errors.api_rate_limit_rpm",
        "errors.api_rate_limit_tpm",
        "errors.anthropic_rate_limit",
        "errors.gemini_rate_limit",
    }
)


class AiDeckSplitService:
    async def analyze_deck(
        self,
        deck_id: int,
        model_entry: ModelEntry,
        *,
        user_note: str = "",
        cancel_flag: Callable[[], bool] | None = None,
    ) -> DeckSplitAnalysisResult:
        if cancel_flag and cancel_flag():
            raise RuntimeError("cancelled")
        deck = learning.get_deck(deck_id)
        if deck is None:
            raise ValueError(f"Deck {deck_id} not found")
        cards = learning.list_cards(deck_id)
        if not cards:
            raise ValueError("Deck has no cards")

        system = get_deck_split_system_prompt(deck.direction)
        user = build_deck_split_user_message(deck, cards, user_note=user_note)

        with ai_request_scope("learning.deck_split"):
            try:
                raw = await model_entry.provider.complete(
                    system,
                    user,
                    model_entry.model_id,
                    temperature=0.2,
                )
            except TranslatableError as exc:
                if exc.key in _RATE_LIMIT_KEYS:
                    raise
                raise

        return parse_deck_split_response(
            raw,
            deck_id=deck_id,
            source_tag=deck.tag,
            direction=deck.direction,
        )
