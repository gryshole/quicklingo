from __future__ import annotations

import json
import re
from dataclasses import dataclass

from quicklingo.db import history
from quicklingo.learning.difficult_words import DifficultItem, compute_difficult_words

_WORD_RE = re.compile(r"[\w']+", re.UNICODE)


@dataclass
class CorpusCandidate:
    source_text: str
    result_text: str
    record_id: int
    reason: str
    priority: int


@dataclass
class AnalysisSummary:
    themes: list[str]
    recommended_daily_count: int
    total_unique: int
    comment: str


def select_candidates(
    records: list[history.TranslationRecord],
    *,
    max_candidates: int = 120,
    starred_only: bool = False,
) -> list[CorpusCandidate]:
    if starred_only:
        records = [r for r in records if r.is_starred]
    if not records:
        return []

    seen_hash: set[str] = set()
    deduped: list[history.TranslationRecord] = []
    for record in records:
        key = record.content_hash or _normalize_source(record.source_text)
        if key in seen_hash:
            continue
        seen_hash.add(key)
        deduped.append(record)

    candidates: dict[int, CorpusCandidate] = {}

    for record in deduped:
        if record.is_starred:
            candidates[record.id] = CorpusCandidate(
                source_text=record.source_text.strip(),
                result_text=record.result_text.strip(),
                record_id=record.id,
                reason="starred",
                priority=5,
            )

    for item in compute_difficult_words(deduped):
        for record in deduped:
            if item.kind == "phrase" and _normalize_source(record.source_text) == _normalize_source(
                item.example_source
            ):
                candidates.setdefault(
                    record.id,
                    CorpusCandidate(
                        source_text=record.source_text.strip(),
                        result_text=record.result_text.strip(),
                        record_id=record.id,
                        reason="difficult_phrase",
                        priority=4,
                    ),
                )
                break
            if item.kind == "word" and item.term in record.source_text.lower():
                candidates.setdefault(
                    record.id,
                    CorpusCandidate(
                        source_text=record.source_text.strip(),
                        result_text=record.result_text.strip(),
                        record_id=record.id,
                        reason="difficult_word",
                        priority=3,
                    ),
                )
                break

    direction = deduped[0].direction if deduped else "ua-en"
    top_words = _top_tokens_from_records(deduped, top_n=80)
    for record in deduped:
        if record.id in candidates:
            continue
        tokens = set(_WORD_RE.findall(record.source_text.lower()))
        if tokens & top_words:
            candidates[record.id] = CorpusCandidate(
                source_text=record.source_text.strip(),
                result_text=record.result_text.strip(),
                record_id=record.id,
                reason="frequency",
                priority=2,
            )

    for record in deduped:
        if record.id in candidates:
            continue
        candidates[record.id] = CorpusCandidate(
            source_text=record.source_text.strip(),
            result_text=record.result_text.strip(),
            record_id=record.id,
            reason="corpus",
            priority=1,
        )

    ordered = sorted(candidates.values(), key=lambda c: (-c.priority, c.record_id))
    return ordered[: max(1, max_candidates)]


def build_analysis_prompt(candidates: list[CorpusCandidate], *, tag: str, direction: str) -> str:
    lines = [
        "You analyze translation history from a TV series / immersion corpus.",
        f"Corpus tag: {tag}",
        f"Direction: {direction}",
        "Return ONLY valid JSON with this schema:",
        '{"cards":[{"front":"...","back":"...","context":"...","priority":1-5,"source_record_id":123}],',
        '"summary":{"themes":["..."],"recommended_daily_count":20,"total_unique":0,"comment":"..."}}',
        "Create concise flashcards from the items below. front=term in source language, back=translation.",
        "Merge duplicates. priority 5 = most important for a learner.",
        "Items:",
    ]
    for index, candidate in enumerate(candidates, start=1):
        lines.append(
            f"{index}. id={candidate.record_id} [{candidate.reason}] "
            f"source={candidate.source_text!r} result={candidate.result_text!r}"
        )
    return "\n".join(lines)


def parse_analysis_response(raw: str) -> tuple[list[dict], AnalysisSummary]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    data = json.loads(text)
    cards = data.get("cards", [])
    summary_raw = data.get("summary", {})
    summary = AnalysisSummary(
        themes=[str(t) for t in summary_raw.get("themes", []) if str(t).strip()],
        recommended_daily_count=int(summary_raw.get("recommended_daily_count", 20)),
        total_unique=int(summary_raw.get("total_unique", len(cards))),
        comment=str(summary_raw.get("comment", "")),
    )
    if not isinstance(cards, list):
        cards = []
    return cards, summary


def format_summary_text(summary: AnalysisSummary, *, difficult: list[DifficultItem]) -> str:
    lines = []
    if summary.comment:
        lines.append(summary.comment)
    if summary.themes:
        lines.append("Themes: " + ", ".join(summary.themes))
    lines.append(f"Recommended daily: {summary.recommended_daily_count}")
    lines.append(f"Unique items: {summary.total_unique}")
    if difficult:
        preview = ", ".join(item.term for item in difficult[:12])
        lines.append(f"Difficult (local): {preview}")
    return "\n".join(lines)


def _normalize_source(text: str) -> str:
    return " ".join(text.split()).lower()


def _top_tokens_from_records(
    records: list[history.TranslationRecord], *, top_n: int
) -> set[str]:
    from collections import Counter

    counter: Counter[str] = Counter()
    for record in records:
        for token in _WORD_RE.findall(record.source_text.lower()):
            if len(token) > 1:
                counter[token] += 1
    return {word for word, _ in counter.most_common(max(1, top_n))}
