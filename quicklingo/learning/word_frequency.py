from __future__ import annotations

import re
from collections import Counter

from quicklingo.db import history

_WORD_RE = re.compile(r"[\w']+", re.UNICODE)


def compute_top_words(direction: str, *, top_n: int = 50) -> list[tuple[str, int]]:
    records = history.search_records(direction=direction, limit=5000)
    counter: Counter[str] = Counter()
    for record in records:
        for token in _WORD_RE.findall(record.source_text.lower()):
            if len(token) > 1:
                counter[token] += 1
    return counter.most_common(max(1, top_n))
