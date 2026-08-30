from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass

QUIZ_QUESTION_TYPES = ("fill_blank", "definition_match", "translation_recall")


@dataclass
class LearningDeck:
    id: int
    name: str
    tag: str
    direction: str
    created_at: str
    analysis_summary: str = ""
    source: str = "corpus"


@dataclass
class QuizQuestionRecord:
    id: int
    card_id: int
    question_type: str
    prompt_text: str
    example_sentence: str
    choices_pool: list[str]
    correct_english: str
    status: str
    model_id: str
    prompt_version: str
    created_at: str
    updated_at: str


@dataclass
class QuizQuestionRow(QuizQuestionRecord):
    card_front: str = ""
    card_back: str = ""
    deck_id: int = 0
    deck_name: str = ""


@dataclass(frozen=True)
class QuizCoverageStats:
    eligible: int
    ready: int
    missing_any: int
    missing_by_type: dict[str, int]


@dataclass
class LearningCard:
    id: int
    deck_id: int
    front: str
    back: str
    context: str = ""
    hint: str = ""
    notes: str = ""
    image_path: str = ""
    image_prompt: str = ""
    phonetic: str = ""
    audio_path: str = ""
    card_type: str = "basic"
    priority: int = 3
    source_record_id: int | None = None
    ease: float = 2.5
    interval_days: int = 0
    next_review_date: str = ""
    last_reviewed: str = ""
    fsrs_state: str = ""
    quiz_distractors: str = ""


_CARD_COLUMNS = (
    "id, deck_id, front, back, context, hint, notes, image_path, image_prompt, "
    "phonetic, audio_path, card_type, priority, source_record_id, ease, "
    "interval_days, next_review_date, last_reviewed, fsrs_state, quiz_distractors"
)

_CARD_SELECT = f"""
    SELECT {_CARD_COLUMNS}
    FROM learning_cards
"""


def _parse_choices_pool(raw: str) -> list[str]:
    text = (raw or "").strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [" ".join(str(item).split()).strip() for item in parsed if str(item).strip()]


def _serialize_choices_pool(items: list[str]) -> str:
    cleaned = [" ".join(str(item).split()).strip() for item in items if str(item).strip()]
    return json.dumps(cleaned, ensure_ascii=False)


def _row_to_quiz_question(row: sqlite3.Row) -> QuizQuestionRecord:
    return QuizQuestionRecord(
        id=int(row["id"]),
        card_id=int(row["card_id"]),
        question_type=str(row["question_type"]),
        prompt_text=str(row["prompt_text"] or ""),
        example_sentence=str(row["example_sentence"] or ""),
        choices_pool=_parse_choices_pool(str(row["choices_pool"] or "")),
        correct_english=str(row["correct_english"] or ""),
        status=str(row["status"] or "active"),
        model_id=str(row["model_id"] or ""),
        prompt_version=str(row["prompt_version"] or "v1"),
        created_at=str(row["created_at"] or ""),
        updated_at=str(row["updated_at"] or ""),
    )


def _row_to_quiz_question_row(row: sqlite3.Row) -> QuizQuestionRow:
    base = _row_to_quiz_question(row)
    return QuizQuestionRow(
        id=base.id,
        card_id=base.card_id,
        question_type=base.question_type,
        prompt_text=base.prompt_text,
        example_sentence=base.example_sentence,
        choices_pool=base.choices_pool,
        correct_english=base.correct_english,
        status=base.status,
        model_id=base.model_id,
        prompt_version=base.prompt_version,
        created_at=base.created_at,
        updated_at=base.updated_at,
        card_front=str(row["card_front"] or ""),
        card_back=str(row["card_back"] or ""),
        deck_id=int(row["deck_id"]),
        deck_name=str(row["deck_name"] or ""),
    )


def _row_to_deck(row: sqlite3.Row) -> LearningDeck:
    keys = row.keys()
    return LearningDeck(
        id=row["id"],
        name=row["name"],
        tag=row["tag"],
        direction=row["direction"],
        created_at=row["created_at"],
        analysis_summary=row["analysis_summary"] or "",
        source=row["source"] if "source" in keys else "corpus",
    )


def _row_to_card(row: sqlite3.Row) -> LearningCard:
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
        quiz_distractors=row["quiz_distractors"] if "quiz_distractors" in keys else "",
    )
