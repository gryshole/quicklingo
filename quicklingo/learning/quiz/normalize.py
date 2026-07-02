from __future__ import annotations

from quicklingo.config.loader import resolve_learning_direction
from quicklingo.db.learning import LearningCard
from quicklingo.learning.card_display import parse_context
from quicklingo.learning.card_prompt import extract_pos_from_hint
from quicklingo.learning.quiz.distractors import parse_quiz_distractors
from quicklingo.learning.quiz.models import QuizWordDto
from quicklingo.learning.review_queue import english_side_text, ukrainian_side_text

_DEFINITION_PREFIX = "Definition:"


def parse_definition(notes: str) -> str:
    text = (notes or "").strip()
    if text.lower().startswith(_DEFINITION_PREFIX.lower()):
        return text[len(_DEFINITION_PREFIX) :].strip()
    return text


def card_to_quiz_word(card: LearningCard, direction: str) -> QuizWordDto:
    kind = resolve_learning_direction(direction)
    english = english_side_text(card, kind)
    ukrainian = ukrainian_side_text(card, kind)
    examples = parse_context(card.context, direction=kind)
    return QuizWordDto(
        card_id=card.id,
        english=english,
        ukrainian=ukrainian,
        definition=parse_definition(card.notes),
        examples=examples,
        distractors=parse_quiz_distractors(card.quiz_distractors),
        hint_pos=extract_pos_from_hint(card.hint),
    )
