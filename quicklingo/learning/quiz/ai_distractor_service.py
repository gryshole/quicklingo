from __future__ import annotations

import asyncio
import json
from collections.abc import Callable

from quicklingo.db import learning
from quicklingo.i18n import tr
from quicklingo.i18n.translator import TranslatableError
from quicklingo.learning.ai_deck.candidates import words_to_candidates
from quicklingo.learning.ai_deck.card_prompt import build_ai_word_card_prompt
from quicklingo.learning.ai_deck.models import AiDeckParams
from quicklingo.learning.ai_deck.system_prompts import CARD_BATCH_SYSTEM_PROMPT
from quicklingo.learning.card_prompt import enrich_card_fields
from quicklingo.learning.corpus_analysis import CorpusCandidate, parse_analysis_response
from quicklingo.learning.quiz.distractor_deck import (
    QUIZ_DISTRACTOR_CARD_TYPE,
    QUIZ_DISTRACTOR_DECK_TAG,
)
from quicklingo.learning.quiz.distractor_generation_outcome import DistractorGenerationOutcome
from quicklingo.logging.ai_requests import ai_request_scope
from quicklingo.providers.api_errors import parse_openai_compat_error
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


class _RateLimitStopped(Exception):
    def __init__(self, retry_seconds: int | None = None) -> None:
        self.retry_seconds = retry_seconds
        super().__init__()


