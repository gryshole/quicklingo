from __future__ import annotations

from quicklingo.config.loader import resolve_learning_direction
from quicklingo.db.learning_decks import list_decks
from quicklingo.db.learning_cards import list_cards
from quicklingo.db.learning_models import LearningCard, LearningDeck
from quicklingo.learning.review_queue import english_side_text

QUIZ_DISTRACTOR_DECK_TAG = "__quiz-distractors"
QUIZ_DISTRACTOR_CARD_TYPE = "quiz_distractor"
QUIZ_DISTRACTOR_DECK_SOURCE = "quiz_distractor"
NO_REVIEW_SCHEDULE_DATE = "2099-12-31"


def is_quiz_distractor_deck(deck: LearningDeck) -> bool:
    return (deck.tag or "").strip() == QUIZ_DISTRACTOR_DECK_TAG


def is_quiz_distractor_card(card: LearningCard, deck: LearningDeck | None = None) -> bool:
    if (card.card_type or "").strip() == QUIZ_DISTRACTOR_CARD_TYPE:
        return True
    if deck is not None and is_quiz_distractor_deck(deck):
        return True
    return False


def filter_user_decks(decks: list[LearningDeck]) -> list[LearningDeck]:
    return [deck for deck in decks if not is_quiz_distractor_deck(deck)]


def collect_english_keys_across_decks(
    *,
    direction: str,
    include_distractor_deck: bool = True,
) -> set[str]:
    kind = resolve_learning_direction(direction)
    if kind not in ("ua-en", "en-ua"):
        return set()
    keys: set[str] = set()
    for deck in list_decks():
        if resolve_learning_direction(deck.direction) != kind:
            continue
        if not include_distractor_deck and is_quiz_distractor_deck(deck):
            continue
        for card in list_cards(deck.id):
            english = english_side_text(card, kind).strip().lower()
            if english:
                keys.add(english)
    return keys


def count_distractor_cards(direction: str) -> int:
    kind = resolve_learning_direction(direction)
    total = 0
    for deck in list_decks():
        if not is_quiz_distractor_deck(deck):
            continue
        if resolve_learning_direction(deck.direction) != kind:
            continue
        total += len(list_cards(deck.id))
    return total
