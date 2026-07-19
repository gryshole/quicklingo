from __future__ import annotations

import random

from quicklingo.learning.text_normalize import collapse_whitespace


def sample_display_choices(
    pool: list[str],
    correct: str,
    *,
    display_count: int = 4,
) -> list[str]:
    correct_clean = collapse_whitespace(correct)
    if not correct_clean:
        return []
    distractors: list[str] = []
    seen = {correct_clean.lower()}
    for item in pool:
        word = " ".join(str(item).split()).strip()
        key = word.lower()
        if not word or key in seen:
            continue
        seen.add(key)
        distractors.append(word)
    need_wrong = max(0, display_count - 1)
    if len(distractors) < need_wrong:
        chosen_wrong = distractors[:need_wrong]
    else:
        chosen_wrong = random.sample(distractors, need_wrong)
    choices = [correct_clean, *chosen_wrong]
    random.shuffle(choices)
    return choices