class AiDistractorService:
    async def generate_for_words(
        self,
        source_deck_id: int,
        words: list[str],
        model_entry: ModelEntry,
        *,
        progress_cb: Callable[[str], None] | None = None,
        cancel_flag: Callable[[], bool] | None = None,
        word_delay_sec: float = 0,
        batch_size: int = 5,
        retry_on_rate_limit: bool = False,
        rate_limit_padding_sec: float = 2.0,
        rate_limit_wait_cb: Callable[[int], None] | None = None,
    ) -> DistractorGenerationOutcome:
        source_deck = learning.get_deck(source_deck_id)
        if source_deck is None:
            raise ValueError(f"Deck {source_deck_id} not found")
        if not words:
            return DistractorGenerationOutcome(
                created=0, cancelled=False, rate_limited=False, total_attempted=0
            )

        from quicklingo.config.loader import resolve_learning_direction

        kind = resolve_learning_direction(source_deck.direction)
        distractor_deck = learning.get_or_create_distractor_deck(source_deck.direction)
        params = AiDeckParams(
            tag=QUIZ_DISTRACTOR_DECK_TAG,
            level="B1",
            topic_key="everyday",
            custom_topic="",
            lexicon_type="any",
            word_count=len(words),
            direction=source_deck.direction,
            merge_existing=True,
        )
        candidates = words_to_candidates(words, direction=source_deck.direction)
        total = len(candidates)
        batch_size = max(1, batch_size)
        batches = [
            candidates[index : index + batch_size]
            for index in range(0, len(candidates), batch_size)
        ]
        created = 0
        rate_limited = False
        cancelled = False
        retry_seconds: int | None = None

        for batch_index, batch in enumerate(batches, start=1):
            if cancel_flag and cancel_flag():
                cancelled = True
                break
            words_done = min(batch_index * batch_size, total)
            if progress_cb:
                progress_cb(
                    tr(
                        "learning.quiz_distractor_cards_progress_batch",
                        words_done=words_done,
                        total=total,
                        batch=batch_index,
                        batch_total=len(batches),
                    )
                )
            try:
                cards = await self._analyze_batch_with_rate_limit_retry(
                    batch,
                    params,
                    model_entry,
                    cancel_flag=cancel_flag,
                    retry_on_rate_limit=retry_on_rate_limit,
                    rate_limit_padding_sec=rate_limit_padding_sec,
                    rate_limit_wait_cb=rate_limit_wait_cb,
                    progress_cb=progress_cb,
                )
            except _RateLimitStopped as stopped:
                if cancel_flag and cancel_flag():
                    cancelled = True
                    break
                rate_limited = True
                retry_seconds = stopped.retry_seconds
                break
            except (json.JSONDecodeError, ValueError):
                if progress_cb:
                    progress_cb(tr("learning.quiz_distractor_cards_batch_parse_failed"))
                continue

            prepared = _prepare_distractor_cards_batch(
                cards,
                batch,
                source_deck.direction,
                kind,
            )
            if prepared:
                learning.batch_upsert_cards(distractor_deck.id, prepared)
                created += len(prepared)
            elif progress_cb:
                if cards:
                    progress_cb(tr("learning.quiz_distractor_cards_batch_no_match"))
                else:
                    progress_cb(tr("learning.quiz_distractor_cards_batch_empty_response"))

            if batch_index < len(batches) and word_delay_sec > 0:
                await asyncio.sleep(word_delay_sec)

        return DistractorGenerationOutcome(
            created=created,
            cancelled=cancelled,
            rate_limited=rate_limited,
            total_attempted=total,
            retry_seconds=retry_seconds,
        )

    async def _analyze_batch_with_rate_limit_retry(
        self,
        batch: list[CorpusCandidate],
        params: AiDeckParams,
        model_entry: ModelEntry,
        *,
        cancel_flag: Callable[[], bool] | None,
        retry_on_rate_limit: bool,
        rate_limit_padding_sec: float,
        rate_limit_wait_cb: Callable[[int], None] | None,
        progress_cb: Callable[[str], None] | None,
    ) -> list[dict]:
        try:
            return await self._request_batch(batch, params, model_entry, cancel_flag=cancel_flag)
        except _RateLimitStopped as stopped:
            if len(batch) > 1:
                mid = len(batch) // 2
                left_cards = await self._analyze_batch_with_rate_limit_retry(
                    batch[:mid],
                    params,
                    model_entry,
                    cancel_flag=cancel_flag,
                    retry_on_rate_limit=retry_on_rate_limit,
                    rate_limit_padding_sec=rate_limit_padding_sec,
                    rate_limit_wait_cb=rate_limit_wait_cb,
                    progress_cb=progress_cb,
                )
                right_cards = await self._analyze_batch_with_rate_limit_retry(
                    batch[mid:],
                    params,
                    model_entry,
                    cancel_flag=cancel_flag,
                    retry_on_rate_limit=retry_on_rate_limit,
                    rate_limit_padding_sec=rate_limit_padding_sec,
                    rate_limit_wait_cb=rate_limit_wait_cb,
                    progress_cb=progress_cb,
                )
                return left_cards + right_cards
            if not retry_on_rate_limit:
                raise
            await self._wait_rate_limit(
                stopped,
                cancel_flag=cancel_flag,
                rate_limit_padding_sec=rate_limit_padding_sec,
                rate_limit_wait_cb=rate_limit_wait_cb,
                progress_cb=progress_cb,
            )
            return await self._analyze_batch_with_rate_limit_retry(
                batch,
                params,
                model_entry,
                cancel_flag=cancel_flag,
                retry_on_rate_limit=retry_on_rate_limit,
                rate_limit_padding_sec=rate_limit_padding_sec,
                rate_limit_wait_cb=rate_limit_wait_cb,
                progress_cb=progress_cb,
            )
        except (json.JSONDecodeError, ValueError):
            if len(batch) <= 1:
                raise
            mid = len(batch) // 2
            left_cards = await self._analyze_batch_with_rate_limit_retry(
                batch[:mid],
                params,
                model_entry,
                cancel_flag=cancel_flag,
                retry_on_rate_limit=retry_on_rate_limit,
                rate_limit_padding_sec=rate_limit_padding_sec,
                rate_limit_wait_cb=rate_limit_wait_cb,
                progress_cb=progress_cb,
            )
            right_cards = await self._analyze_batch_with_rate_limit_retry(
                batch[mid:],
                params,
                model_entry,
                cancel_flag=cancel_flag,
                retry_on_rate_limit=retry_on_rate_limit,
                rate_limit_padding_sec=rate_limit_padding_sec,
                rate_limit_wait_cb=rate_limit_wait_cb,
                progress_cb=progress_cb,
            )
            return left_cards + right_cards

    async def _wait_rate_limit(
        self,
        stopped: _RateLimitStopped,
        *,
        cancel_flag: Callable[[], bool] | None,
        rate_limit_padding_sec: float,
        rate_limit_wait_cb: Callable[[int], None] | None,
        progress_cb: Callable[[str], None] | None,
    ) -> None:
        wait_seconds = float(stopped.retry_seconds or 30) + max(0.0, rate_limit_padding_sec)
        remaining_sleep = wait_seconds
        while remaining_sleep > 0:
            if cancel_flag and cancel_flag():
                raise _RateLimitStopped()
            wait_display = max(1, int(remaining_sleep))
            if rate_limit_wait_cb is not None:
                rate_limit_wait_cb(wait_display)
            elif progress_cb:
                progress_cb(
                    tr(
                        "learning.quiz_distractor_cards_rate_limit_wait",
                        seconds=wait_display,
                    )
                )
            step = min(1.0, remaining_sleep)
            await asyncio.sleep(step)
            remaining_sleep -= step

    async def _request_batch(
        self,
        batch: list[CorpusCandidate],
        params: AiDeckParams,
        model_entry: ModelEntry,
        *,
        cancel_flag: Callable[[], bool] | None,
    ) -> list[dict]:
        if cancel_flag and cancel_flag():
            raise _RateLimitStopped()
        try:
            prompt = build_ai_word_card_prompt(batch, params)
            with ai_request_scope("learning.quiz.distractor_cards"):
                raw = await model_entry.provider.complete(
                    CARD_BATCH_SYSTEM_PROMPT,
                    prompt,
                    model_entry.model_id,
                    temperature=0.3,
                )
            cards, _summary = parse_analysis_response(raw)
            return cards
        except TranslatableError as exc:
            if exc.key in _RATE_LIMIT_KEYS:
                raise _RateLimitStopped(_retry_seconds_from_error(exc)) from exc
            raise


