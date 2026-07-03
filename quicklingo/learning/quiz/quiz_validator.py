from __future__ import annotations

from quicklingo.features import get_feature
from quicklingo.learning.quiz.distractors import (
    distractor_passes_basic_validation,
    distractor_passes_substitution_test,
)
from quicklingo.learning.quiz.models import QuizQuestionType


def validate_choice_candidate(
    *,
    question_type: QuizQuestionType,
    correct: str,
    candidate: str,
    examples: list[str],
    definition: str,
    example_sentence: str = "",
) -> bool:
    word = " ".join(candidate.split()).strip()
    if not word:
        return False
    if word.lower() == correct.lower():
        return True
    filter_examples = [example_sentence] if example_sentence else examples
    if question_type == QuizQuestionType.FILL_BLANK:
        return distractor_passes_substitution_test(
            correct,
            word,
            filter_examples,
            definition,
            check_examples=True,
        )
    if question_type == QuizQuestionType.DEFINITION_MATCH:
        return distractor_passes_substitution_test(
            correct,
            word,
            filter_examples,
            definition,
            check_examples=False,
        )
    return distractor_passes_basic_validation(correct, word, definition)


def filter_valid_choices(
    *,
    question_type: QuizQuestionType,
    correct: str,
    candidates: list[str],
    examples: list[str],
    definition: str,
    example_sentence: str = "",
    target_size: int | None = None,
) -> list[str]:
    if target_size is None:
        target_size = int(get_feature("learning.quiz").get("choices_pool_size", 6))
    result: list[str] = []
    seen = {correct.lower()}
    correct_clean = " ".join(correct.split()).strip()
    if correct_clean:
        result.append(correct_clean)
    for candidate in candidates:
        word = " ".join(str(candidate).split()).strip()
        key = word.lower()
        if not word or key in seen:
            continue
        if not validate_choice_candidate(
            question_type=question_type,
            correct=correct,
            candidate=word,
            examples=examples,
            definition=definition,
            example_sentence=example_sentence,
        ):
            continue
        seen.add(key)
        result.append(word)
        if len(result) >= target_size:
            break
    return result


def pools_overlap_too_much(pools: list[list[str]], *, max_shared: int = 2) -> bool:
    if len(pools) < 2:
        return False
    for index, left in enumerate(pools):
        left_set = {word.lower() for word in left if word.strip()}
        for right in pools[index + 1 :]:
            right_set = {word.lower() for word in right if word.strip()}
            if len(left_set & right_set) > max_shared:
                return True
    return False
