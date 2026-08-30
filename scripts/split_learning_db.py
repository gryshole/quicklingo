"""One-off splitter — run from repo root: python scripts/split_learning_db.py"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "quicklingo/db/learning.py"
text = SRC.read_text(encoding="utf-8")
lines = text.splitlines(keepends=True)

db_dir = ROOT / "quicklingo/db"


def slice_lines(start: int, end: int) -> str:
    return "".join(lines[start - 1:end])


MODELS = """from __future__ import annotations

import json
import sqlite3

""" + slice_lines(25, 104) + slice_lines(917, 951) + slice_lines(1057, 1078) + slice_lines(1282, 1320)

SCHEMA = """from __future__ import annotations

import sqlite3

from quicklingo.db.connection import connection
from quicklingo.db.tombstones import clear_deck_tombstone

""" + slice_lines(107, 334)

DECKS = """from __future__ import annotations

from quicklingo.db.connection import connection
from quicklingo.db.learning_models import LearningDeck, _row_to_deck
from quicklingo.db.tombstones import clear_deck_tombstone, record_deck_delete

""" + slice_lines(335, 457)

CARDS = """from __future__ import annotations

import sqlite3
from datetime import date

from quicklingo import settings as app_settings
from quicklingo.db.connection import connection, fetch_all, in_placeholders, scalar_int
from quicklingo.db.learning_models import LearningCard, _CARD_SELECT, _row_to_card
from quicklingo.db.sync_schema import new_card_sync_id
from quicklingo.db.tombstones import record_card_delete
from quicklingo.learning.text_normalize import normalize_source

""" + slice_lines(458, 865)

QUIZ = """from __future__ import annotations

from quicklingo import settings as app_settings
from quicklingo.db.connection import connection, fetch_all, in_placeholders, scalar_int
from quicklingo.db.learning_models import (
    QuizCoverageStats,
    QuizQuestionRecord,
    QuizQuestionRow,
    QUIZ_QUESTION_TYPES,
    _parse_choices_pool,
    _row_to_quiz_question,
    _row_to_quiz_question_row,
    _serialize_choices_pool,
)

""" + slice_lines(866, 916) + slice_lines(952, 1056) + slice_lines(1079, 1164)

REVIEWS = """from __future__ import annotations

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
from quicklingo.learning.review_queue import english_side_text

""" + slice_lines(1165, 1281) + slice_lines(1321, 1345)

(db_dir / "learning_models.py").write_text(MODELS, encoding="utf-8")
(db_dir / "learning_schema.py").write_text(SCHEMA, encoding="utf-8")
(db_dir / "learning_decks.py").write_text(DECKS, encoding="utf-8")
(db_dir / "learning_cards.py").write_text(CARDS, encoding="utf-8")
(db_dir / "learning_quiz.py").write_text(QUIZ, encoding="utf-8")
(db_dir / "learning_reviews.py").write_text(REVIEWS, encoding="utf-8")

FACADE = '''"""Learning DB facade — re-exports split modules for stable imports."""

from quicklingo.db.learning_cards import *  # noqa: F403
from quicklingo.db.learning_decks import *  # noqa: F403
from quicklingo.db.learning_due import *  # noqa: F403
from quicklingo.db.learning_models import *  # noqa: F403
from quicklingo.db.learning_quiz import *  # noqa: F403
from quicklingo.db.learning_reviews import *  # noqa: F403
from quicklingo.db.learning_schema import init_learning_tables
'''
(db_dir / "learning.py").write_text(FACADE, encoding="utf-8")
print("Split complete")
