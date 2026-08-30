from __future__ import annotations

from datetime import date, timedelta

from quicklingo.config.loader import resolve_learning_direction
from quicklingo.db.connection import connection, fetch_all, scalar_int
from quicklingo.db.learning_cards import list_cards, list_cards_by_ids
from quicklingo.db.learning_decks import get_deck, list_decks
from quicklingo.db.learning_models import (
    LearningCard,
    LearningDeck,
    QuizCoverageStats,
    QUIZ_QUESTION_TYPES,
)
from quicklingo.learning.card_prompt import hint_pos_matches
from quicklingo.learning.quiz.eligibility import is_quiz_eligible
from quicklingo.learning.quiz.normalize import card_to_quiz_word


def insert_review_log(
    card_id: int,
    *,
    rating: int,
    mode: str = "flip",
    was_correct: bool | None = None,
    response_ms: int | None = None,
) -> None:
    with connection() as conn:
        conn.execute(
            """
            INSERT INTO review_logs (card_id, rating, mode, was_correct, response_ms)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                card_id,
                rating,
                mode,
                None if was_correct is None else int(was_correct),
                response_ms,
            ),
        )


def get_quiz_coverage(deck_id: int) -> QuizCoverageStats:
    deck = get_deck(deck_id)
    if deck is None:
        return QuizCoverageStats(eligible=0, ready=0, missing_any=0, missing_by_type={})

    kind = resolve_learning_direction(deck.direction)
    if kind not in ("ua-en", "en-ua"):
        return QuizCoverageStats(eligible=0, ready=0, missing_any=0, missing_by_type={})

    cards = list_cards(deck_id)
    question_rows = fetch_all(
        """
        SELECT qq.card_id, qq.question_type
        FROM quiz_questions qq
        INNER JOIN learning_cards c ON c.id = qq.card_id
        WHERE c.deck_id = ? AND qq.status = 'active'
        """,
        (deck_id,),
    )
    active_by_card: dict[int, set[str]] = {}
    for row in question_rows:
        card_id = int(row["card_id"])
        active_by_card.setdefault(card_id, set()).add(str(row["question_type"]))

    ready = 0
    missing_by_type = {qtype: 0 for qtype in QUIZ_QUESTION_TYPES}
    eligible = 0

    for card in cards:
        word = card_to_quiz_word(card, deck.direction)
        if not is_quiz_eligible(card, word):
            continue
        eligible += 1
        active_types = active_by_card.get(card.id, set())
        if len(active_types) >= len(QUIZ_QUESTION_TYPES):
            ready += 1
        else:
            for qtype in QUIZ_QUESTION_TYPES:
                if qtype not in active_types:
                    missing_by_type[qtype] += 1

    return QuizCoverageStats(
        eligible=eligible,
        ready=ready,
        missing_any=max(0, eligible - ready),
        missing_by_type=missing_by_type,
    )


def count_failed_quiz_questions_for_deck(deck_id: int) -> int:
    return scalar_int(
        """
        SELECT COUNT(*) AS cnt
        FROM quiz_questions qq
        INNER JOIN learning_cards c ON c.id = qq.card_id
        WHERE c.deck_id = ? AND qq.status = 'failed'
        """,
        (deck_id,),
    )


def record_review(
    card_id: int,
    *,
    again: bool | None = None,
    fsrs_rating=None,
    mode: str = "flip",
    was_correct: bool | None = None,
    response_ms: int | None = None,
) -> None:
    from quicklingo.features import is_enabled

    if fsrs_rating is not None:
        rating_value = int(getattr(fsrs_rating, "value", fsrs_rating))
    else:
        rating_value = 1 if again else 3
    insert_review_log(
        card_id,
        rating=rating_value,
        mode=mode,
        was_correct=was_correct,
        response_ms=response_ms,
    )
    if is_enabled("learning.srs_review") and fsrs_rating is not None:
        from quicklingo.learning.fsrs_review import apply_fsrs_review

        apply_fsrs_review(card_id, fsrs_rating)
        return
    _record_review_lite(card_id, again=bool(again))


def _record_review_lite(card_id: int, *, again: bool) -> None:
    today = date.today()
    today_str = today.isoformat()
    with connection() as conn:
        row = conn.execute(
            """
            SELECT interval_days FROM learning_cards WHERE id = ?
            """,
            (card_id,),
        ).fetchone()
        if not row:
            return
        interval = int(row["interval_days"])
        if again:
            new_interval = 1
        else:
            new_interval = min(30, max(1, interval * 2 if interval else 1))
        next_review = (today + timedelta(days=new_interval)).isoformat()
        conn.execute(
            """
            UPDATE learning_cards
            SET interval_days = ?, next_review_date = ?, last_reviewed = ?,
                srs_updated_at = datetime('now')
            WHERE id = ?
            """,
            (new_interval, next_review, today_str, card_id),
        )


def list_quiz_english_words(
    *,
    pos_prefix: str | None = None,
    exclude: set[str] | None = None,
) -> list[str]:
    from quicklingo.config.loader import resolve_learning_direction
    from quicklingo.learning.card_prompt import hint_pos_matches
    from quicklingo.learning.review_queue import english_side_text

    exclude_lower = {word.lower() for word in (exclude or set())}
    seen: set[str] = set()
    results: list[str] = []
    for deck in list_decks():
        if resolve_learning_direction(deck.direction) not in ("ua-en", "en-ua"):
            continue
        for card in list_cards(deck.id):
            english = english_side_text(card, deck.direction).strip()
            key = english.lower()
            if not english or key in exclude_lower or key in seen:
                continue
            if pos_prefix and not hint_pos_matches(card.hint, pos_prefix):
                continue
            seen.add(key)
            results.append(english)
    return results
