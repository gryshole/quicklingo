from __future__ import annotations

import json
import re
from dataclasses import dataclass

from quicklingo.learning.quiz.models import QuizQuestionType

_FIELD_BY_TYPE = {
    QuizQuestionType.FILL_BLANK: "quiz_prompt_fill_blank",
    QuizQuestionType.DEFINITION_MATCH: "quiz_prompt_definition_match",
    QuizQuestionType.TRANSLATION_RECALL: "quiz_prompt_translation_recall",
}

DEFAULT_QUIZ_SYSTEM_PROMPT = """You generate English multiple-choice distractors for a language-learning quiz.
Output JSON only: {"choices": ["word1", "word2", ...]}.
Rules:
- Return 6 to 8 unique English words or short phrases (lemma form).
- Never include Cyrillic.
- Never duplicate the correct answer unless it appears in the requested list as the target word.
- Match part of speech where possible.
- Distractors must be plausible but wrong for the given task.
- Do not repeat the same distractor twice."""

DEFAULT_QUIZ_PROMPT_FILL_BLANK = """Target word: {english}
Part of speech hint: {hint_pos}
Definition: {definition}
Example sentences:
{examples}

Sentence with blank (only ONE word fits — the target):
{blanked_sentence}
Full sentence: {fill_sentence}

Generate {choices_count} English answer choices for this fill-in-the-blank question.
Include "{english}" in the list.
Every OTHER choice must NOT fit naturally into the blank in the sentence."""

DEFAULT_QUIZ_PROMPT_DEFINITION_MATCH = """Target word: {english}
Part of speech hint: {hint_pos}
Definition shown to the learner:
{definition}

Generate {choices_count} English answer choices for a definition-matching question.
Include "{english}" in the list.
Other choices must NOT match the definition as well as the target word."""

DEFAULT_QUIZ_PROMPT_TRANSLATION_RECALL = """Ukrainian prompt shown to the learner: {ukrainian}
Correct English answer: {english}
Part of speech hint: {hint_pos}

Generate {choices_count} English answer choices for a translation-recall question.
Include "{english}" in the list.
Other choices must be English only and must NOT be valid translations of the Ukrainian prompt."""

_BUILTIN_BY_TYPE = {
    QuizQuestionType.FILL_BLANK: DEFAULT_QUIZ_PROMPT_FILL_BLANK,
    QuizQuestionType.DEFINITION_MATCH: DEFAULT_QUIZ_PROMPT_DEFINITION_MATCH,
    QuizQuestionType.TRANSLATION_RECALL: DEFAULT_QUIZ_PROMPT_TRANSLATION_RECALL,
}


@dataclass(frozen=True)
class CardQuizContext:
    english: str
    ukrainian: str
    definition: str
    hint_pos: str
    examples: list[str]
    direction: str
    fill_sentence: str = ""
    blanked_sentence: str = ""


def get_builtin_quiz_system_prompt() -> str:
    return DEFAULT_QUIZ_SYSTEM_PROMPT


def get_builtin_quiz_prompt(question_type: QuizQuestionType) -> str:
    return _BUILTIN_BY_TYPE[question_type]


def get_quiz_system_prompt() -> str:
    from quicklingo.features import get_feature

    custom = get_feature("learning.quiz").get("quiz_system_prompt_template", "")
    if isinstance(custom, str) and custom.strip():
        return custom.strip()
    return get_builtin_quiz_system_prompt()


def get_quiz_prompt(question_type: QuizQuestionType) -> str:
    from quicklingo.features import get_feature

    field = _FIELD_BY_TYPE[question_type]
    custom = get_feature("learning.quiz").get(field, "")
    if isinstance(custom, str) and custom.strip():
        return custom.strip()
    return get_builtin_quiz_prompt(question_type)


def is_custom_quiz_prompt() -> bool:
    from quicklingo.features import get_feature

    feature = get_feature("learning.quiz")
    for key in (
        "quiz_system_prompt_template",
        "quiz_prompt_fill_blank",
        "quiz_prompt_definition_match",
        "quiz_prompt_translation_recall",
    ):
        value = feature.get(key, "")
        if isinstance(value, str) and value.strip():
            return True
    return False


def format_examples_block(examples: list[str]) -> str:
    lines = [example.strip() for example in examples if example.strip()]
    if not lines:
        return "(none)"
    return "\n".join(f"{index}. {line}" for index, line in enumerate(lines, start=1))


def build_choices_user_prompt(
    question_type: QuizQuestionType,
    context: CardQuizContext,
    *,
    choices_count: int = 6,
    extra_context: str = "",
) -> str:
    from quicklingo.features import get_feature

    pool_size = int(get_feature("learning.quiz").get("choices_pool_size", 6))
    count = choices_count or pool_size
    template = get_quiz_prompt(question_type)
    payload = {
        "english": context.english,
        "ukrainian": context.ukrainian,
        "definition": context.definition or context.english,
        "hint_pos": context.hint_pos or "(unknown)",
        "examples": format_examples_block(context.examples),
        "fill_sentence": context.fill_sentence,
        "blanked_sentence": context.blanked_sentence,
        "choices_count": count,
    }
    prompt = template.format(**payload)
    extra = (extra_context or "").strip()
    if extra:
        prompt = f"{prompt}\n\n{extra}"
    return prompt


def build_regen_extra_context(
    *,
    user_context: str,
    prompt_text: str = "",
    example_sentence: str = "",
    choices_pool: list[str] | None = None,
) -> str:
    lines = [
        "Additional instructions from the learner (follow if compatible with rules above):",
        user_context.strip(),
        "",
        "Current question (for reference — improve, do not copy blindly):",
    ]
    if prompt_text.strip():
        lines.append(f"Prompt: {prompt_text.strip()}")
    if example_sentence.strip():
        lines.append(f"Example sentence: {example_sentence.strip()}")
    if choices_pool:
        lines.append("Choices: " + ", ".join(choices_pool))
    return "\n".join(lines)


def parse_choices_response(raw: str) -> list[str]:
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
    choices = parsed.get("choices") if isinstance(parsed, dict) else None
    if not isinstance(choices, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for item in choices:
        word = " ".join(str(item).split()).strip()
        key = word.lower()
        if not word or key in seen:
            continue
        seen.add(key)
        result.append(word)
    return result
