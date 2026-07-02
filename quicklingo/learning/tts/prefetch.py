from __future__ import annotations

from collections.abc import Iterable

from quicklingo.db.learning import LearningCard
from quicklingo.learning.card_display import parse_context
from quicklingo.learning.quiz.models import QuizQuestion
from quicklingo.learning.review_queue import english_side_text
from quicklingo.learning.tts.synth import resolve_sentence_audio, synthesize_sentence


def unique_texts(texts: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for raw in texts:
        cleaned = raw.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def collect_question_tts_texts(question: QuizQuestion) -> list[str]:
    texts: list[str] = []
    if question.prompt_spoken_text.strip():
        texts.append(question.prompt_spoken_text)
    if question.answer_spoken_text.strip():
        texts.append(question.answer_spoken_text)
    return unique_texts(texts)


def collect_quiz_tts_texts(questions: list[QuizQuestion]) -> list[str]:
    texts: list[str] = []
    for question in questions:
        texts.append(question.prompt_spoken_text)
        texts.append(question.answer_spoken_text)
    return unique_texts(texts)


def collect_review_card_tts_texts(card: LearningCard, *, direction: str) -> list[str]:
    texts = list(parse_context(card.context, direction=direction))
    english = english_side_text(card, direction).strip()
    if english:
        texts.append(english)
    return unique_texts(texts)


def collect_review_tts_texts(cards: list[LearningCard], *, direction: str) -> list[str]:
    texts: list[str] = []
    for card in cards:
        texts.extend(collect_review_card_tts_texts(card, direction=direction))
    return unique_texts(texts)


def prefetch_sentences(texts: Iterable[str]) -> int:
    """Synthesize missing sentence MP3 files. Safe to call from a worker thread."""
    synthesized = 0
    for text in unique_texts(texts):
        if resolve_sentence_audio(text) is not None:
            continue
        if synthesize_sentence(text) is not None:
            synthesized += 1
    return synthesized
