from __future__ import annotations

import random

from quicklingo.db import learning
from quicklingo.features import get_feature
from quicklingo.learning.quiz.models import QuizQuestionType

_ALL_TYPES = (
    QuizQuestionType.FILL_BLANK,
    QuizQuestionType.DEFINITION_MATCH,
    QuizQuestionType.TRANSLATION_RECALL,
)


def pick_question_type(card_id: int) -> QuizQuestionType:
    lookback = int(get_feature("learning.quiz").get("type_picker_lookback", 10))
    recent = learning.list_recent_quiz_question_types(card_id, limit=lookback)
    weights: dict[QuizQuestionType, float] = {qtype: 1.0 for qtype in _ALL_TYPES}
    for index, qtype_value in enumerate(recent):
        try:
            qtype = QuizQuestionType(qtype_value)
        except ValueError:
            continue
        if qtype not in weights:
            continue
        weights[qtype] *= 0.5 ** (index + 1)
    total = sum(weights.values())
    if total <= 0:
        return random.choice(_ALL_TYPES)
    threshold = random.random() * total
    cumulative = 0.0
    for qtype, weight in weights.items():
        cumulative += weight
        if threshold <= cumulative:
            return qtype
    return _ALL_TYPES[-1]
