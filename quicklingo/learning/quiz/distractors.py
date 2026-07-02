from __future__ import annotations

import json
import random
import re

from quicklingo.learning.card_prompt import _content_tokens, texts_too_similar

_MIN_DISTRACTORS = 3
_MAX_DISTRACTORS = 5
_CYRILLIC = re.compile(r"[\u0400-\u04FF]")
_DEFINITION_PREFIX = re.compile(r"(?i)^definition:\s*")
_DISTRACTOR_SIMILARITY_THRESHOLD = 0.35
_GENERIC_SLOT_PATTERNS = (
    re.compile(r"\bshowed\s+great\s+___\b", re.I),
    re.compile(r"\b___\s+surprised\s+everyone\b", re.I),
)


def parse_quiz_distractors(raw: object) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return _clean_distractor_list([str(item) for item in raw])
    text = str(raw).strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return []
        if isinstance(parsed, list):
            return _clean_distractor_list([str(item) for item in parsed])
    return []


def serialize_quiz_distractors(items: list[str]) -> str:
    cleaned = _clean_distractor_list(items)
    if not cleaned:
        return ""
    return json.dumps(cleaned, ensure_ascii=False)


def _clean_distractor_list(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        word = " ".join(str(item).split()).strip()
        key = word.lower()
        if not word or key in seen or _CYRILLIC.search(word):
            continue
        seen.add(key)
        result.append(word)
    return result


def _shared_morphological_root(a: str, b: str, *, min_len: int = 5) -> bool:
    a_key = a.lower().strip()
    b_key = b.lower().strip()
    if not a_key or not b_key:
        return False
    limit = min(len(a_key), len(b_key), min_len + 2)
    for size in range(limit, min_len - 1, -1):
        if a_key[:size] == b_key[:size]:
            return True
    return False


def _phrasal_verb_family(term: str, distractor: str) -> bool:
    if " " not in term or " " not in distractor:
        return False
    term_parts = term.lower().split()
    dist_parts = distractor.lower().split()
    return term_parts[-1] == dist_parts[-1]


def _distractors_too_similar(a: str, b: str) -> bool:
    if texts_too_similar(a, b):
        return True
    a_tokens = _content_tokens(a, min_len=3)
    b_tokens = _content_tokens(b, min_len=3)
    if not a_tokens or not b_tokens:
        return False
    overlap = a_tokens & b_tokens
    ratio = len(overlap) / min(len(a_tokens), len(b_tokens))
    return ratio >= _DISTRACTOR_SIMILARITY_THRESHOLD


def _definition_body(definition: str) -> str:
    return _DEFINITION_PREFIX.sub("", definition.strip())


def _definition_describes_distractor(definition: str, distractor: str) -> bool:
    body = _definition_body(definition)
    if not body:
        return False
    dist_tokens = _content_tokens(distractor, min_len=3)
    if not dist_tokens:
        return False
    def_tokens = _content_tokens(body, min_len=3)
    if not def_tokens:
        return False
    return dist_tokens.issubset(def_tokens) or def_tokens.issubset(dist_tokens)


def _replace_term(sentence: str, term: str, replacement: str) -> str:
    pattern = re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)
    if pattern.search(sentence):
        return pattern.sub(replacement, sentence, count=1)
    return sentence


def _is_generic_slot_sentence(sentence: str) -> bool:
    blanked = sentence.replace("_______", "___")
    return any(pattern.search(blanked) for pattern in _GENERIC_SLOT_PATTERNS)


def distractor_fits_example(term: str, distractor: str, example: str) -> bool:
    """Return True when distractor plausibly fits the target slot in example."""
    if not term.strip() or not distractor.strip() or not example.strip():
        return False
    if term.lower() not in example.lower():
        return False
    replaced = _replace_term(example, term, distractor)
    if replaced.lower() == example.lower():
        return False
    blanked = _replace_term(example, term, "___")
    return _is_generic_slot_sentence(blanked)


