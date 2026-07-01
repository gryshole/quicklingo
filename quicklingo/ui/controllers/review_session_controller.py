from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Literal

from fsrs import Rating

from quicklingo import settings
from quicklingo.db import learning
from quicklingo.features import get_feature, is_enabled
from quicklingo.learning.answer_check import AnswerResult, check_answer
from quicklingo.learning.cram_queue import build_cram_queue
from quicklingo.learning.pronunciation import ensure_card_pronunciation, resolve_audio_path
from quicklingo.learning.review_queue import (
    SessionQueue,
    build_session_queue,
    card_bucket,
    requeue_in_session,
)

StudyMode = Literal["normal", "cram"]


@dataclass
class SessionStats:
    total: int = 0
    answered: int = 0
    correct: int = 0
    partial: int = 0
    wrong: int = 0
    started_at: float = field(default_factory=time.monotonic)

    @property
    def accuracy(self) -> float:
        if self.answered == 0:
            return 0.0
        return (self.correct + self.partial * 0.5) / self.answered

    @property
    def elapsed_seconds(self) -> int:
        return max(0, int(time.monotonic() - self.started_at))


class ReviewSessionController:
    def __init__(self) -> None:
        self._deck_id: int | None = None
        self._direction = "ua-en"
        self._mode = "flip"
        self._study_mode: StudyMode = "normal"
        self._queue = SessionQueue()
        self._stats = SessionStats()
        self._revealed = False
        self._typing_result: AnswerResult | None = None
        self._response_started: float | None = None
        self._session_active = False
        self._normal_session_card_ids: list[int] = []
        self._session_snapshots: dict[int, list[int]] = {}

    @property
    def session_active(self) -> bool:
        return self._session_active

    @property
    def study_mode(self) -> StudyMode:
        return self._study_mode

    @property
    def is_cram(self) -> bool:
        return self._study_mode == "cram"

    @property
    def last_normal_session_card_ids(self) -> list[int]:
        if self._deck_id is None:
            return []
        return list(self._session_snapshots.get(self._deck_id, []))

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def stats(self) -> SessionStats:
        return self._stats

    @property
    def revealed(self) -> bool:
        return self._revealed

    @property
    def typing_result(self) -> AnswerResult | None:
        return self._typing_result

    @property
    def queue_position(self) -> int:
        return self._queue.position

    def current_card(self) -> learning.LearningCard | None:
        return self._queue.current()

    def start_session(self, deck_id: int, *, direction: str, mode: str = "flip") -> bool:
        if not is_enabled("learning.daily_review"):
            return False
        limit = int(get_feature("learning.daily_review").get("daily_limit", 20))
        new_limit = int(get_feature("learning.srs_review").get("new_cards_per_day", 10))
        queue = build_session_queue(deck_id, limit=limit, new_limit=new_limit)
        if not queue.cards:
            self._session_active = False
            return False
        self._deck_id = deck_id
        self._direction = direction
        self._mode = mode if is_enabled("learning.review_typing") or mode == "flip" else "flip"
        self._study_mode = "normal"
        self._normal_session_card_ids = []
        self._queue = queue
        self._stats = SessionStats(total=len(queue.cards))
        self._revealed = False
        self._typing_result = None
        self._response_started = time.monotonic()
        self._session_active = True
        return True

    def start_cram_session(
        self,
        deck_id: int,
        cards: list[learning.LearningCard],
        *,
        direction: str,
        mode: str = "flip",
    ) -> bool:
        if not cards:
            self._session_active = False
            return False
        self._deck_id = deck_id
        self._direction = direction
        self._mode = mode if is_enabled("learning.review_typing") or mode == "flip" else "flip"
        self._study_mode = "cram"
        self._queue = build_cram_queue(cards)
        self._stats = SessionStats(total=len(self._queue.cards))
        self._revealed = False
        self._typing_result = None
        self._response_started = time.monotonic()
        self._session_active = True
        return True

    def reset(self) -> None:
        self._session_active = False
        self._study_mode = "normal"
        self._queue = SessionQueue()
        self._revealed = False
        self._typing_result = None
        self._normal_session_card_ids = []

    def reveal(self) -> None:
        if not self._session_active or self._revealed:
            return
        self._revealed = True

    def check_typing(self, user_input: str) -> AnswerResult:
        card = self.current_card()
        if card is None:
            return AnswerResult.WRONG
        result = check_answer(user_input, card.back)
        self._typing_result = result
        self._revealed = True
        if result == AnswerResult.CORRECT:
            self._stats.correct += 1
        elif result == AnswerResult.PARTIAL:
            self._stats.partial += 1
        else:
            self._stats.wrong += 1
        self._stats.answered += 1
        return result

    def suggested_rating(self) -> int:
        if self._typing_result == AnswerResult.CORRECT:
            return 3
        if self._typing_result == AnswerResult.PARTIAL:
            return 2
        if self._typing_result == AnswerResult.WRONG:
            return 1
        return 3

    def submit_grade(self, rating_value: int) -> bool:
        card = self.current_card()
        if card is None or not self._session_active:
            return False
        response_ms = None
        if self._response_started is not None:
            response_ms = int((time.monotonic() - self._response_started) * 1000)
        uses_fsrs = is_enabled("learning.srs_review")
        was_correct = None
        if self._mode == "typing" and self._typing_result is not None:
            was_correct = self._typing_result == AnswerResult.CORRECT
        if self._study_mode == "normal":
            if card.id not in self._normal_session_card_ids:
                self._normal_session_card_ids.append(card.id)
            if uses_fsrs:
                learning.record_review(
                    card.id,
                    fsrs_rating=Rating(rating_value),
                    mode=self._mode,
                    was_correct=was_correct,
                    response_ms=response_ms,
                )
            else:
                learning.record_review(
                    card.id,
                    again=rating_value == 1,
                    mode=self._mode,
                    was_correct=was_correct,
                    response_ms=response_ms,
                )
        requeue_in_session(self._queue, card, rating_value)
        self._queue.completed += 1
        self._queue.position += 1
        self._revealed = False
        self._typing_result = None
        self._response_started = time.monotonic()
        if self._queue.finished:
            self._session_active = False
            if self._study_mode == "normal":
                if self._deck_id is not None and self._normal_session_card_ids:
                    self._session_snapshots[self._deck_id] = list(self._normal_session_card_ids)
                if is_enabled("learning.streak"):
                    settings.record_learning_review_today()
        return True

    def bucket_counts(self) -> dict[str, int]:
        counts = {"new": 0, "learning": 0, "review": 0}
        for card in self._queue.cards:
            bucket = card_bucket(card)
            if bucket in counts:
                counts[bucket] += 1
        return counts

    def ensure_pronunciation(self) -> str | None:
        card = self.current_card()
        if card is None or not is_enabled("learning.card_pronunciation"):
            return None
        updated = ensure_card_pronunciation(card.id, direction=self._direction)
        if updated is None:
            return None
        path = resolve_audio_path(updated)
        return str(path) if path else None

    def audio_path_for_current(self) -> str | None:
        card = self.current_card()
        if card is None:
            return None
        path = resolve_audio_path(card)
        return str(path) if path else None