def _retry_seconds_from_error(exc: TranslatableError) -> int | None:
    if not exc.raw_detail:
        return None
    return parse_openai_compat_error(exc.raw_detail).retry_seconds


def _candidate_label(candidate: CorpusCandidate, kind: str) -> str:
    if kind == "ua-en":
        return candidate.result_text.strip() or candidate.source_text.strip()
    return candidate.source_text.strip() or candidate.result_text.strip()


def _card_english_term(card: dict, kind: str) -> str:
    front = str(card.get("front", "")).strip()
    back = str(card.get("back", "")).strip()
    if kind == "ua-en":
        return back
    return front


def _prepare_distractor_cards_batch(
    cards: list[dict],
    batch: list[CorpusCandidate],
    direction: str,
    kind: str,
) -> list[dict]:
    by_term: dict[str, dict] = {}
    for card in cards:
        term = _card_english_term(card, kind)
        if not term:
            continue
        key = term.lower()
        if key not in by_term:
            by_term[key] = card

    prepared: list[dict] = []
    for candidate in batch:
        word_label = _candidate_label(candidate, kind)
        if not word_label:
            continue
        card = by_term.get(word_label.lower())
        if card is None:
            continue
        item = _prepare_distractor_card([card], direction, kind, word_label)
        if item is not None:
            prepared.append(item)
    return prepared


def _prepare_distractor_card(
    cards: list[dict],
    direction: str,
    kind: str,
    word_label: str,
) -> dict | None:
    for card in cards:
        front = str(card.get("front", "")).strip()
        back = str(card.get("back", "")).strip()
        if not front or not back:
            continue
        term = back if kind == "ua-en" else front
        item = dict(card)
        if not item.get("imageable"):
            item["image_prompt"] = ""
        item["card_type"] = QUIZ_DISTRACTOR_CARD_TYPE
        quiz_pool = [term] if term else ([word_label] if word_label else [])
        return enrich_card_fields(
            item,
            direction=direction,
            source_text="",
            quiz_pool=quiz_pool,
        )
    return None
