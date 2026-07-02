from __future__ import annotations

from quicklingo.config.loader import get_direction_label, resolve_learning_direction
from quicklingo.learning.ai_deck.models import AiDeckParams
from quicklingo.learning.ai_deck.topics import resolve_lexicon_type_text, resolve_topic_text


def build_word_list_prompt(params: AiDeckParams) -> str:
    kind = resolve_learning_direction(params.direction)
    topic = resolve_topic_text(params)
    lexicon = resolve_lexicon_type_text(params)
    direction_label = get_direction_label(params.direction)
    language_note = (
        "Return English lemmas/phrases suitable as the English learning target (back side)."
        if kind == "ua-en"
        else "Return English lemmas/phrases suitable as the English source term (front side)."
    )
    lexicon_line = (
        f"Focus on {lexicon} vocabulary."
        if params.lexicon_type != "any"
        else "Use varied useful vocabulary for the topic."
    )
    return (
        f"Generate exactly {params.word_count} unique vocabulary items for a flashcard deck.\n"
        f"CEFR level: {params.level}.\n"
        f"Topic: {topic}.\n"
        f"Direction: {direction_label}.\n"
        f"{language_note}\n"
        f"{lexicon_line}\n"
        "Rules:\n"
        "- No duplicates, no numbering, no translations.\n"
        "- One item per string; keep items concise (1-4 words for phrases).\n"
        "- Output ONLY a JSON array of strings, e.g. [\"word1\", \"word2\"]."
    )
