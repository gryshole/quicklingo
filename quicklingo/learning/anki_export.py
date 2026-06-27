from __future__ import annotations

import csv
import io
import zlib
from pathlib import Path

import genanki

from quicklingo.db.learning import LearningCard, LearningDeck

_MODEL_ID = 1607392320
_DECK_ID_BASE = 2059400110

_QUICKLINGO_MODEL = genanki.Model(
    _MODEL_ID,
    "QuickLingo Basic",
    fields=[
        {"name": "Front"},
        {"name": "Back"},
        {"name": "Context"},
    ],
    templates=[
        {
            "name": "Card 1",
            "qfmt": "{{Front}}",
            "afmt": "{{FrontSide}}<hr id=answer>{{Back}}{{#Context}}<hr><div class=context>{{Context}}</div>{{/Context}}",
        },
    ],
    css=".context { color: #555; font-size: 0.9em; }",
)


def _deck_tags(deck: LearningDeck) -> list[str]:
    tags = ["QuickLingo", deck.direction.replace("-", "_")]
    if deck.tag:
        tags.append(deck.tag.replace(" ", "_"))
    return tags


def _deck_id(deck: LearningDeck) -> int:
    key = f"{deck.id}:{deck.tag}:{deck.direction}"
    return (_DECK_ID_BASE + zlib.adler32(key.encode())) & 0x7FFFFFFF


def _deck_name(deck: LearningDeck) -> str:
    parts = [deck.name or "QuickLingo"]
    if deck.tag:
        parts.append(deck.tag)
    parts.append(deck.direction)
    return " — ".join(parts)


def export_anki_csv(cards: list[LearningCard], deck: LearningDeck) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["Front", "Back", "Tags", "Context"])
    tags = " ".join(_deck_tags(deck))
    for card in cards:
        writer.writerow([card.front, card.back, tags, card.context])
    return buffer.getvalue()


def export_anki_apkg(cards: list[LearningCard], deck: LearningDeck, path: Path) -> None:
    anki_deck = genanki.Deck(_deck_id(deck), _deck_name(deck))
    tags = _deck_tags(deck)
    for card in cards:
        note = genanki.Note(
            model=_QUICKLINGO_MODEL,
            fields=[card.front, card.back, card.context or ""],
            tags=tags,
        )
        anki_deck.add_note(note)
    genanki.Package(anki_deck).write_to_file(str(path))
