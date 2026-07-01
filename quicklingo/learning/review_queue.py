from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date

from fsrs import Card as FsrsCard
from fsrs import State

from quicklingo.db.learning import LearningCard, list_cards


@dataclass
class SessionQueue:
    cards: list[LearningCard] = field(default_factory=list)
    position: int = 0
    requeue_buffer: list[tuple[LearningCard, int]] = field(default_factory=list)
    completed: int = 0
    new_seen: int = 0

    @property
    def total(self) -> int:
        return len(self.cards)

    @property
    def finished(self) -> bool:
        return self.position >= len(self.cards)

    def current(self) -> LearningCard | None:
        if self.finished:
            return None
        return self.cards[self.position]


def card_bucket(card: LearningCard) -> str:
    if not card.last_reviewed and not (card.fsrs_state or "").strip():
        return "new"
    state = _fsrs_state(card)
    if state in (State.Learning, State.Relearning):
        return "learning"
    today = date.today().isoformat()
    if card.next_review_date and card.next_review_date <= today:
        return "review"
    if state == State.Review:
        return "review"
    return "review"


def _fsrs_state(card: LearningCard) -> State | None:
    raw = card.fsrs_state or ""
    if not raw.strip():
        return None
    try:
        return FsrsCard.from_dict(json.loads(raw)).state
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def build_session_queue(
    deck_id: int,
    *,
    limit: int = 20,
    new_limit: int = 10,
) -> SessionQueue:
    cards = list_cards(deck_id)
    today = date.today().isoformat()
    learning: list[LearningCard] = []
    due_review: list[LearningCard] = []
    new_cards: list[LearningCard] = []

    for card in cards:
        bucket = card_bucket(card)
        if bucket == "new":
            new_cards.append(card)
        elif bucket == "learning":
            learning.append(card)
        elif card.next_review_date and card.next_review_date <= today:
            due_review.append(card)

    def sort_key(card: LearningCard) -> tuple[int, int]:
        return (-card.priority, card.id)

    learning.sort(key=sort_key)
    due_review.sort(key=sort_key)
    new_cards.sort(key=sort_key)

    selected: list[LearningCard] = []
    selected.extend(learning)
    remaining = max(0, limit - len(selected))
    selected.extend(due_review[:remaining])
    remaining = max(0, limit - len(selected))
    selected.extend(new_cards[: min(new_limit, remaining)])

    return SessionQueue(cards=selected)


def requeue_in_session(queue: SessionQueue, card: LearningCard, rating: int, *, offset: int = 3) -> None:
    if rating > 1:
        return
    insert_at = min(len(queue.cards), queue.position + max(1, offset))
    queue.cards.insert(insert_at, card)


def count_due_cards(deck_id: int) -> int:
    today = date.today().isoformat()
    count = 0
    for card in list_cards(deck_id):
        bucket = card_bucket(card)
        if bucket in ("learning", "review") and card.next_review_date and card.next_review_date <= today:
            count += 1
        elif bucket == "new":
            count += 1
    return count


def count_due_today_all_decks() -> int:
    total = 0
    from quicklingo.db import learning

    for deck in learning.list_decks():
        total += count_due_cards(deck.id)
    return total


def english_side_text(card: LearningCard, direction: str) -> str:
    if direction.startswith("en"):
        return card.front.strip()
    if direction.endswith("en"):
        return card.back.strip()
    return card.front.strip()
