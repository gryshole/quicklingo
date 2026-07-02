from __future__ import annotations

from dataclasses import dataclass

CEFR_LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2")

TAG_PATTERN = r"^[a-z0-9_\-]{2,40}$"


@dataclass(frozen=True)
class AiDeckParams:
    tag: str
    level: str
    topic_key: str
    custom_topic: str
    lexicon_type: str
    word_count: int
    direction: str
    merge_existing: bool = False

    def normalized_tag(self) -> str:
        return self.tag.strip().lower()
