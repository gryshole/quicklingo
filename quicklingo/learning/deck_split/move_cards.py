from __future__ import annotations

from quicklingo.config.loader import resolve_learning_direction
from quicklingo.db.connection import connection
from quicklingo.db.learning_decks import get_deck, get_or_create_deck
from quicklingo.learning.deck_split.models import MoveCardsResult
from quicklingo.learning.quiz.distractor_deck import (
    QUIZ_DISTRACTOR_DECK_TAG,
    is_quiz_distractor_deck,
)
from quicklingo.learning.text_normalize import normalize_source


def move_cards_to_deck(
    card_ids: list[int],
    target_tag: str,
    direction: str,
    *,
    deck_name: str | None = None,
) -> MoveCardsResult:
    tag = (target_tag or "").strip().lower()
    if not tag or tag == QUIZ_DISTRACTOR_DECK_TAG:
        return MoveCardsResult(moved=0, skipped=len(card_ids))
    name = (deck_name or tag).strip() or tag
    target_deck = get_or_create_deck(name, tag, direction)
    moved = 0
    skipped = 0

    with connection() as conn:
        for card_id in card_ids:
            row = conn.execute(
                "SELECT id, deck_id, front FROM learning_cards WHERE id = ?",
                (card_id,),
            ).fetchone()
            if row is None:
                skipped += 1
                continue
            source_deck = get_deck(int(row["deck_id"]))
            if source_deck is None or is_quiz_distractor_deck(source_deck):
                skipped += 1
                continue
            if resolve_learning_direction(source_deck.direction) != resolve_learning_direction(
                direction
            ):
                skipped += 1
                continue
            normalized_front = normalize_source(str(row["front"]))
            existing = conn.execute(
                """
                SELECT id FROM learning_cards
                WHERE deck_id = ? AND lower(trim(front)) = ?
                """,
                (target_deck.id, normalized_front),
            ).fetchone()
            if existing:
                skipped += 1
                continue
            conn.execute(
                """
                UPDATE learning_cards
                SET deck_id = ?, content_updated_at = datetime('now')
                WHERE id = ?
                """,
                (target_deck.id, card_id),
            )
            moved += 1

    return MoveCardsResult(moved=moved, skipped=skipped)
