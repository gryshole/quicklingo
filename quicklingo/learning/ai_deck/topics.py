from __future__ import annotations

from quicklingo.i18n import tr
from quicklingo.learning.ai_deck.models import AiDeckParams

CUSTOM_TOPIC_KEY = "custom"

TOPIC_KEYS: tuple[str, ...] = (
    "it",
    "business_finance",
    "marketing",
    "medicine",
    "law",
    "jobs",
    "science",
    "everyday",
    "travel",
    "food",
    "shopping",
    "sport",
    "arts",
    "psychology",
    "politics",
    "environment",
    "gaming",
    "slang",
    "academic",
    CUSTOM_TOPIC_KEY,
)

LEXICON_TYPE_KEYS: tuple[str, ...] = (
    "any",
    "nouns",
    "verbs",
    "irregular_verbs",
    "phrasal_verbs",
    "adjectives",
    "adverbs",
    "idioms",
    "collocations",
    "phrases",
    "linking_words",
    "proverbs",
)


def topic_label(key: str) -> str:
    if key == CUSTOM_TOPIC_KEY:
        return tr("learning.ai_deck.topic.custom")
    return tr(f"learning.ai_deck.topic.{key}")


def lexicon_type_label(key: str) -> str:
    return tr(f"learning.ai_deck.lexicon.{key}")


def resolve_topic_text(params: AiDeckParams) -> str:
    if params.topic_key == CUSTOM_TOPIC_KEY:
        return params.custom_topic.strip()
    return topic_label(params.topic_key)


def resolve_lexicon_type_text(params: AiDeckParams) -> str:
    if params.lexicon_type == "any":
        return tr("learning.ai_deck.lexicon.any")
    return lexicon_type_label(params.lexicon_type)
