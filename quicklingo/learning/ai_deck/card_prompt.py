from __future__ import annotations

from quicklingo.learning.ai_deck.models import AiDeckParams
from quicklingo.learning.ai_deck.topics import resolve_lexicon_type_text, resolve_topic_text
from quicklingo.learning.card_prompt import build_card_analysis_prompt
from quicklingo.learning.corpus_analysis import CorpusCandidate

_AI_WORD_MODE_NOTE = """
AI WORD LIST MODE:
- Each item is a bare vocabulary target without a ready-made translation pair.
- Invent the missing side (front/back) and all required card fields.
- Keep vocabulary at the requested CEFR level and topic; do not reuse the same root across cards.
"""


def build_ai_word_card_prompt(
    candidates: list[CorpusCandidate],
    params: AiDeckParams,
) -> str:
    base = build_card_analysis_prompt(
        candidates,
        tag=params.normalized_tag(),
        direction=params.direction,
    )
    topic = resolve_topic_text(params)
    lexicon = resolve_lexicon_type_text(params)
    header = (
        f"{_AI_WORD_MODE_NOTE.strip()}\n"
        f"Requested level: {params.level}.\n"
        f"Topic: {topic}.\n"
        f"Lexicon focus: {lexicon}.\n\n"
    )
    return header + base


def format_deck_summary(params: AiDeckParams, *, word_count: int) -> str:
    topic = resolve_topic_text(params)
    lexicon = resolve_lexicon_type_text(params)
    return (
        f"AI deck: tag={params.normalized_tag()}, level={params.level}, "
        f"topic={topic}, lexicon={lexicon}, words={word_count}, "
        f"direction={params.direction}."
    )
