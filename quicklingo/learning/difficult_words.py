from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from quicklingo.db import history

_WORD_RE = re.compile(r"[\w']+", re.UNICODE)


@dataclass
class DifficultItem:
    term: str
    count: int
    example_source: str
    example_result: str
    kind: str


from quicklingo.learning.text_normalize import normalize_source as _normalize_source


def compute_difficult_words(records: list[history.TranslationRecord]) -> list[DifficultItem]:
    if not records:
        return []

    source_counts: Counter[str] = Counter()
    source_examples: dict[str, history.TranslationRecord] = {}
    token_records: dict[str, set[int]] = {}
    token_examples: dict[str, history.TranslationRecord] = {}

    for record in records:
        norm = _normalize_source(record.source_text)
        if norm:
            source_counts[norm] += 1
            source_examples.setdefault(norm, record)
        for token in _WORD_RE.findall(record.source_text.lower()):
            if len(token) <= 1:
                continue
            token_records.setdefault(token, set()).add(record.id)
            token_examples.setdefault(token, record)

    items: dict[str, DifficultItem] = {}

    for norm, count in source_counts.items():
        if count < 2:
            continue
        example = source_examples[norm]
        key = f"phrase:{norm}"
        items[key] = DifficultItem(
            term=example.source_text.strip(),
            count=count,
            example_source=example.source_text.strip(),
            example_result=example.result_text.strip(),
            kind="phrase",
        )

    for token, record_ids in token_records.items():
        if len(record_ids) < 3:
            continue
        example = token_examples[token]
        key = f"word:{token}"
        if key in items:
            continue
        items[key] = DifficultItem(
            term=token,
            count=len(record_ids),
            example_source=example.source_text.strip(),
            example_result=example.result_text.strip(),
            kind="word",
        )

    return sorted(items.values(), key=lambda item: (-item.count, item.term.lower()))
