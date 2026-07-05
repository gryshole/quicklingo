from __future__ import annotations

import re
from dataclasses import dataclass

from quicklingo.db import history, learning
from quicklingo.learning.text_normalize import normalize_source

_WORD_RE = re.compile(r"[\w']+", re.UNICODE)


@dataclass(frozen=True)
class DeckCorpusCoverage:
    source_record_ids: frozenset[int]
    fronts: frozenset[str]
    backs: frozenset[str]


def load_deck_corpus_coverage(tag: str, direction: str) -> DeckCorpusCoverage | None:
    deck = learning.find_deck_by_tag(tag, direction)
    if deck is None:
        return None
    cards = learning.list_cards(deck.id)
    source_record_ids = frozenset(
        card.source_record_id
        for card in cards
        if card.source_record_id is not None
    )
    fronts = frozenset(
        normalize_source(card.front) for card in cards if card.front.strip()
    )
    backs = frozenset(
        normalize_source(card.back) for card in cards if card.back.strip()
    )
    return DeckCorpusCoverage(
        source_record_ids=source_record_ids,
        fronts=fronts,
        backs=backs,
    )


def is_record_covered(
    record: history.TranslationRecord,
    coverage: DeckCorpusCoverage,
) -> bool:
    if record.id in coverage.source_record_ids:
        return True
    source = normalize_source(record.source_text)
    if source and (source in coverage.fronts or source in coverage.backs):
        return True
    result = normalize_source(record.result_text)
    if result and (result in coverage.fronts or result in coverage.backs):
        return True
    single_terms = {
        term
        for term in coverage.fronts | coverage.backs
        if term and len(term.split()) == 1
    }
    if not single_terms:
        return False
    source_tokens = set(_WORD_RE.findall(source))
    if source_tokens & single_terms:
        return True
    result_tokens = set(_WORD_RE.findall(result))
    return bool(result_tokens & single_terms)


def pending_corpus_records(
    records: list[history.TranslationRecord],
    *,
    tag: str,
    direction: str,
) -> list[history.TranslationRecord]:
    coverage = load_deck_corpus_coverage(tag, direction)
    if coverage is None:
        return records
    return [record for record in records if not is_record_covered(record, coverage)]
