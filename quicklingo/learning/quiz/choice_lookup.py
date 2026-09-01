from __future__ import annotations

from dataclasses import dataclass

from quicklingo.config.loader import resolve_learning_direction
from quicklingo.db.learning_cards import list_cards
from quicklingo.db.learning_decks import find_deck_by_tag, list_decks
from quicklingo.learning.quiz.distractor_deck import (
    QUIZ_DISTRACTOR_DECK_TAG,
    is_quiz_distractor_deck,
)
from quicklingo.learning.quiz.models import QuizQuestionType
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


def _selected_choice_label(meta: ChoiceMetadata | None) -> str | None:
    if meta is None:
        return None
    ukrainian = meta.ukrainian.strip()
    if ukrainian:
        return ukrainian
    definition = meta.definition.strip()
    if definition:
        return definition
    return None


def _combined_wrong_choice_feedback(
    selected: str,
    direction: str,
    *,
    correct_english: str,
    match_key: str,
    unknown_selected_key: str,
) -> str | None:
    from quicklingo.i18n import tr

    correct_term = collapse_whitespace(correct_english)
    correct_meta = lookup_english_metadata(correct_term, direction)
    correct_ukrainian = correct_meta.ukrainian.strip() if correct_meta else ""
    if not correct_ukrainian:
        return None

    selected_meta = lookup_english_metadata(selected, direction)
    selected_label = _selected_choice_label(selected_meta)
    correct_english_label = correct_meta.english if correct_meta else correct_term
    if selected_label:
        return tr(
            match_key,
            correct_ukrainian=correct_ukrainian,
            correct_english=correct_english_label,
            selected=selected,
            selected_ukrainian=selected_label,
        )
    return tr(
        unknown_selected_key,
        correct_ukrainian=correct_ukrainian,
        correct_english=correct_english_label,
        selected=selected,
    )


def format_wrong_choice_feedback(
    english: str,
    direction: str,
    *,
    correct_english: str | None = None,
    question_type: QuizQuestionType | None = None,
) -> str | None:
    """Human-readable hint for a wrong quiz choice (ukrainian or definition from cards)."""
    from quicklingo.i18n import tr

    term = collapse_whitespace(english)
    if not term:
        return None

    if correct_english and question_type == QuizQuestionType.DEFINITION_MATCH:
        combined = _combined_wrong_choice_feedback(
            term,
            direction,
            correct_english=correct_english,
            match_key="learning.quiz_wrong_choice_definition_match",
            unknown_selected_key="learning.quiz_wrong_choice_definition_match_unknown_selected",
        )
        if combined is not None:
            return combined

    if correct_english and question_type == QuizQuestionType.FILL_BLANK:
        combined = _combined_wrong_choice_feedback(
            term,
            direction,
            correct_english=correct_english,
            match_key="learning.quiz_wrong_choice_fill_blank",
            unknown_selected_key="learning.quiz_wrong_choice_fill_blank_unknown_selected",
        )
        if combined is not None:
            return combined

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
