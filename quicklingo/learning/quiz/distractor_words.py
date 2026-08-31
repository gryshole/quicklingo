from __future__ import annotations

from quicklingo.db import learning
from quicklingo.db.learning_decks import get_deck
from quicklingo.learning.quiz.aggregator import list_quiz_eligible_decks
from quicklingo.learning.quiz.distractor_deck import collect_english_keys_across_decks
from quicklingo.learning.quiz.normalize import normalize_english_quiz_key
from quicklingo.learning.text_normalize import collapse_whitespace


def collect_missing_distractor_words(deck_id: int) -> list[str]:
    """English choices from quiz questions not yet covered by any card (all decks)."""
    deck = get_deck(deck_id)
    if deck is None:
        return []
    existing = collect_english_keys_across_decks(direction=deck.direction)
    seen_in_pool: set[str] = set()
    result: list[str] = []
    for question in learning.list_quiz_questions(deck_id, status="active"):
        for raw in question.choices_pool:
            word = collapse_whitespace(str(raw))
            key = normalize_english_quiz_key(word)
            if not word or key in seen_in_pool:
                continue
            seen_in_pool.add(key)
            if key in existing:
                continue
            result.append(word)
    return result


def resolve_distractor_generation_deck_id(
    deck_ids: frozenset[int] | None,
) -> int | None:
    """Pick the deck in scope with the most missing distractor-card words."""
    best_id: int | None = None
    best_count = 0
    for deck in list_quiz_eligible_decks():
        if deck_ids is not None and deck.id not in deck_ids:
            continue
        missing_count = len(collect_missing_distractor_words(deck.id))
        if missing_count > best_count:
            best_count = missing_count
            best_id = deck.id
    return best_id


def count_missing_distractor_words_in_scope(deck_ids: frozenset[int] | None) -> int:
    total = 0
    for deck in list_quiz_eligible_decks():
        if deck_ids is not None and deck.id not in deck_ids:
            continue
        total += len(collect_missing_distractor_words(deck.id))
    return total
