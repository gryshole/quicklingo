from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from quicklingo import settings as app_settings
from quicklingo.config.loader import resolve_learning_direction
from quicklingo.db.connection import connection
from quicklingo.db.learning_decks import get_deck, get_or_create_deck
from quicklingo.db.learning_models import LearningCard
from quicklingo.db.tombstones import record_card_delete
from quicklingo.learning.quiz.distractor_deck import (
    QUIZ_DISTRACTOR_DECK_TAG,
    is_quiz_distractor_card,
    is_quiz_distractor_deck,
)
from quicklingo.learning.text_normalize import normalize_source


@dataclass(frozen=True)
class DistractorTransferResult:
    moved: int
    merged: int
    skipped: int


def transfer_distractor_cards(
    card_ids: list[int],
    target_tag: str,
    direction: str,
    *,
    deck_name: str | None = None,
) -> DistractorTransferResult:
    """Move distractor cards into a user deck by tag; merge duplicates by front."""
    tag = (target_tag or "").strip()
    if not tag or tag == QUIZ_DISTRACTOR_DECK_TAG:
        return DistractorTransferResult(moved=0, merged=0, skipped=len(card_ids))
    name = (deck_name or tag).strip() or tag
    target_deck = get_or_create_deck(name, tag, direction)
    today = date.today().isoformat()
    device_id = app_settings.get_sync_device_id()
    moved = 0
    merged = 0
    skipped = 0

    with connection() as conn:
        for card_id in card_ids:
            row = conn.execute(
                """
                SELECT id, deck_id, front, back, context, hint, notes, card_type
                FROM learning_cards
                WHERE id = ?
                """,
                (card_id,),
            ).fetchone()
            if row is None:
                skipped += 1
                continue
            source_deck = get_deck(int(row["deck_id"]))
            if source_deck is None:
                skipped += 1
                continue
            card = LearningCard(
                id=int(row["id"]),
                deck_id=int(row["deck_id"]),
                front=row["front"] or "",
                back=row["back"] or "",
                context=row["context"] or "",
                hint=row["hint"] or "",
                notes=row["notes"] or "",
                card_type=row["card_type"] or "basic",
            )
            if not is_quiz_distractor_deck(source_deck):
                skipped += 1
                continue
            if resolve_learning_direction(source_deck.direction) != resolve_learning_direction(
                direction
            ):
                skipped += 1
                continue
            if not is_quiz_distractor_card(card, source_deck):
                skipped += 1
                continue

            normalized_front = normalize_source(card.front)
            existing = conn.execute(
                """
                SELECT id, back, context, hint, notes
                FROM learning_cards
                WHERE deck_id = ? AND lower(trim(front)) = ?
                """,
                (target_deck.id, normalized_front),
            ).fetchone()

            if existing:
                merge_back = existing["back"] or ""
                merge_context = existing["context"] or ""
                merge_hint = existing["hint"] or ""
                merge_notes = existing["notes"] or ""
                if not merge_back.strip() and card.back.strip():
                    merge_back = card.back
                if not merge_context.strip() and card.context.strip():
                    merge_context = card.context
                if not merge_hint.strip() and card.hint.strip():
                    merge_hint = card.hint
                if not merge_notes.strip() and card.notes.strip():
                    merge_notes = card.notes
                conn.execute(
                    """
                    UPDATE learning_cards
                    SET back = ?, context = ?, hint = ?, notes = ?,
                        content_updated_at = datetime('now')
                    WHERE id = ?
                    """,
                    (
                        merge_back,
                        merge_context,
                        merge_hint,
                        merge_notes,
                        int(existing["id"]),
                    ),
                )
                record_card_delete(card_id, device_id=device_id, conn=conn)
                conn.execute("DELETE FROM learning_cards WHERE id = ?", (card_id,))
                merged += 1
            else:
                conn.execute(
                    """
                    UPDATE learning_cards
                    SET deck_id = ?, card_type = ?, next_review_date = ?,
                        ease = 2.5, interval_days = 0, fsrs_state = '',
                        last_reviewed = '', content_updated_at = datetime('now')
                    WHERE id = ?
                    """,
                    (target_deck.id, "basic", today, card_id),
                )
                moved += 1

    return DistractorTransferResult(moved=moved, merged=merged, skipped=skipped)
