from __future__ import annotations

import json

from fsrs import Card as FsrsCard
from fsrs import State

from quicklingo.db.learning import LearningCard

MASTERED_INTERVAL_DAYS = 21


def is_mastered(card: LearningCard) -> bool:
    if card.interval_days < MASTERED_INTERVAL_DAYS:
        return False
    if not (card.last_reviewed or "").strip():
        return False
    state = _fsrs_state(card)
    if state is None:
        return True
    return state == State.Review


def _fsrs_state(card: LearningCard) -> State | None:
    raw = card.fsrs_state or ""
    if not raw.strip():
        return None
    try:
        return FsrsCard.from_dict(json.loads(raw)).state
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def is_learning(card: LearningCard) -> bool:
    if not (card.last_reviewed or "").strip() and not (card.fsrs_state or "").strip():
        return False
    return not is_mastered(card)
