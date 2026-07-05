import asyncio
import json

from PySide6.QtCore import QThread, Signal

from quicklingo.db import learning
from quicklingo.learning.card_prompt import enrich_card_fields
from quicklingo.learning.corpus_analysis import (
    AnalysisSummary,
    CorpusCandidate,
    build_analysis_prompt,
    format_summary_text,
    parse_analysis_response,
    select_candidates,
)
from quicklingo.learning.deck_corpus import pending_corpus_records
from quicklingo.learning.difficult_words import compute_difficult_words
from quicklingo.i18n import tr
from quicklingo.logging.ai_requests import ai_request_scope
from quicklingo.providers.registry import ModelEntry


class CorpusAnalysisWorker(QThread):
    finished = Signal(int, str)
    error = Signal(str)
    progress = Signal(str)
    cancelled = Signal()

    def __init__(
        self,
        records: list,
        *,
        tag: str,
        direction: str,
        model_entry: ModelEntry,
        deck_display_name: str = "Corpus",
        max_candidates: int = 120,
        batch_size: int = 40,
        starred_only: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._records = records
        self._tag = tag
        self._direction = direction
        self._deck_display_name = deck_display_name
        self._model_entry = model_entry
        self._max_candidates = max_candidates
        self._batch_size = batch_size
        self._starred_only = starred_only
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True
        self.requestInterruption()

    def run(self) -> None:
        try:
            deck_id, summary_text = asyncio.run(self._analyze())
        except asyncio.CancelledError:
            self.cancelled.emit()
            return
        except Exception as exc:
            if self._cancelled:
                self.cancelled.emit()
                return
            self.error.emit(str(exc))
            return
        if self._cancelled:
            self.cancelled.emit()
            return
        self.finished.emit(deck_id, summary_text)

    async def _analyze(self) -> tuple[int, str]:
        records = pending_corpus_records(
            self._records,
            tag=self._tag,
            direction=self._direction,
        )
        candidates = select_candidates(
            records,
            max_candidates=self._max_candidates,
            starred_only=self._starred_only,
        )
        difficult = compute_difficult_words(records)
        deck = learning.get_or_create_deck(
            name=self._tag or self._deck_display_name,
            tag=self._tag,
            direction=self._direction,
        )

        if not candidates:
            summary = format_summary_text(
                AnalysisSummary([], 20, 0, tr("learning.summary_no_records")),
                difficult=difficult,
            )
            learning.update_deck_summary(deck.id, summary)
            return deck.id, summary

        all_cards: list[dict] = []
        summaries: list[AnalysisSummary] = []
        batches = [
            candidates[i : i + self._batch_size]
            for i in range(0, len(candidates), self._batch_size)
        ]
        for index, batch in enumerate(batches, start=1):
            if self._cancelled:
                raise asyncio.CancelledError()
            self.progress.emit(tr("learning.analysis_batch", index=index, total=len(batches)))
            cards, summary = await self._analyze_batch(batch)
            all_cards.extend(cards)
            summaries.append(summary)

        merged = AnalysisSummary(
            themes=_merge_unique(s.themes for s in summaries),
            recommended_daily_count=max(
                (s.recommended_daily_count for s in summaries), default=20
            ),
            total_unique=len(all_cards),
            comment=next((s.comment for s in summaries if s.comment), ""),
        )

        prepared: list[dict] = []
        sources = {candidate.record_id: candidate.source_text for candidate in candidates}
        from quicklingo.config.loader import resolve_learning_direction

        kind = resolve_learning_direction(self._direction)
        batch_english: list[str] = []
        for card in all_cards:
            front = str(card.get("front", "")).strip()
            back = str(card.get("back", "")).strip()
            if not front or not back:
                continue
            term = back if kind == "ua-en" else front
            if term:
                batch_english.append(term)
        db_pool = learning.list_quiz_english_words()
        quiz_pool = list(dict.fromkeys(batch_english + db_pool))
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
            source_text = ""
            record_id = item.get("source_record_id")
            try:
                if record_id is not None:
                    source_text = sources.get(int(record_id), "")
            except (TypeError, ValueError):
                source_text = ""
            prepared.append(
                enrich_card_fields(
                    item,
                    direction=self._direction,
                    source_text=source_text,
                    quiz_pool=quiz_pool,
                )
            )

        learning.batch_upsert_cards(deck.id, prepared)
        summary_text = format_summary_text(merged, difficult=difficult)
        learning.update_deck_summary(deck.id, summary_text)
        return deck.id, summary_text

    async def _analyze_batch(
        self, batch: list[CorpusCandidate]
    ) -> tuple[list[dict], AnalysisSummary]:
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

    async def _request_batch(
        self, batch: list[CorpusCandidate]
    ) -> tuple[list[dict], AnalysisSummary]:
        prompt = build_analysis_prompt(batch, tag=self._tag, direction=self._direction)
        with ai_request_scope("learning.corpus_analysis"):
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
