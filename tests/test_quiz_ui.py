from __future__ import annotations

import unittest

from quicklingo.learning.quiz.quiz_feedback_content import format_wrong_hint_html


class QuizUiTests(unittest.TestCase):
    def test_format_wrong_hint_html_bolds_quoted_inner_text(self) -> None:
        html_text = format_wrong_hint_html("Твій вибір «grape» - виноград")
        self.assertIn("font-weight:700", html_text)
        self.assertIn(">grape</span>", html_text)
        self.assertIn("«</span>", html_text)
        self.assertIn("виноград", html_text)
        self.assertNotIn(">«grape»</span>", html_text)


if __name__ == "__main__":
    unittest.main()
