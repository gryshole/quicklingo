from __future__ import annotations

from quicklingo.db import learning
from quicklingo.features import get_feature
from quicklingo.learning.quiz.ai_quiz_service import record_to_quiz_question
from quicklingo.learning.quiz.choice_sampler import sample_display_choices
from quicklingo.learning.quiz.models import QuizQuestion, QuizQuestionType, QuizWordDto
from quicklingo.learning.quiz.type_picker import pick_question_type


class DbQuizGenerator:
    def build_questions(self, words: list[QuizWordDto]) -> list[QuizQuestion]:
        if not words:
            return []
        card_ids = [word.card_id for word in words]
        records = learning.list_quiz_questions_for_cards(card_ids, status="active")
        by_card: dict[int, dict[str, learning.QuizQuestionRecord]] = {}
        for record in records:
            by_card.setdefault(record.card_id, {})[record.question_type] = record
        display_count = int(get_feature("learning.quiz").get("choices_display_count", 4))
        questions: list[QuizQuestion] = []
        for word in words:
            type_map = by_card.get(word.card_id, {})
            if len(type_map) < 3:
                continue
            qtype = pick_question_type(word.card_id)
            record = type_map.get(qtype.value)
            if record is None:
                record = next(iter(type_map.values()))
                qtype = QuizQuestionType(record.question_type)
            choices = sample_display_choices(
                record.choices_pool,
                record.correct_english,
                display_count=display_count,
            )
            if len(choices) < 2:
                continue
            questions.append(
                record_to_quiz_question(
                    index=len(questions),
                    word=word,
                    qtype=qtype,
                    record=record,
                    choices=choices,
                )
            )
        return questions
