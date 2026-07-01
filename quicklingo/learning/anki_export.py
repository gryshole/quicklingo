from __future__ import annotations

import csv
import io
import zlib
from pathlib import Path

import genanki

from quicklingo.db.learning import LearningCard, LearningDeck
from quicklingo.learning.card_display import parse_context
from quicklingo.learning.image_resolver import resolve_image_path
from quicklingo.learning.pronunciation import resolve_audio_path

_MODEL_ID = 1607392320
_DECK_ID_BASE = 2059400110

_QUICKLINGO_MODEL = genanki.Model(
    _MODEL_ID,
    "QuickLingo Basic",
    fields=[
        {"name": "Front"},
        {"name": "Back"},
        {"name": "Context"},
        {"name": "Extra"},
    ],
    templates=[
        {
            "name": "Card 1",
            "qfmt": "{{Front}}",
            "afmt": (
                "{{FrontSide}}<hr id=answer>{{Back}}"
                "{{#Context}}<hr><div class=context>{{Context}}</div>{{/Context}}"
                "{{#Extra}}<hr><div class=extra>{{Extra}}</div>{{/Extra}}"
            ),
        },
    ],
    css=".context,.extra { color: #555; font-size: 0.9em; }",
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


def _front_html(card: LearningCard) -> str:
    parts = [card.front]
    if card.phonetic:
        parts.append(f'<div class="phonetic">{card.phonetic}</div>')
    image_path = resolve_image_path(card.image_path)
    if image_path:
        parts.append(f'<img src="{image_path.name}">')
    return "".join(parts)


def _extra_text(card: LearningCard) -> str:
    chunks = []
    if card.hint:
        chunks.append(f"Hint: {card.hint}")
    if card.notes:
        chunks.append(card.notes)
    return "\n".join(chunks)


def _format_context_for_export(
    card: LearningCard, deck: LearningDeck, *, html: bool = False
) -> str:
    examples = parse_context(card.context, direction=deck.direction)
    if not examples:
        return card.context or ""
    if html:
        return "<br>".join(examples)
    return "\n".join(f"• {example}" for example in examples)


def export_anki_csv(cards: list[LearningCard], deck: LearningDeck) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["Front", "Back", "Tags", "Context", "Extra"])
    tags = " ".join(_deck_tags(deck))
    for card in cards:
        writer.writerow(
            [card.front, card.back, tags, _format_context_for_export(card, deck), _extra_text(card)]
        )
    return buffer.getvalue()


def export_anki_apkg(cards: list[LearningCard], deck: LearningDeck, path: Path) -> None:
    anki_deck = genanki.Deck(_deck_id(deck), _deck_name(deck))
    tags = _deck_tags(deck)
    media_files: list[str] = []
    for card in cards:
        front = _front_html(card)
        back = card.back
        audio_path = resolve_audio_path(card)
        if audio_path:
            media_files.append(str(audio_path))
            back += f' [sound:{audio_path.name}]'
        note = genanki.Note(
            model=_QUICKLINGO_MODEL,
            fields=[front, back, _format_context_for_export(card, deck, html=True), _extra_text(card)],
            tags=tags,
        )
        anki_deck.add_note(note)
    package = genanki.Package(anki_deck)
    if media_files:
        package.media_files = media_files
    package.write_to_file(str(path))
