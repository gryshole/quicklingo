from __future__ import annotations

from dataclasses import dataclass

from quicklingo.config.loader import resolve_learning_direction
from quicklingo.db.learning_cards import list_cards
from quicklingo.db.learning_decks import find_deck_by_tag, list_decks
from quicklingo.learning.quiz.distractor_deck import (
    QUIZ_DISTRACTOR_DECK_TAG,
    is_quiz_distractor_deck,
)
from quicklingo.learning.quiz.normalize import card_to_quiz_word, normalize_english_quiz_key
from quicklingo.learning.text_normalize import collapse_whitespace


@dataclass(frozen=True)
class ChoiceMetadata:
    english: str
    ukrainian: str
    definition: str
    examples: list[str]
    card_id: int
    from_distractor_deck: bool


def lookup_english_metadata(english: str, direction: str) -> ChoiceMetadata | None:
    term = collapse_whitespace(english)
    key = normalize_english_quiz_key(term)
    if not key:
        return None
    kind = resolve_learning_direction(direction)
    if kind not in ("ua-en", "en-ua"):
        return None

    for deck in list_decks():
        if is_quiz_distractor_deck(deck):
            continue
        if resolve_learning_direction(deck.direction) != kind:
            continue
        meta = _match_in_deck(deck, term, key, from_distractor=False)
        if meta is not None:
            return meta

    distractor_deck = find_deck_by_tag(QUIZ_DISTRACTOR_DECK_TAG, direction)
    if distractor_deck is not None:
        return _match_in_deck(distractor_deck, term, key, from_distractor=True)
    return None


def _match_in_deck(
    deck,
    term: str,
    key: str,
    *,
    from_distractor: bool,
) -> ChoiceMetadata | None:
    for card in list_cards(deck.id):
        word = card_to_quiz_word(card, deck.direction)
        if normalize_english_quiz_key(word.english) != key:
            continue
        return ChoiceMetadata(
            english=word.english,
            ukrainian=word.ukrainian,
            definition=word.definition,
            examples=list(word.examples),
            card_id=word.card_id,
            from_distractor_deck=from_distractor,
        )
    return None


def format_wrong_choice_feedback(english: str, direction: str) -> str | None:
    """Human-readable hint for a wrong quiz choice (ukrainian or definition from cards)."""
    from quicklingo.i18n import tr

    term = collapse_whitespace(english)
    if not term:
        return None
    meta = lookup_english_metadata(term, direction)
    if meta is None:
        return tr("learning.quiz_wrong_choice_unknown", english=term)
    ukrainian = meta.ukrainian.strip()
    if ukrainian:
        return tr("learning.quiz_wrong_choice_hint", english=term, ukrainian=ukrainian)
    definition = meta.definition.strip()
    if definition:
        return tr("learning.quiz_wrong_choice_definition", english=term, definition=definition)
    return None
