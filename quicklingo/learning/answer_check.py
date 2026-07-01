from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from enum import Enum


class AnswerResult(str, Enum):
    CORRECT = "correct"
    PARTIAL = "partial"
    WRONG = "wrong"


def normalize_answer(text: str) -> str:
    text = unicodedata.normalize("NFKC", text.strip().lower())
    text = re.sub(r"[^\w\s'-]+", " ", text, flags=re.UNICODE)
    return " ".join(text.split())


def split_acceptable_answers(back: str) -> list[str]:
    parts = re.split(r"[;/|]|(?:\s+or\s+)", back, flags=re.IGNORECASE)
    answers = [normalize_answer(part) for part in parts if part.strip()]
    primary = normalize_answer(back)
    if primary and primary not in answers:
        answers.insert(0, primary)
    return answers or [primary]


def check_answer(user_input: str, expected_back: str, *, strictness: float = 0.85) -> AnswerResult:
    normalized_input = normalize_answer(user_input)
    if not normalized_input:
        return AnswerResult.WRONG
    acceptable = split_acceptable_answers(expected_back)
    for answer in acceptable:
        if not answer:
            continue
        if normalized_input == answer:
            return AnswerResult.CORRECT
        ratio = SequenceMatcher(None, normalized_input, answer).ratio()
        if ratio >= strictness:
            return AnswerResult.CORRECT
        if ratio >= max(0.65, strictness - 0.15):
            return AnswerResult.PARTIAL
    return AnswerResult.WRONG
