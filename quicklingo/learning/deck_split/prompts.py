from __future__ import annotations

import json

from quicklingo.config.loader import get_direction, get_direction_label, resolve_learning_direction
from quicklingo.db.learning_models import LearningCard, LearningDeck
from quicklingo.features import get_feature

_LANG_DISPLAY = {
    "en": "English",
    "uk": "Ukrainian",
    "ua": "Ukrainian",
}


def _lang_display(code: str) -> str:
    normalized = code.strip().lower()
    if normalized in ("uk", "ua"):
        return "Ukrainian"
    if normalized == "en":
        return "English"
    return _LANG_DISPLAY.get(normalized, code)


def deck_split_direction_placeholders(direction_id: str) -> dict[str, str]:
    """Placeholders for system prompt based on deck learning direction."""
    direction = get_direction(direction_id)
    kind = resolve_learning_direction(direction_id)
    if direction is not None:
        front_lang = _lang_display(direction.source_lang)
        back_lang = _lang_display(direction.target_lang)
    elif kind == "ua-en":
        front_lang, back_lang = "Ukrainian", "English"
    else:
        front_lang, back_lang = "English", "Ukrainian"

    return {
        "cards_description": (
            f"Each card has {front_lang} on the learning side (front) and {back_lang} "
            "translation (back)."
        ),
        "fronts_match_note": (
            f'fronts must be character-exact copies of strings from the "front" field ({front_lang}) '
            "in the input — same spelling, casing, and punctuation; do not lemmatize, normalize, "
            "or rephrase"
        ),
        "direction_label": get_direction_label(direction_id),
    }


def get_builtin_deck_split_prompt() -> str:
    return """You are an analyst helping organize vocabulary learning decks into coherent thematic subgroups.

The user message contains a deck with cards ({cards_description}).

Your task:
1. Read all cards and decide whether the deck mixes distinct themes (e.g. domains, registers, topics, idioms vs single words).
2. Propose 0 to {max_options} split options. Each option moves a thematic subgroup into a NEW deck with its own tag.
3. Target subgroup size: about 20–35 words per option when possible.
4. HARD limit: each option must list at least {min_subgroup_cards} words in "fronts". If a theme has fewer, do NOT include that option — merge into another theme or omit it.
5. Each word (each "front" string) may appear in exactly ONE option's "fronts". Never assign the same front to multiple options.
6. Words NOT listed in any option's "fronts" stay in the source deck.
7. If the deck is already cohesive, return "options": [] and explain in "summary".
8. If user_note is non-empty, use it as context (topic, source material, learner goal).

Fronts copying rules (critical):
- fronts ({fronts_match_note}).
- Wrong casing, lemmatized forms, or paraphrases will fail matching — copy-paste from input only.

Tag rules:
- lowercase, latin letters, digits, hyphens only
- logically related to source_tag (e.g. source "work" → "work-legal", "work-meetings", not bare "legal")
- must differ from source_tag
- never use "__quiz-distractors"

Each option needs: id (short letter), title (human label), tag, deck_name (display name), rationale (1–2 sentences), fronts (list of front strings obeying the rules above).

Respond with JSON only, no markdown:
{
  "summary": "short analysis",
  "options": [
    {
      "id": "a",
      "title": "...",
      "tag": "source-theme",
      "deck_name": "...",
      "rationale": "...",
      "fronts": ["exact front", ...]
    }
  ]
}"""


def _apply_deck_split_placeholders(template: str, *, direction_id: str) -> str:
    feature = get_feature("learning.deck_split")
    max_options = int(feature.get("max_options", 4))
    min_subgroup = int(feature.get("min_subgroup_cards", 8))
    values = {
        "max_options": str(max_options),
        "min_subgroup_cards": str(min_subgroup),
        **deck_split_direction_placeholders(direction_id),
    }
    result = template
    for key, value in values.items():
        result = result.replace(f"{{{key}}}", value)
    return result


def get_deck_split_system_prompt(direction_id: str = "en-ua") -> str:
    feature = get_feature("learning.deck_split")
    custom = (feature.get("split_prompt_template") or "").strip()
    template = custom if custom else get_builtin_deck_split_prompt()
    return _apply_deck_split_placeholders(template, direction_id=direction_id)


def _card_payload(card: LearningCard) -> dict[str, str]:
    return {
        "front": card.front.strip(),
        "back": card.back.strip(),
    }


def build_deck_split_user_message(
    deck: LearningDeck,
    cards: list[LearningCard],
    *,
    user_note: str = "",
) -> str:
    payload = {
        "source_tag": deck.tag,
        "direction": deck.direction,
        "direction_label": get_direction_label(deck.direction),
        "deck_name": deck.name,
        "user_note": user_note.strip(),
        "cards": [_card_payload(card) for card in cards],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
