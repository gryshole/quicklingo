from __future__ import annotations

import html
import re

from dataclasses import dataclass

from quicklingo.config.loader import resolve_learning_direction
from quicklingo.db import learning
from quicklingo.learning.quiz.models import QuizQuestion, QuizQuestionType, QuizWordDto
from quicklingo.learning.quiz.normalize import card_to_quiz_word
from quicklingo.learning.text_normalize import collapse_whitespace

MAX_EXAMPLES = 3


@dataclass(frozen=True)
class QuizFeedbackContent:
    ukrainian: str | None
    definition: str | None
    examples: list[str]
    highlight_term: str


def _normalize_sentence_key(value: str) -> str:
    return collapse_whitespace(value).lower()


def _should_exclude_example(example: str, exclude_sentences: list[str]) -> bool:
    key = _normalize_sentence_key(example)
    return any(_normalize_sentence_key(sentence) == key for sentence in exclude_sentences)


def build_quiz_feedback_content(
    word: QuizWordDto,
    question_type: QuizQuestionType,
    *,
    exclude_sentences: list[str] | None = None,
    learning_kind: str | None = None,
) -> QuizFeedbackContent:
    examples = [item.strip() for item in word.examples if item.strip()]
    exclude = exclude_sentences or []
    if exclude:
        examples = [example for example in examples if not _should_exclude_example(example, exclude)]
    examples = examples[:MAX_EXAMPLES]

    definition = (
        None
        if question_type == QuizQuestionType.DEFINITION_MATCH
        else (word.definition.strip() or None)
    )
    ukrainian = (
        None
        if question_type == QuizQuestionType.TRANSLATION_RECALL
        else (word.ukrainian.strip() or None)
    )

    kind = learning_kind or "ua-en"
    highlight_term = word.english.lower() if kind == "en-ua" else word.english

    return QuizFeedbackContent(
        ukrainian=ukrainian,
        definition=definition,
        examples=examples,
        highlight_term=highlight_term,
    )


def is_choice_visible_in_feedback(
    choice: str,
    phase: str,
    *,
    last_correct: bool | None,
    selected_choice: str | None,
    correct_english: str,
) -> bool:
    if phase != "feedback":
        return True

    def normalize(value: str) -> str:
        return value.strip().lower()

    is_correct = normalize(choice) == normalize(correct_english)
    is_selected = (
        selected_choice is not None and normalize(choice) == normalize(selected_choice)
    )

    if last_correct:
        return is_correct
    return is_correct or is_selected


def load_quiz_feedback_content(
    question: QuizQuestion,
    direction: str,
) -> QuizFeedbackContent | None:
    card = learning.get_card(question.source_card_id)
    if card is None:
        return None

    learning_kind = resolve_learning_direction(direction)
    word = card_to_quiz_word(card, direction)
    exclude_sentences: list[str] = []
    if question.type == QuizQuestionType.FILL_BLANK and question.answer_spoken_text.strip():
        exclude_sentences = [question.answer_spoken_text]

    return build_quiz_feedback_content(
        word,
        question.type,
        exclude_sentences=exclude_sentences,
        learning_kind=learning_kind,
    )


def feedback_content_has_body(content: QuizFeedbackContent) -> bool:
    return bool(content.ukrainian or content.definition or content.examples)


def should_show_quiz_feedback_enrichment(
    *,
    wrong_hint: str,
    content: QuizFeedbackContent | None,
) -> bool:
    """Whether the post-answer enrichment block should be shown.

    Do not use QWidget.isVisible() for this: the feedback host may still be
    hidden when we decide visibility, which makes child widgets report False.
    """
    return bool(wrong_hint.strip()) or (
        content is not None and feedback_content_has_body(content)
    )


def format_wrong_hint_html(text: str) -> str:
    """Emphasize quoted inner text; keep guillemets and surrounding copy muted."""
    if not text:
        return ""
    parts = re.split(r"(«[^»]+»)", text)
    chunks: list[str] = []
    muted_open = '<span style="color:#64748b;">'
    bold_open = '<span style="font-weight:700;color:#0f172a;">'
    for part in parts:
        if not part:
            continue
        if part.startswith("«") and part.endswith("»") and len(part) > 2:
            inner = html.escape(part[1:-1])
            chunks.append(f"{muted_open}«</span>{bold_open}{inner}</span>{muted_open}»</span>")
        else:
            chunks.append(f"{muted_open}{html.escape(part)}</span>")
    return "".join(chunks)
