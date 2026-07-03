import asyncio
import json

from PySide6.QtCore import QThread, Signal

from quicklingo.db import learning
from quicklingo.learning.ai_deck.candidates import words_to_candidates
from quicklingo.learning.ai_deck.card_prompt import build_ai_word_card_prompt, format_deck_summary
from quicklingo.learning.ai_deck.models import AiDeckParams
from quicklingo.learning.ai_deck.word_list_parser import parse_word_list_response
from quicklingo.learning.ai_deck.word_list_prompt import build_word_list_prompt
from quicklingo.learning.card_prompt import enrich_card_fields
from quicklingo.learning.corpus_analysis import AnalysisSummary, parse_analysis_response
from quicklingo.logging.ai_requests import ai_request_scope
from quicklingo.providers.registry import ModelEntry


class AiDeckGeneratorWorker(QThread):
    finished = Signal(int, str, dict)
    error = Signal(str)
    progress = Signal(str)

    def __init__(
        self,
        params: AiDeckParams,
        *,
        model_entry: ModelEntry,
        batch_size: int = 10,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._params = params
        self._model_entry = model_entry
        self._batch_size = max(1, batch_size)
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True
        self.requestInterruption()

    def run(self) -> None:
        try:
            deck_id, summary_text, media_meta = asyncio.run(self._generate())
        except Exception as exc:
            if self._cancelled or self.isInterruptionRequested():
                return
            self.error.emit(str(exc))
            return
        if self._cancelled or self.isInterruptionRequested():
            return
        self.finished.emit(deck_id, summary_text, media_meta)

    async def _generate(self) -> tuple[int, str, dict]:
        params = self._params
        tag = params.normalized_tag()

        self.progress.emit("Step 1/2: Generating word list…")
        words = await self._fetch_word_list()
        if self._cancelled:
            raise asyncio.CancelledError()

        if params.merge_existing:
            deck = learning.get_or_create_deck(name=tag, tag=tag, direction=params.direction)
        else:
            deck = learning.create_deck(name=tag, tag=tag, direction=params.direction, source="ai")

        candidates = words_to_candidates(words, direction=params.direction)
        if not candidates:
            summary = format_deck_summary(params, word_count=0)
            learning.update_deck_summary(deck.id, summary)
            return deck.id, summary, {"card_ids": [], "imageable": {}, "image_prompts": {}}

        all_cards: list[dict] = []
        summaries: list[AnalysisSummary] = []
        batches = [
            candidates[index : index + self._batch_size]
            for index in range(0, len(candidates), self._batch_size)
        ]
        for index, batch in enumerate(batches, start=1):
            if self._cancelled:
                raise asyncio.CancelledError()
            self.progress.emit(f"Step 2/2: Batch {index}/{len(batches)}")
            cards, summary = await self._analyze_batch(batch)
            all_cards.extend(cards)
            summaries.append(summary)

        from quicklingo.config.loader import resolve_learning_direction

        kind = resolve_learning_direction(params.direction)
        batch_english: list[str] = []
        for card in all_cards:
            front = str(card.get("front", "")).strip()
            back = str(card.get("back", "")).strip()
            if not front or not back:
                continue
            term = back if kind == "ua-en" else front
            if term:
                batch_english.append(term)
        quiz_pool = list(dict.fromkeys(batch_english + learning.list_quiz_english_words()))

        prepared: list[dict] = []
        for card in all_cards:
            if self._cancelled:
                raise asyncio.CancelledError()
            front = str(card.get("front", "")).strip()
            back = str(card.get("back", "")).strip()
            if not front or not back:
                continue
            item = dict(card)
            if not item.get("imageable"):
                item["image_prompt"] = ""
            prepared.append(
                enrich_card_fields(
                    item,
                    direction=params.direction,
                    source_text="",
                    quiz_pool=quiz_pool,
                )
            )

        card_ids = learning.batch_upsert_cards(deck.id, prepared)
        imageable: dict[int, bool] = {}
        image_prompts: dict[int, str] = {}
        for card_id, card in zip(card_ids, prepared[: len(card_ids)]):
            imageable[card_id] = bool(card.get("imageable"))
            prompt = str(card.get("image_prompt", "")).strip()
            if prompt:
                image_prompts[card_id] = prompt

        merged = AnalysisSummary(
            themes=_merge_unique(s.themes for s in summaries),
            recommended_daily_count=max(
                (s.recommended_daily_count for s in summaries), default=20
            ),
            total_unique=len(prepared),
            comment=next((s.comment for s in summaries if s.comment), ""),
        )
        summary_text = format_deck_summary(params, word_count=len(prepared))
        if merged.themes or merged.comment:
            summary_text += f"\nThemes: {', '.join(merged.themes)}. {merged.comment}".strip()
        learning.update_deck_summary(deck.id, summary_text)
        media_meta = {
            "card_ids": card_ids,
            "imageable": imageable,
            "image_prompts": image_prompts,
        }
        return deck.id, summary_text, media_meta

    async def _fetch_word_list(self) -> list[str]:
        prompt = build_word_list_prompt(self._params)
        with ai_request_scope("learning.ai_deck.word_list"):
            raw = await self._model_entry.provider.complete(
                "You are a vocabulary curator for language learners. Output JSON only.",
                prompt,
                self._model_entry.model_id,
                temperature=0.4,
            )
        words = parse_word_list_response(raw, expected_count=self._params.word_count)
        return words[: self._params.word_count]

    async def _analyze_batch(self, batch) -> tuple[list[dict], AnalysisSummary]:
        try:
            return await self._request_batch(batch)
        except (json.JSONDecodeError, ValueError):
            if len(batch) <= 1:
                raise
            mid = len(batch) // 2
            left_cards, left_summary = await self._analyze_batch(batch[:mid])
            right_cards, right_summary = await self._analyze_batch(batch[mid:])
            merged_summary = AnalysisSummary(
                themes=_merge_unique([left_summary.themes, right_summary.themes]),
                recommended_daily_count=max(
                    left_summary.recommended_daily_count,
                    right_summary.recommended_daily_count,
                ),
                total_unique=len(left_cards) + len(right_cards),
                comment=left_summary.comment or right_summary.comment,
            )
            return left_cards + right_cards, merged_summary

    async def _request_batch(self, batch) -> tuple[list[dict], AnalysisSummary]:
        prompt = build_ai_word_card_prompt(batch, self._params)
        with ai_request_scope("learning.ai_deck.cards"):
            raw = await self._model_entry.provider.complete(
                "You are a language learning assistant creating flashcards for active recall. "
                "The learner must recall back without spoilers in hint. Output JSON only.",
                prompt,
                self._model_entry.model_id,
                temperature=0.3,
            )
        return parse_analysis_response(raw)


def _merge_unique(groups) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for group in groups:
        for item in group:
            key = item.lower()
            if key not in seen:
                seen.add(key)
                result.append(item)
    return result
