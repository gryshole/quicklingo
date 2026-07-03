from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class QuizQuestionType(str, Enum):
    FILL_BLANK = "fill_blank"
    DEFINITION_MATCH = "definition_match"
    TRANSLATION_RECALL = "translation_recall"


@dataclass
class QuizWordDto:
    card_id: int
    english: str
    ukrainian: str
    definition: str
    examples: list[str]
    distractors: list[str]
    hint_pos: str


@dataclass
class QuizQuestion:
    index: int
    type: QuizQuestionType
    prompt_html: str
    prompt_text: str
    prompt_hint: str
    choices: list[str]
    correct_english: str
    source_card_id: int
    prompt_spoken_text: str = ""
    answer_spoken_text: str = ""
    question_id: int | None = None
    choices_shown: list[str] = field(default_factory=list)


@dataclass
class QuizAnswer:
    question_index: int
    selected: str
    correct: bool
    elapsed_ms: int


@dataclass
class QuizSessionState:
    words: list[QuizWordDto] = field(default_factory=list)
    questions: list[QuizQuestion] = field(default_factory=list)
    answers: list[QuizAnswer] = field(default_factory=list)
    started_at: float = 0.0
    position: int = 0


@dataclass
class QuizResult:
    score: int
    total: int
    wrong_words: list[QuizWordDto]
