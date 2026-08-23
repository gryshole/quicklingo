from __future__ import annotations

import json
from datetime import UTC, date, datetime

from fsrs import Card as FsrsCard
from fsrs import Rating, Scheduler, State

from quicklingo.db.connection import connection, get_connection
from quicklingo.db.learning import _CARD_SELECT, LearningCard

_scheduler: Scheduler | None = None


def get_scheduler() -> Scheduler:
    global _scheduler
    if _scheduler is None:
        from quicklingo.features import get_feature

        retention = float(get_feature("learning.srs_review").get("desired_retention", 90))
        if retention > 1:
            retention /= 100.0
        _scheduler = Scheduler(desired_retention=retention)
    return _scheduler


def parse_fsrs_card(raw: str, *, default_card_id: int) -> FsrsCard | None:
    """Parse stored FSRS JSON (current or legacy py-fsrs format)."""
    if not raw.strip():
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None

    if "card_id" not in data:
        data = {**data, "card_id": default_card_id}

    if "step" in data:
        try:
            return FsrsCard.from_dict(data)
        except (TypeError, ValueError, KeyError):
            pass

    if "state" not in data:
        return None
    try:
        due = _parse_iso_datetime(data.get("due")) or datetime.now(UTC)
        last_review = _parse_iso_datetime(data.get("last_review"))
        stability = data.get("stability")
        difficulty = data.get("difficulty")
        step = data.get("step", data.get("learning_steps"))
        return FsrsCard(
            card_id=int(data.get("card_id", default_card_id)),
            state=State(int(data["state"])),
            step=int(step) if step is not None else None,
            stability=float(stability) if stability is not None else None,
            difficulty=float(difficulty) if difficulty is not None else None,
            due=due,
            last_review=last_review,
        )
    except (TypeError, ValueError, KeyError):
        return None


def card_fsrs_state(card: LearningCard) -> State | None:
    parsed = parse_fsrs_card(card.fsrs_state or "", default_card_id=card.id)
    return parsed.state if parsed else None


def apply_fsrs_review(card_id: int, rating: Rating) -> None:
    row = _fetch_card_row(card_id)
    if row is None:
        return
    learning_card = _row_to_learning_card(row)
    fsrs_card = _load_fsrs_from_row(row, learning_card)
    updated, _log = get_scheduler().review_card(fsrs_card, rating)
    _save_fsrs_state(card_id, updated)


def _load_fsrs_from_row(row, learning_card: LearningCard) -> FsrsCard:
    raw = row["fsrs_state"] or ""
    if raw.strip():
        parsed = parse_fsrs_card(raw, default_card_id=learning_card.id)
        if parsed is not None:
            return parsed
    due = _parse_due_date(learning_card.next_review_date)
    return FsrsCard(
        card_id=learning_card.id,
        state=State.Learning,
        due=due,
    )


def load_fsrs_card(learning_card: LearningCard) -> FsrsCard:
    row = _fetch_card_row(learning_card.id)
    if row is None:
        raise ValueError(f"Card {learning_card.id} not found")
    return _load_fsrs_from_row(row, learning_card)


def _save_fsrs_state(card_id: int, fsrs_card: FsrsCard) -> None:
    due_date = fsrs_card.due.astimezone(UTC).date().isoformat()
    last_reviewed = ""
    interval_days = 0
    if fsrs_card.last_review is not None:
        last_reviewed = fsrs_card.last_review.astimezone(UTC).date().isoformat()
        due_day = fsrs_card.due.astimezone(UTC).date()
        last_day = fsrs_card.last_review.astimezone(UTC).date()
        interval_days = max(1, (due_day - last_day).days)
    payload = json.dumps(fsrs_card.to_dict())
    with connection() as conn:
        conn.execute(
            """
            UPDATE learning_cards
            SET fsrs_state = ?, next_review_date = ?, last_reviewed = ?, interval_days = ?,
                srs_updated_at = datetime('now')
            WHERE id = ?
            """,
            (payload, due_date, last_reviewed, interval_days, card_id),
        )


def _fetch_card_row(card_id: int):
    return get_connection().execute(
        f"{_CARD_SELECT} WHERE id = ?",
        (card_id,),
    ).fetchone()


def _parse_iso_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _parse_due_date(value: str) -> datetime:
    if value:
        try:
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=UTC)
            return parsed
        except ValueError:
            pass
        try:
            parsed = date.fromisoformat(value)
            return datetime(parsed.year, parsed.month, parsed.day, tzinfo=UTC)
        except ValueError:
            pass
    return datetime.now(UTC)


def _row_to_learning_card(row) -> LearningCard:
    keys = row.keys()
    return LearningCard(
        id=row["id"],
        deck_id=row["deck_id"],
        front=row["front"],
        back=row["back"],
        context=row["context"] or "",
        hint=row["hint"] if "hint" in keys else "",
        notes=row["notes"] if "notes" in keys else "",
        image_path=row["image_path"] if "image_path" in keys else "",
        image_prompt=row["image_prompt"] if "image_prompt" in keys else "",
        phonetic=row["phonetic"] if "phonetic" in keys else "",
        audio_path=row["audio_path"] if "audio_path" in keys else "",
        card_type=row["card_type"] if "card_type" in keys else "basic",
        priority=int(row["priority"]),
        source_record_id=row["source_record_id"],
        ease=float(row["ease"]),
        interval_days=int(row["interval_days"]),
        next_review_date=row["next_review_date"] or "",
        last_reviewed=row["last_reviewed"] or "",
        fsrs_state=row["fsrs_state"] or "",
    )


def preview_fsrs_intervals(learning_card: LearningCard) -> dict[int, int]:
    """Return mapping rating (1-4) -> scheduled days until next review (preview only)."""
    fsrs_card = load_fsrs_card(learning_card)
    scheduler = get_scheduler()
    now = datetime.now(UTC)
    previews: dict[int, int] = {}
    for rating in (Rating.Again, Rating.Hard, Rating.Good, Rating.Easy):
        clone = FsrsCard.from_dict(fsrs_card.to_dict())
        updated, _log = scheduler.review_card(clone, rating)
        delta = updated.due.astimezone(UTC) - now
        previews[rating.value] = max(0, int(delta.total_seconds() // 86400))
    return previews
