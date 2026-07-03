from __future__ import annotations

import random
from dataclasses import dataclass

from quicklingo.config.loader import resolve_learning_direction
from quicklingo.db import learning
from quicklingo.learning.quiz.eligibility import is_quiz_eligible
from quicklingo.learning.quiz.models import QuizWordDto
from quicklingo.learning.quiz.normalize import card_to_quiz_word


@dataclass(frozen=True)
class QuizPoolStats:
    eligible: int
    ready_with_questions: int
    missing_questions: int
    total_cards: int
    skipped_no_examples: int


def list_quiz_eligible_decks() -> list[learning.LearningDeck]:
    result: list[learning.LearningDeck] = []
    for deck in learning.list_decks():
        if resolve_learning_direction(deck.direction) in ("ua-en", "en-ua"):
            result.append(deck)
    return result


def _deck_in_scope(deck_id: int, deck_ids: frozenset[int] | None) -> bool:
    if deck_ids is None:
        return True
    return deck_id in deck_ids


def _dedupe_key(word: QuizWordDto) -> str:
    return word.english.lower()


def _dedupe_score(card: learning.LearningCard, word: QuizWordDto) -> tuple[str, int, int]:
    return (card.last_reviewed or "", card.id, card.id)


def collect_eligible_quiz_words(
    *,
    deck_ids: frozenset[int] | None = None,
    require_quiz_questions: bool = False,
) -> list[QuizWordDto]:
    best: dict[str, tuple[learning.LearningCard, QuizWordDto]] = {}
    for deck in list_quiz_eligible_decks():
        if not _deck_in_scope(deck.id, deck_ids):
            continue
        for card in learning.list_cards(deck.id):
            word = card_to_quiz_word(card, deck.direction)
            if not is_quiz_eligible(card, word):
                continue
            if require_quiz_questions and not learning.card_has_full_quiz_coverage(card.id):
                continue
            key = _dedupe_key(word)
            existing = best.get(key)
            if existing is None or _dedupe_score(card, word) > _dedupe_score(existing[0], existing[1]):
                best[key] = (card, word)
    return [word for _, word in best.values()]


def get_quiz_pool_stats(*, deck_ids: frozenset[int] | None = None) -> QuizPoolStats:
    total_cards = 0
    skipped_no_examples = 0
    eligible_count = 0
    ready_count = 0

    for deck in list_quiz_eligible_decks():
        if not _deck_in_scope(deck.id, deck_ids):
            continue
        for card in learning.list_cards(deck.id):
            total_cards += 1
            word = card_to_quiz_word(card, deck.direction)
            if not word.english.strip() or len(word.examples) < 1:
                skipped_no_examples += 1
                continue
            if not is_quiz_eligible(card, word):
                continue
            eligible_count += 1
            if learning.card_has_full_quiz_coverage(card.id):
                ready_count += 1

    return QuizPoolStats(
        eligible=eligible_count,
        ready_with_questions=ready_count,
        missing_questions=max(0, eligible_count - ready_count),
        total_cards=total_cards,
        skipped_no_examples=skipped_no_examples,
    )


def count_eligible_quiz_words(*, deck_ids: frozenset[int] | None = None) -> int:
    return len(collect_eligible_quiz_words(deck_ids=deck_ids))


def build_quiz_pool(
    *,
    limit: int = 15,
    deck_ids: frozenset[int] | None = None,
    require_quiz_questions: bool = True,
) -> list[QuizWordDto]:
    eligible = collect_eligible_quiz_words(
        deck_ids=deck_ids,
        require_quiz_questions=require_quiz_questions,
    )
    if not eligible:
        return []
    if len(eligible) <= limit:
        random.shuffle(eligible)
        return eligible
    return random.sample(eligible, limit)
