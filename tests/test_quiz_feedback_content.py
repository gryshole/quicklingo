from __future__ import annotations

import unittest

from quicklingo.learning.quiz.models import QuizQuestionType, QuizWordDto
from quicklingo.learning.quiz.quiz_feedback_content import (
    build_quiz_feedback_content,
    is_choice_visible_in_feedback,
)


class QuizFeedbackContentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sample_word = QuizWordDto(
            card_id=1,
            english="covenant",
            ukrainian="угода",
            definition="a formal agreement",
            examples=[
                "The company signed a covenant with the supplier.",
                "They entered a sacred covenant.",
                "A third example sentence.",
                "A fourth example sentence.",
            ],
            distractors=[],
            hint_pos="",
        )

    def test_definition_match_hides_definition(self) -> None:
        content = build_quiz_feedback_content(
            self.sample_word,
            QuizQuestionType.DEFINITION_MATCH,
        )
        self.assertIsNone(content.definition)
        self.assertEqual(content.ukrainian, "угода")
        self.assertEqual(len(content.examples), 3)

    def test_translation_recall_hides_ukrainian(self) -> None:
        content = build_quiz_feedback_content(
            self.sample_word,
            QuizQuestionType.TRANSLATION_RECALL,
        )
        self.assertEqual(content.definition, "a formal agreement")
        self.assertIsNone(content.ukrainian)

    def test_fill_blank_excludes_quiz_sentence(self) -> None:
        content = build_quiz_feedback_content(
            self.sample_word,
            QuizQuestionType.FILL_BLANK,
            exclude_sentences=["The company signed a covenant with the supplier."],
        )
        self.assertNotIn(
            "The company signed a covenant with the supplier.",
            content.examples,
        )
        self.assertEqual(content.definition, "a formal agreement")

    def test_correct_feedback_shows_only_correct_choice(self) -> None:
        options = {
            "last_correct": True,
            "selected_choice": "covenant",
            "correct_english": "covenant",
        }
        self.assertTrue(
            is_choice_visible_in_feedback("covenant", "feedback", **options)
        )
        self.assertFalse(
            is_choice_visible_in_feedback("bicycle", "feedback", **options)
        )

    def test_wrong_feedback_shows_selected_and_correct(self) -> None:
        options = {
            "last_correct": False,
            "selected_choice": "bicycle",
            "correct_english": "covenant",
        }
        self.assertTrue(
            is_choice_visible_in_feedback("bicycle", "feedback", **options)
        )
        self.assertTrue(
            is_choice_visible_in_feedback("covenant", "feedback", **options)
        )
        self.assertFalse(
            is_choice_visible_in_feedback("kitten", "feedback", **options)
        )

    def test_session_phase_shows_all_choices(self) -> None:
        options = {
            "last_correct": False,
            "selected_choice": "bicycle",
            "correct_english": "covenant",
        }
        self.assertTrue(
            is_choice_visible_in_feedback("kitten", "session", **options)
        )


if __name__ == "__main__":
    unittest.main()
