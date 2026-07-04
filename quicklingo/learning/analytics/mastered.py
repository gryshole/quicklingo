from __future__ import annotations

import json
from datetime import date

from fsrs import Card as FsrsCard
from fsrs import State

from quicklingo.db.learning import LearningCard

MASTERED_INTERVAL_DAYS = 21


def _fsrs_state(card: LearningCard) -> State | None:
    raw = card.fsrs_state or ""
    if not raw.strip():
        return None
    try:
        return FsrsCard.from_dict(json.loads(raw)).state
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def _scheduled_interval_days(card: LearningCard) -> int:
    if card.next_review_date and card.last_reviewed:
        try:
            due = date.fromisoformat(card.next_review_date[:10])
            last = date.fromisoformat(card.last_reviewed[:10])
            return max(0, (due - last).days)
        except ValueError:
            pass
    return int(card.interval_days or 0)


def is_mastered(card: LearningCard) -> bool:
    if not (card.last_reviewed or "").strip():
        return False
    interval = _scheduled_interval_days(card)
    state = _fsrs_state(card)
    if state is not None:
        return state == State.Review and interval >= MASTERED_INTERVAL_DAYS
    return interval >= MASTERED_INTERVAL_DAYS


def is_learning(card: LearningCard) -> bool:
    if not (card.last_reviewed or "").strip() and not (card.fsrs_state or "").strip():
        return False
    return not is_mastered(card)
