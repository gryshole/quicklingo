from __future__ import annotations

import re
from dataclasses import dataclass

from quicklingo.config.loader import resolve_learning_direction
from quicklingo.db import history, learning
from quicklingo.db.learning_decks import list_decks
from quicklingo.learning.quiz.distractor_deck import filter_user_decks
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
    return _coverage_from_cards(learning.list_cards(deck.id))


def load_direction_corpus_coverage(direction: str) -> DeckCorpusCoverage | None:
    """All user decks in a learning direction (excludes quiz distractor deck)."""
    kind = resolve_learning_direction(direction)
    decks = [
        deck
        for deck in filter_user_decks(list_decks())
        if resolve_learning_direction(deck.direction) == kind
    ]
    if not decks:
        return None
    cards: list[learning.LearningCard] = []
    for deck in decks:
        cards.extend(learning.list_cards(deck.id))
    if not cards:
        return None
    return _coverage_from_cards(cards)


def _coverage_from_cards(cards: list[learning.LearningCard]) -> DeckCorpusCoverage:
    source_record_ids = frozenset(
        card.source_record_id for card in cards if card.source_record_id is not None
    )
    fronts = frozenset(normalize_source(card.front) for card in cards if card.front.strip())
    backs = frozenset(normalize_source(card.back) for card in cards if card.back.strip())
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
    coverage = load_direction_corpus_coverage(direction)
    if coverage is None:
        return records
    return [record for record in records if not is_record_covered(record, coverage)]
