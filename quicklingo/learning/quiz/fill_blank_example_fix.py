from __future__ import annotations

import json
from collections.abc import Callable

from quicklingo.db import learning
from quicklingo.db.learning import LearningCard
from quicklingo.learning.quiz.card_eligibility_fix import (
    DEFAULT_FIX_EXAMPLES_SYSTEM,
    parse_examples_response,
)
from quicklingo.learning.quiz.fill_blank import (
    all_fill_blank_examples_unviable,
    is_discriminating_fill_blank_example,
)
from quicklingo.learning.quiz.models import QuizWordDto
from quicklingo.learning.quiz.normalize import card_to_quiz_word
from quicklingo.logging.ai_requests import ai_request_scope, get_logger
from quicklingo.providers.registry import ModelEntry

_MAX_AI_ATTEMPTS = 3
_MAX_CONTEXT_EXAMPLES = 4

ADD_ONE_FILL_BLANK_EXAMPLE_PROMPT = """Term (English): {english}
Ukrainian: {ukrainian}
Definition: {definition}

Write exactly 1 NEW English example sentence for fill-in-the-blank quiz practice.

Existing sentences (do NOT repeat or paraphrase closely):
{existing_examples}

Rules:
- Include "{english}" with other words BOTH before and after it (not first/last in the sentence).
- After replacing "{english}" with a blank, only "{english}" should fit naturally — not any random word.
- AVOID template patterns such as: "showed great X", "very X", "truly X", "X surprised everyone", "found it X".
- Prefer a concrete situation (sport, work, travel, study) where "{english}" is the specific correct answer.
- B1-B2 level, end with . ! or ?

Output JSON: {{"examples": ["..."]}}"""


def needs_new_fill_blank_example(examples: list[str], term: str) -> bool:
    return all_fill_blank_examples_unviable(examples, term)


def _normalize_sentence(raw: str) -> str:
    sentence = " ".join(str(raw).split()).strip()
    if not sentence:
        return ""
    if not sentence.endswith((".", "!", "?")):
        sentence += "."
    return sentence


def _fallback_discriminating_examples(english: str) -> list[str]:
    term = english.strip()
    if not term:
        return []
    if " " in term:
        return [
            f"We needed more time to {term} before the deadline.",
            f"The team learned to {term} during the project.",
            f"It is difficult to {term} without proper preparation.",
        ]
    return [
        f"Long races require more {term} than short sprints.",
        f"The coach focused on building {term} before the tournament.",
        f"Without enough {term}, the hike became exhausting.",
    ]


def _pick_new_example(candidates: list[str], term: str, existing: list[str]) -> str | None:
    seen = {item.lower() for item in existing}
    for raw in candidates:
        sentence = _normalize_sentence(raw)
        if not sentence or sentence.lower() in seen:
            continue
        if is_discriminating_fill_blank_example(sentence, term):
            return sentence
    return None


def build_add_one_example_prompt(word: QuizWordDto) -> str:
    lines = [example.strip() for example in word.examples if example.strip()]
    existing = "\n".join(f"- {line}" for line in lines) if lines else "(none)"
    return ADD_ONE_FILL_BLANK_EXAMPLE_PROMPT.format(
        english=word.english,
        ukrainian=word.ukrainian,
        definition=word.definition or word.english,
        existing_examples=existing,
    )


def _serialize_examples(examples: list[str]) -> str:
    cleaned = [item.strip() for item in examples if item.strip()]
    return json.dumps(cleaned[:_MAX_CONTEXT_EXAMPLES], ensure_ascii=False)


async def append_discriminating_fill_blank_example(
    card: LearningCard,
    word: QuizWordDto,
    direction: str,
    model_entry: ModelEntry,
    *,
    cancel_flag: Callable[[], bool] | None = None,
) -> tuple[LearningCard, QuizWordDto] | None:
    if not needs_new_fill_blank_example(word.examples, word.english):
        return None

    existing = [_normalize_sentence(item) for item in word.examples if item.strip()]
    existing = [item for item in existing if item]

    new_sentence = _pick_new_example(_fallback_discriminating_examples(word.english), word.english, existing)
    if new_sentence is None:
        for attempt in range(_MAX_AI_ATTEMPTS):
            if cancel_flag and cancel_flag():
                return None
            purpose = "learning.quiz.add_fill_blank_example"
            if attempt > 0:
                purpose = f"{purpose}.retry{attempt}"
            with ai_request_scope(purpose):
                raw = await model_entry.provider.complete(
                    DEFAULT_FIX_EXAMPLES_SYSTEM,
                    build_add_one_example_prompt(word),
                    model_entry.model_id,
                    temperature=0.4,
                )
            new_sentence = _pick_new_example(parse_examples_response(raw), word.english, existing)
            if new_sentence is not None:
                break

    if new_sentence is None:
        return None

    updated_examples = [*existing, new_sentence]
    learning.update_card(
        card.id,
        context=_serialize_examples(updated_examples),
    )
    updated_card = learning.get_card(card.id)
    if updated_card is None:
        return None
    get_logger().info(
        "ADDED_FILL_BLANK_EXAMPLE card_id=%s term=%s sentence=%s example_count=%d",
        card.id,
        word.english,
        new_sentence,
        len(json.loads(updated_card.context or "[]")),
    )
    return updated_card, card_to_quiz_word(updated_card, direction)
