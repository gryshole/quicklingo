from __future__ import annotations

from typing import Protocol

from quicklingo.learning.quiz.db_generator import DbQuizGenerator
from quicklingo.learning.quiz.models import QuizQuestion, QuizWordDto


class QuizGenerator(Protocol):
    def build_questions(self, words: list[QuizWordDto]) -> list[QuizQuestion]: ...


def get_quiz_generator() -> QuizGenerator:
    return DbQuizGenerator()
