from __future__ import annotations

from quicklingo.db.learning import LearningCard
from quicklingo.learning.quiz.fill_blank import is_usable_fill_blank_example
from quicklingo.learning.quiz.models import QuizWordDto


def is_quiz_eligible(card: LearningCard, word: QuizWordDto) -> bool:
    if not word.english.strip():
        return False
    examples = [example for example in word.examples if example.strip()]
    if not examples:
        return False
    return any(is_usable_fill_blank_example(example, word.english) for example in examples)
