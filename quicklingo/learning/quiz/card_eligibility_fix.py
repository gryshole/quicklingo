from __future__ import annotations

import json
import re
from dataclasses import dataclass

from quicklingo.config.loader import resolve_learning_direction
from quicklingo.db import learning
from quicklingo.db.learning import LearningCard
from quicklingo.learning.quiz.eligibility import is_quiz_eligible
from quicklingo.learning.quiz.fill_blank import (
    blank_word,
    has_full_context_around_term,
    is_degenerate_blank_prompt,
    is_usable_fill_blank_example,
)
from quicklingo.learning.quiz.models import QuizWordDto
from quicklingo.learning.quiz.normalize import card_to_quiz_word

DEFAULT_FIX_EXAMPLES_SYSTEM = (
    "You write English example sentences for language-learning flashcards. Output JSON only."
)

DEFAULT_FIX_EXAMPLES_PROMPT = """Term (English): {english}
Ukrainian: {ukrainian}
Definition: {definition}

Write exactly 3 natural English example sentences for quiz fill-in-the-blank practice.

Rules:
- Each sentence must contain the term "{english}" (exact word or natural inflection).
- The term must have other words BOTH before and after it (not first/last in the sentence).
- After replacing the term with a blank, the sentence must still read naturally.
- B1-B2 level, end with . ! or ?

Output JSON: {{"examples": ["...", "...", "..."]}}"""


@dataclass(frozen=True)
class IneligibleCard:
    card: LearningCard
    word: QuizWordDto
    reason: str


def ineligibility_reason(card: LearningCard, word: QuizWordDto) -> str:
    if not word.english.strip():
        return "missing_english"
    examples = [example for example in word.examples if example.strip()]
    if not examples:
        return "missing_examples"
    for example in examples:
        if is_usable_fill_blank_example(example, word.english):
            return ""
        if not has_full_context_around_term(example, word.english):
            continue
        blanked = blank_word(example, word.english)
        if is_degenerate_blank_prompt(blanked):
            continue
    return "examples_not_usable"


def list_ineligible_cards(deck_id: int) -> list[IneligibleCard]:
    deck = learning.get_deck(deck_id)
    if deck is None:
        return []
    if resolve_learning_direction(deck.direction) not in ("ua-en", "en-ua"):
        return []
    result: list[IneligibleCard] = []
    for card in learning.list_cards(deck_id):
        word = card_to_quiz_word(card, deck.direction)
        if is_quiz_eligible(card, word):
            continue
        reason = ineligibility_reason(card, word)
        result.append(IneligibleCard(card=card, word=word, reason=reason or "unknown"))
    return result


def count_ineligible_cards(deck_id: int) -> int:
    return len(list_ineligible_cards(deck_id))


def _template_examples(english: str) -> list[str]:
    term = english.strip()
    if not term:
        return []
    if " " in term:
        return [
            f"We tried to {term} during the break.",
            f"They plan to {term} after the match.",
            f"It's hard to {term} on short notice.",
        ]
    return [
        f"The very {term} story kept everyone talking.",
        f"A truly {term} result surprised the team.",
        f"People found it {term} from the start.",
    ]


def filter_usable_examples(examples: list[str], term: str, *, limit: int = 3) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for raw in examples:
        sentence = " ".join(str(raw).split()).strip()
        if not sentence:
            continue
        if not sentence.endswith((".", "!", "?")):
            sentence += "."
        key = sentence.lower()
        if key in seen:
            continue
        if not is_usable_fill_blank_example(sentence, term):
            continue
        seen.add(key)
        result.append(sentence)
        if len(result) >= limit:
            break
    return result


def parse_examples_response(raw: str) -> list[str]:
    text = (raw or "").strip()
    if not text:
        return []
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return []
    examples = parsed.get("examples") if isinstance(parsed, dict) else None
    if not isinstance(examples, list):
        return []
    return [str(item).strip() for item in examples if str(item).strip()]


def build_fix_examples_prompt(word: QuizWordDto) -> str:
    return DEFAULT_FIX_EXAMPLES_PROMPT.format(
        english=word.english,
        ukrainian=word.ukrainian,
        definition=word.definition or word.english,
    )


def pick_quiz_eligible_examples(word: QuizWordDto, candidates: list[str]) -> list[str]:
    usable = filter_usable_examples(candidates, word.english, limit=3)
    if len(usable) >= 3:
        return usable
    for template in _template_examples(word.english):
        if template.lower() in {item.lower() for item in usable}:
            continue
        if is_usable_fill_blank_example(template, word.english):
            usable.append(template)
        if len(usable) >= 3:
            break
    return usable[:3]