def distractor_passes_basic_validation(
    term: str,
    distractor: str,
    definition: str = "",
) -> bool:
    """POS/morphology checks without example substitution (for persisting AI distractors)."""
    if not distractor.strip() or distractor.lower() == term.lower():
        return False
    if _phrasal_verb_family(term, distractor):
        return False
    if _shared_morphological_root(term, distractor):
        return False
    if _distractors_too_similar(distractor, term):
        return False
    if definition and _definition_describes_distractor(definition, distractor):
        return False
    return True


def distractor_passes_substitution_test(
    term: str,
    distractor: str,
    examples: list[str],
    definition: str = "",
    *,
    check_examples: bool = True,
) -> bool:
    """Return True if distractor is safe to use (does not fit examples as correct answer)."""
    if not distractor_passes_basic_validation(term, distractor, definition):
        return False
    if not check_examples:
        return True
    for example in examples:
        if distractor_fits_example(term, distractor, example):
            return False
    return True


def filter_valid_distractors(
    term: str,
    distractors: list[str],
    examples: list[str],
    definition: str = "",
) -> list[str]:
    result: list[str] = []
    seen: set[str] = {term.lower()}
    for word in distractors:
        key = word.lower()
        if key in seen:
            continue
        if not distractor_passes_substitution_test(term, word, examples, definition):
            continue
        seen.add(key)
        result.append(word)
    return result


def fallback_quiz_distractors(
    term: str,
    pos: str,
    pool: list[str],
    *,
    count: int = 3,
    extra_pool: list[str] | None = None,
    examples: list[str] | None = None,
    definition: str = "",
    check_examples: bool = True,
) -> list[str]:
    term_key = term.lower()
    candidates: list[str] = []
    seen: set[str] = {term_key}
    example_list = examples or []
    for source in (pool, extra_pool or []):
        for word in source:
            key = word.lower()
            if key in seen:
                continue
            if not distractor_passes_substitution_test(
                term,
                word,
                example_list,
                definition,
                check_examples=check_examples,
            ):
                continue
            seen.add(key)
            candidates.append(word)
    if len(candidates) < count:
        return candidates[:count]
    return random.sample(candidates, count)


def pick_quiz_choices(
    *,
    correct: str,
    distractors: list[str],
    pool: list[str],
    pos: str,
    count: int = 4,
    examples: list[str] | None = None,
    definition: str = "",
    example_sentence: str | None = None,
    check_examples: bool = True,
) -> list[str]:
    need = count - 1
    example_list = list(examples or [])
    if example_sentence and example_sentence not in example_list:
        example_list.insert(0, example_sentence)
    filter_examples = [example_sentence] if example_sentence else example_list
    chosen: list[str] = []
    seen = {correct.lower()}
    for word in distractors:
        key = word.lower()
        if key in seen:
            continue
        if not distractor_passes_substitution_test(
            correct,
            word,
            filter_examples or example_list,
            definition,
            check_examples=check_examples,
        ):
            continue
        seen.add(key)
        chosen.append(word)
        if len(chosen) >= need:
            break
    if len(chosen) < need:
        for word in fallback_quiz_distractors(
            correct,
            pos,
            pool,
            count=need - len(chosen),
            extra_pool=pool,
            examples=filter_examples or example_list,
            definition=definition,
            check_examples=check_examples,
        ):
            key = word.lower()
            if key in seen:
                continue
            seen.add(key)
            chosen.append(word)
            if len(chosen) >= need:
                break
    if len(chosen) < need and check_examples:
        for word in fallback_quiz_distractors(
            correct,
            pos,
            pool,
            count=need - len(chosen),
            extra_pool=pool,
            examples=filter_examples or example_list,
            definition=definition,
            check_examples=False,
        ):
            key = word.lower()
            if key in seen:
                continue
            seen.add(key)
            chosen.append(word)
            if len(chosen) >= need:
                break
    choices = [correct, *chosen[:need]]
    random.shuffle(choices)
    return choices


def score_example_for_distractors(
    term: str,
    example: str,
    distractors: list[str],
    definition: str = "",
) -> int:
    """Higher score = more distractors fail substitution (better discrimination)."""
    if term.lower() not in example.lower():
        return -1
    return sum(
        1
        for distractor in distractors
        if not distractor_fits_example(term, distractor, example)
    )
