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
    total_cards: int
    skipped_no_examples: int


def _dedupe_key(word: QuizWordDto) -> str:
    return word.english.lower()


def _dedupe_score(card: learning.LearningCard, word: QuizWordDto) -> tuple[str, int, int]:
    return (card.last_reviewed or "", len(word.distractors), card.id)


def collect_eligible_quiz_words(*, tag: str | None = None) -> list[QuizWordDto]:
    best: dict[str, tuple[learning.LearningCard, QuizWordDto]] = {}
    for deck in learning.list_decks():
        kind = resolve_learning_direction(deck.direction)
        if kind not in ("ua-en", "en-ua"):
            continue
        if tag and deck.tag != tag:
            continue
        for card in learning.list_cards(deck.id):
            word = card_to_quiz_word(card, deck.direction)
            if not is_quiz_eligible(card, word):
                continue
            key = _dedupe_key(word)
            existing = best.get(key)
            if existing is None or _dedupe_score(card, word) > _dedupe_score(existing[0], existing[1]):
                best[key] = (card, word)
    return [word for _, word in best.values()]


def get_quiz_pool_stats(*, tag: str | None = None) -> QuizPoolStats:
    total_cards = 0
    skipped_no_examples = 0
    for deck in learning.list_decks():
        kind = resolve_learning_direction(deck.direction)
        if kind not in ("ua-en", "en-ua"):
            continue
        if tag and deck.tag != tag:
            continue
        for card in learning.list_cards(deck.id):
            total_cards += 1
            word = card_to_quiz_word(card, deck.direction)
            if not word.english.strip() or len(word.examples) < 1:
                skipped_no_examples += 1
    eligible = len(collect_eligible_quiz_words(tag=tag))
    return QuizPoolStats(
        eligible=eligible,
        total_cards=total_cards,
        skipped_no_examples=skipped_no_examples,
    )


def count_eligible_quiz_words(*, tag: str | None = None) -> int:
    return len(collect_eligible_quiz_words(tag=tag))


def build_quiz_pool(*, limit: int = 15, tag: str | None = None) -> list[QuizWordDto]:
    eligible = collect_eligible_quiz_words(tag=tag)
    if not eligible:
        return []
    if len(eligible) <= limit:
        random.shuffle(eligible)
        return eligible
    return random.sample(eligible, limit)
