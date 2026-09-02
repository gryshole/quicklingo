from __future__ import annotations

import json
import re

from quicklingo.db.learning_cards import list_cards
from quicklingo.features import get_feature
from quicklingo.learning.corpus_analysis import _extract_json_object, _strip_code_fence
from quicklingo.learning.deck_split.models import DeckSplitAnalysisResult, DeckSplitOption
from quicklingo.learning.quiz.distractor_deck import QUIZ_DISTRACTOR_DECK_TAG
from quicklingo.learning.text_normalize import normalize_source

_TAG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _salvage_deck_split_truncated(text: str, error: json.JSONDecodeError) -> dict:
    """Best-effort recovery when the model returns truncated deck-split JSON."""
    cut = text[: error.pos].rstrip() if error.pos else text.rstrip()
    while cut and cut[-1] not in "}]":
        cut = cut[:-1]
    cut = cut.rstrip().rstrip(",")
    if not cut or cut.endswith("{") or cut.endswith("["):
        raise error
    if '"options"' in cut:
        if not cut.rstrip().endswith("]"):
            cut += "]"
    while cut.count("{") > cut.count("}"):
        cut += "}"
    return json.loads(cut)


def _load_deck_split_json(raw: str) -> dict:
    text = (raw or "").strip()
    if not text:
        raise ValueError("Model returned an empty response. Try again or choose another model.")

    payload = _extract_json_object(_strip_code_fence(text))
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        try:
            data = _salvage_deck_split_truncated(payload, exc)
        except json.JSONDecodeError:
            raise ValueError(
                "Could not parse AI response as deck-split JSON. Try again or choose another model."
            ) from exc
    if not isinstance(data, dict):
        raise ValueError("AI response must be a JSON object with summary and options.")
    return data


def match_fronts_to_card_ids(deck_id: int, fronts: list[str]) -> tuple[list[int], list[str]]:
    """Map AI front strings to card ids in deck. Returns (matched_ids, unmatched_fronts)."""
    cards = list_cards(deck_id)
    index: dict[str, int] = {}
    for card in cards:
        key = normalize_source(card.front)
        if key and key not in index:
            index[key] = card.id
    matched: list[int] = []
    unmatched: list[str] = []
    seen_ids: set[int] = set()
    for raw in fronts:
        front = str(raw).strip()
        if not front:
            continue
        key = normalize_source(front)
        card_id = index.get(key)
        if card_id is None:
            unmatched.append(front)
            continue
        if card_id not in seen_ids:
            seen_ids.add(card_id)
            matched.append(card_id)
    return matched, unmatched


def _normalize_tag(tag: str, source_tag: str) -> str:
    cleaned = (tag or "").strip().lower()
    cleaned = re.sub(r"[^a-z0-9-]", "-", cleaned)
    cleaned = re.sub(r"-+", "-", cleaned).strip("-")
    if not cleaned or cleaned == QUIZ_DISTRACTOR_DECK_TAG:
        return ""
    if cleaned == source_tag.strip().lower():
        return ""
    if not _TAG_RE.match(cleaned):
        return ""
    return cleaned


def parse_deck_split_response(
    raw: str,
    *,
    deck_id: int,
    source_tag: str,
    direction: str,
) -> DeckSplitAnalysisResult:
    data = _load_deck_split_json(raw)
    summary = str(data.get("summary", "")).strip()
    options_raw = data.get("options", [])
    if not isinstance(options_raw, list):
        options_raw = []

    feature = get_feature("learning.deck_split")
    min_subgroup = int(feature.get("min_subgroup_cards", 8))
    max_options = int(feature.get("max_options", 4))

    assigned_fronts: set[str] = set()
    options: list[DeckSplitOption] = []

    for index, item in enumerate(options_raw):
        if index >= max_options:
            break
        if not isinstance(item, dict):
            continue
        tag = _normalize_tag(str(item.get("tag", "")), source_tag)
        if not tag:
            continue
        fronts_raw = item.get("fronts", [])
        if not isinstance(fronts_raw, list):
            continue
        fronts: list[str] = []
        for f in fronts_raw:
            front = str(f).strip()
            if not front:
                continue
            norm = normalize_source(front)
            if norm in assigned_fronts:
                continue
            assigned_fronts.add(norm)
            fronts.append(front)
        if len(fronts) < min_subgroup:
            continue
        card_ids, _unmatched = match_fronts_to_card_ids(deck_id, fronts)
        if len(card_ids) < min_subgroup:
            continue
        option_id = str(item.get("id", "")).strip() or chr(ord("a") + index)
        title = str(item.get("title", "")).strip() or tag
        deck_name = str(item.get("deck_name", "")).strip() or tag
        rationale = str(item.get("rationale", "")).strip()
        options.append(
            DeckSplitOption(
                id=option_id,
                title=title,
                tag=tag,
                deck_name=deck_name,
                rationale=rationale,
                fronts=fronts,
                card_ids=card_ids,
            )
        )

    return DeckSplitAnalysisResult(
        summary=summary,
        options=options,
        source_deck_id=deck_id,
        source_tag=source_tag,
        direction=direction,
    )
