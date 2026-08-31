from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from fsrs import State

from quicklingo.db.connection import fetch_all, in_placeholders
from quicklingo.db.learning_decks import list_decks
from quicklingo.learning.quiz.distractor_deck import filter_user_decks
from quicklingo.db.learning_models import LearningCard, LearningDeck
from quicklingo.learning.fsrs_review import card_fsrs_state


@dataclass(frozen=True)
class DeckSummary:
    deck: LearningDeck
    due_count: int
    card_count: int


def _card_bucket(card: LearningCard) -> str:
    if not card.last_reviewed and not (card.fsrs_state or "").strip():
        return "new"
    state = card_fsrs_state(card)
    if state in (State.Learning, State.Relearning):
        return "learning"
    today = date.today().isoformat()
    if card.next_review_date and card.next_review_date <= today:
        return "review"
    if state == State.Review:
        return "review"
    return "review"


def _is_due_for_review(card: LearningCard, today: str) -> bool:
    bucket = _card_bucket(card)
    if bucket == "new":
        return True
    if (
        bucket in ("learning", "review")
        and card.next_review_date
        and card.next_review_date <= today
    ):
        return True
    return False


def count_due_cards_map(deck_ids: list[int]) -> dict[int, int]:
    if not deck_ids:
        return {}
    today = date.today().isoformat()
    placeholders = in_placeholders(len(deck_ids))
    rows = fetch_all(
        f"""
        SELECT id, deck_id, last_reviewed, fsrs_state, next_review_date
        FROM learning_cards
        WHERE deck_id IN ({placeholders})
          AND card_type != 'quiz_distractor'
        """,
        deck_ids,
    )
    counts = {deck_id: 0 for deck_id in deck_ids}
    for row in rows:
        card = LearningCard(
            id=int(row["id"]),
            deck_id=int(row["deck_id"]),
            front="",
            back="",
            last_reviewed=str(row["last_reviewed"] or ""),
            fsrs_state=str(row["fsrs_state"] or ""),
            next_review_date=str(row["next_review_date"] or ""),
        )
        if _is_due_for_review(card, today):
            counts[int(row["deck_id"])] += 1
    return counts


def count_due_cards(deck_id: int) -> int:
    return count_due_cards_map([deck_id]).get(deck_id, 0)


def count_cards_map(deck_ids: list[int]) -> dict[int, int]:
    if not deck_ids:
        return {}
    placeholders = in_placeholders(len(deck_ids))
    rows = fetch_all(
        f"""
        SELECT deck_id, COUNT(*) AS cnt
        FROM learning_cards
        WHERE deck_id IN ({placeholders})
        GROUP BY deck_id
        """,
        deck_ids,
    )
    counts = {deck_id: 0 for deck_id in deck_ids}
    for row in rows:
        counts[int(row["deck_id"])] = int(row["cnt"])
    return counts


def get_deck_summaries() -> list[DeckSummary]:
    decks = filter_user_decks(list_decks())
    deck_ids = [deck.id for deck in decks]
    due_map = count_due_cards_map(deck_ids)
    card_map = count_cards_map(deck_ids)
    return [
        DeckSummary(
            deck=deck,
            due_count=due_map.get(deck.id, 0),
            card_count=card_map.get(deck.id, 0),
        )
        for deck in decks
    ]
