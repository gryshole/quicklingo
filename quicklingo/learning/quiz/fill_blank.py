from __future__ import annotations

import re

from quicklingo.learning.quiz.distractors import (
    is_generic_slot_blank_sentence,
    score_example_for_distractors,
)
from quicklingo.learning.quiz.models import QuizWordDto

_BLANK = "_______"
_TRAILING_PUNCT_RE = re.compile(r"[.!?…]+$")


def blank_word(sentence: str, term: str, *, blank: str = _BLANK) -> str:
    if not term.strip():
        return sentence
    pattern = re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)
    if pattern.search(sentence):
        return pattern.sub(blank, sentence, count=1)
    return sentence.replace(term, _BLANK, 1)


def is_degenerate_blank_prompt(text: str, *, blank: str = _BLANK) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    without_trailing = _TRAILING_PUNCT_RE.sub("", stripped).strip()
    return without_trailing == blank


def has_full_context_around_term(example: str, term: str) -> bool:
    if not example.strip() or not term.strip():
        return False
    pattern = re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)
    match = pattern.search(example)
    if match:
        before = example[: match.start()]
        after = example[match.end() :]
    else:
        lowered = example.lower()
        idx = lowered.find(term.lower())
        if idx < 0:
            return False
        before = example[:idx]
        after = example[idx + len(term) :]
    return _has_word_chars(before) and _has_word_chars(after)


def is_usable_fill_blank_example(example: str, term: str) -> bool:
    if not has_full_context_around_term(example, term):
        return False
    blanked = blank_word(example, term)
    return not is_degenerate_blank_prompt(blanked)


def is_discriminating_fill_blank_example(example: str, term: str) -> bool:
    if not is_usable_fill_blank_example(example, term):
        return False
    return not is_generic_slot_blank_sentence(blank_word(example, term))


def discriminating_fill_blank_examples(examples: list[str], term: str) -> list[str]:
    return [example for example in examples if is_discriminating_fill_blank_example(example, term)]


def all_fill_blank_examples_unviable(examples: list[str], term: str) -> bool:
    return not discriminating_fill_blank_examples(examples, term)


def usable_fill_blank_examples(examples: list[str], term: str) -> list[str]:
    return [example for example in examples if is_usable_fill_blank_example(example, term)]


def best_fill_blank_example(word: QuizWordDto) -> str:
    examples = [example for example in word.examples if example.strip()]
    usable = discriminating_fill_blank_examples(examples, word.english)
    if not usable:
        usable = usable_fill_blank_examples(examples, word.english)
    if not usable:
        return word.english
    scored = [
        (
            score_example_for_distractors(
                word.english,
                example,
                word.distractors,
                word.definition,
            ),
            len(example),
            example,
        )
        for example in usable
    ]
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    best_score, _length, best_example = scored[0]
    if best_score >= 0:
        return best_example
    return max(usable, key=len)


def _has_word_chars(text: str) -> bool:
    return bool(re.search(r"\w", text, re.UNICODE))
