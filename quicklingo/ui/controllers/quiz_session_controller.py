from __future__ import annotations

import time

from quicklingo.features import get_feature, is_enabled
from quicklingo.learning.quiz.aggregator import build_quiz_pool
from quicklingo.learning.quiz.generator import get_quiz_generator
from quicklingo.learning.quiz.models import QuizAnswer, QuizQuestion, QuizResult, QuizSessionState, QuizWordDto


class QuizSessionController:
    def __init__(self) -> None:
        self._state = QuizSessionState()
        self._active = False
        self._answer_started: float | None = None

    @property
    def session_active(self) -> bool:
        return self._active

    def start_session(self, tag: str | None = None) -> bool:
        if not is_enabled("learning.quiz"):
            return False
        limit = int(get_feature("learning.quiz").get("question_count", 15))
        words = build_quiz_pool(limit=limit, tag=tag or None)
        if not words:
            self._active = False
            self._state = QuizSessionState()
            return False
        generator = get_quiz_generator()
        self._state = QuizSessionState(
            words=words,
            questions=generator.build_questions(words),
            answers=[],
            started_at=time.monotonic(),
            position=0,
        )
        self._active = True
        self._answer_started = time.monotonic()
        return True

    def current_question(self) -> QuizQuestion | None:
        if not self._active or self.is_finished():
            return None
        return self._state.questions[self._state.position]

    def submit_answer(self, choice: str) -> bool:
        question = self.current_question()
        if question is None:
            return False
        elapsed_ms = 0
        if self._answer_started is not None:
            elapsed_ms = int((time.monotonic() - self._answer_started) * 1000)
        correct = choice.strip().lower() == question.correct_english.strip().lower()
        self._state.answers.append(
            QuizAnswer(
                question_index=question.index,
                selected=choice,
                correct=correct,
                elapsed_ms=elapsed_ms,
            )
        )
        self._state.position += 1
        self._answer_started = time.monotonic()
        if self.is_finished():
            self._active = False
        return correct

    def is_finished(self) -> bool:
        return self._state.position >= len(self._state.questions)

    def result(self) -> QuizResult:
        score = sum(1 for answer in self._state.answers if answer.correct)
        total = len(self._state.questions)
        wrong_card_ids: set[int] = set()
        for answer in self._state.answers:
            if answer.correct:
                continue
            question = self.question_for_answer(answer)
            if question is not None:
                wrong_card_ids.add(question.source_card_id)
        wrong_words = [word for word in self._state.words if word.card_id in wrong_card_ids]
        return QuizResult(score=score, total=total, wrong_words=wrong_words)

    def progress(self) -> tuple[int, int]:
        total = len(self._state.questions)
        if total == 0:
            return (0, 0)
        current = min(self._state.position + 1, total)
        if self.is_finished():
            current = total
        return (current, total)

    def words_by_id(self) -> dict[int, QuizWordDto]:
        return {word.card_id: word for word in self._state.words}

    def last_answer(self) -> QuizAnswer | None:
        if not self._state.answers:
            return None
        return self._state.answers[-1]

    def question_for_answer(self, answer: QuizAnswer) -> QuizQuestion | None:
        for question in self._state.questions:
            if question.index == answer.question_index:
                return question
        return None

    def answers(self) -> list[QuizAnswer]:
        return list(self._state.answers)

    def questions(self) -> list[QuizQuestion]:
        return list(self._state.questions)

    def reset(self) -> None:
        self._active = False
        self._state = QuizSessionState()
        self._answer_started = None

    def persist_session_logs(self) -> None:
        from quicklingo.db import learning

        entries: list[dict[str, object]] = []
        for answer in self._state.answers:
            question = self.question_for_answer(answer)
            if question is None:
                continue
            entries.append(
                {
                    "card_id": question.source_card_id,
                    "question_type": question.type.value,
                    "selected": answer.selected,
                    "correct": answer.correct,
                    "response_ms": answer.elapsed_ms,
                }
            )
        learning.batch_insert_quiz_logs(entries)
