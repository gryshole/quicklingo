import asyncio

from PySide6.QtCore import QThread, Signal

from quicklingo.db import learning
from quicklingo.learning.corpus_analysis import (
    AnalysisSummary,
    build_analysis_prompt,
    format_summary_text,
    parse_analysis_response,
    select_candidates,
)
from quicklingo.learning.difficult_words import compute_difficult_words
from quicklingo.providers.registry import ModelEntry


class CorpusAnalysisWorker(QThread):
    finished = Signal(int, str)
    error = Signal(str)
    progress = Signal(str)

    def __init__(
        self,
        records: list,
        *,
        tag: str,
        direction: str,
        model_entry: ModelEntry,
        max_candidates: int = 120,
        batch_size: int = 40,
        starred_only: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._records = records
        self._tag = tag
        self._direction = direction
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
        except Exception as exc:
            if self._cancelled:
                return
            self.error.emit(str(exc))
            return
        if self._cancelled:
            return
        self.finished.emit(deck_id, summary_text)

    async def _analyze(self) -> tuple[int, str]:
        candidates = select_candidates(
            self._records,
            max_candidates=self._max_candidates,
            starred_only=self._starred_only,
        )
        difficult = compute_difficult_words(self._records)
        deck = learning.get_or_create_deck(
            name=self._tag or "Corpus",
            tag=self._tag,
            direction=self._direction,
        )

        if not candidates:
            summary = format_summary_text(
                AnalysisSummary([], 20, 0, "No records in corpus."),
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
            self.progress.emit(f"Batch {index}/{len(batches)}")
            prompt = build_analysis_prompt(batch, tag=self._tag, direction=self._direction)
            raw = await self._model_entry.provider.complete(
                "You are a language learning assistant. Output JSON only.",
                prompt,
                self._model_entry.model_id,
                temperature=0.3,
            )
            cards, summary = parse_analysis_response(raw)
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

        for card in all_cards:
            if self._cancelled:
                raise asyncio.CancelledError()
            front = str(card.get("front", "")).strip()
            back = str(card.get("back", "")).strip()
            if not front or not back:
                continue
            source_id = card.get("source_record_id")
            try:
                source_id = int(source_id) if source_id is not None else None
            except (TypeError, ValueError):
                source_id = None
            learning.upsert_card(
                deck.id,
                front=front,
                back=back,
                context=str(card.get("context", "")),
                priority=int(card.get("priority", 3)),
                source_record_id=source_id,
            )

        summary_text = format_summary_text(merged, difficult=difficult)
        learning.update_deck_summary(deck.id, summary_text)
        return deck.id, summary_text


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
