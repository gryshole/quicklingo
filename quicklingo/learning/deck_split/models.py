from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DeckSplitOption:
    id: str
    title: str
    tag: str
    deck_name: str
    rationale: str
    fronts: list[str]
    card_ids: list[int] = field(default_factory=list)


@dataclass(frozen=True)
class DeckSplitAnalysisResult:
    summary: str
    options: list[DeckSplitOption]
    source_deck_id: int
    source_tag: str
    direction: str


@dataclass(frozen=True)
class MoveCardsResult:
    moved: int
    skipped: int
