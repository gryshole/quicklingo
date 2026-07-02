from __future__ import annotations

import re
from typing import Protocol

from quicklingo.learning.quiz.local_generator import LocalQuizGenerator
from quicklingo.learning.quiz.models import QuizQuestion, QuizWordDto


class QuizGenerator(Protocol):
    def build_questions(self, words: list[QuizWordDto]) -> list[QuizQuestion]: ...


def get_quiz_generator() -> QuizGenerator:
    return LocalQuizGenerator()
