from __future__ import annotations

import json
from datetime import date, datetime, timezone

from fsrs import Card as FsrsCard
from fsrs import Rating, Scheduler, State

from quicklingo.db.history import _connect
from quicklingo.db.learning import LearningCard

_scheduler: Scheduler | None = None


def get_scheduler() -> Scheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = Scheduler()
    return _scheduler


def load_fsrs_card(learning_card: LearningCard) -> FsrsCard:
    row = _fetch_card_row(learning_card.id)
    if row is None:
        raise ValueError(f"Card {learning_card.id} not found")
    raw = row["fsrs_state"] or ""
    if raw.strip():
        return FsrsCard.from_dict(json.loads(raw))
    due = _parse_due_date(learning_card.next_review_date)
    return FsrsCard(
        card_id=learning_card.id,
        state=State.Learning,
        due=due,
    )


def apply_fsrs_review(card_id: int, rating: Rating) -> None:
    row = _fetch_card_row(card_id)
    if row is None:
        return
    learning_card = _row_to_learning_card(row)
    fsrs_card = load_fsrs_card(learning_card)
    updated, _log = get_scheduler().review_card(fsrs_card, rating)
    _save_fsrs_state(card_id, updated)


def _save_fsrs_state(card_id: int, fsrs_card: FsrsCard) -> None:
    due_date = fsrs_card.due.astimezone(timezone.utc).date().isoformat()
    last_reviewed = ""
    if fsrs_card.last_review is not None:
        last_reviewed = fsrs_card.last_review.astimezone(timezone.utc).date().isoformat()
    payload = json.dumps(fsrs_card.to_dict())
    with _connect() as conn:
        conn.execute(
            """
            UPDATE learning_cards
            SET fsrs_state = ?, next_review_date = ?, last_reviewed = ?
            WHERE id = ?
            """,
            (payload, due_date, last_reviewed, card_id),
        )


def _parse_due_date(value: str) -> datetime:
    if value:
        try:
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            pass
        try:
            parsed = date.fromisoformat(value)
            return datetime(parsed.year, parsed.month, parsed.day, tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _fetch_card_row(card_id: int):
    with _connect() as conn:
        return conn.execute(
            """
            SELECT id, deck_id, front, back, context, priority, source_record_id,
                   ease, interval_days, next_review_date, last_reviewed, fsrs_state
            FROM learning_cards
            WHERE id = ?
            """,
            (card_id,),
        ).fetchone()


def _row_to_learning_card(row) -> LearningCard:
    return LearningCard(
        id=row["id"],
        deck_id=row["deck_id"],
        front=row["front"],
        back=row["back"],
        context=row["context"] or "",
        priority=int(row["priority"]),
        source_record_id=row["source_record_id"],
        ease=float(row["ease"]),
        interval_days=int(row["interval_days"]),
        next_review_date=row["next_review_date"] or "",
        last_reviewed=row["last_reviewed"] or "",
        fsrs_state=row["fsrs_state"] or "",
    )
