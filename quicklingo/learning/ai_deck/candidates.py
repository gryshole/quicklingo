from __future__ import annotations

from quicklingo.config.loader import resolve_learning_direction
from quicklingo.learning.corpus_analysis import CorpusCandidate


def words_to_candidates(words: list[str], *, direction: str) -> list[CorpusCandidate]:
    kind = resolve_learning_direction(direction)
    candidates: list[CorpusCandidate] = []
    for index, word in enumerate(words, start=1):
        cleaned = word.strip()
        if not cleaned:
            continue
        if kind == "ua-en":
            source_text = ""
            result_text = cleaned
        else:
            source_text = cleaned
            result_text = ""
        candidates.append(
            CorpusCandidate(
                source_text=source_text,
                result_text=result_text,
                record_id=-index,
                reason="ai_word_list",
                priority=3,
            )
        )
    return candidates
