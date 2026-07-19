from __future__ import annotations

import json
import re
from dataclasses import dataclass

from quicklingo.db import history
from quicklingo.learning.difficult_words import DifficultItem, compute_difficult_words
from quicklingo.learning.text_normalize import normalize_source as _normalize_source

_WORD_RE = re.compile(r"[\w']+", re.UNICODE)
_CARD_OBJECT_RE = re.compile(
    r'\{\s*"front"\s*:\s*"(?:[^"\\]|\\.)*"\s*,\s*"back"\s*:\s*"(?:[^"\\]|\\.)*"[^}]*\}',
    re.DOTALL,
)


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
    difficult_items: list[DifficultItem] | None = None,
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

    for item in difficult_items if difficult_items is not None else compute_difficult_words(deduped):
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
    from quicklingo.learning.card_prompt import build_card_analysis_prompt

    return build_card_analysis_prompt(candidates, tag=tag, direction=direction)


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _extract_json_object(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start : end + 1]
    return text


def _salvage_truncated_json(text: str, error: json.JSONDecodeError) -> dict:
    """Best-effort recovery when the model returns truncated JSON."""
    cut = text[: error.pos].rstrip() if error.pos else text.rstrip()
    while cut and cut[-1] not in "}]":
        cut = cut[:-1]
    cut = cut.rstrip().rstrip(",")
    if not cut or cut.endswith("{"):
        raise error
    if '"cards"' in cut:
        if not cut.rstrip().endswith("]"):
            cut += (
                '], "summary": {"themes": [], "recommended_daily_count": 20, '
                '"total_unique": 0, "comment": "Partial response (truncated)."}}'
            )
        elif cut.count("{") > cut.count("}"):
            cut += "}"
    elif cut.count("{") > cut.count("}"):
        cut += "}"
    return json.loads(cut)


def _salvage_cards_regex(text: str) -> dict:
    cards: list[dict] = []
    for match in _CARD_OBJECT_RE.finditer(text):
        try:
            card = json.loads(match.group(0))
        except json.JSONDecodeError:
            continue
        if isinstance(card, dict) and card.get("front") and card.get("back"):
            cards.append(card)
    if not cards:
        raise ValueError("no cards recovered")
    return {
        "cards": cards,
        "summary": {
            "themes": [],
            "recommended_daily_count": 20,
            "total_unique": len(cards),
            "comment": "Partial response (recovered cards).",
        },
    }


def _load_json_from_llm(raw: str) -> dict:
    text = _extract_json_object(_strip_code_fence(raw))
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        try:
            return _salvage_truncated_json(text, exc)
        except json.JSONDecodeError:
            return _salvage_cards_regex(text)


def parse_analysis_response(raw: str) -> tuple[list[dict], AnalysisSummary]:
    data = _load_json_from_llm(raw)
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
    from quicklingo.i18n import tr

    lines = []
    if summary.comment:
        lines.append(summary.comment)
    if summary.themes:
        lines.append(tr("learning.summary_themes", themes=", ".join(summary.themes)))
    lines.append(tr("learning.summary_daily", count=summary.recommended_daily_count))
    lines.append(tr("learning.summary_cards", count=summary.total_unique))
    if difficult:
        preview = ", ".join(item.term for item in difficult[:12])
        lines.append(tr("learning.summary_difficult", terms=preview))
    return "\n".join(lines)


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
