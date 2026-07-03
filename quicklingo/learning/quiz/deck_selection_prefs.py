from __future__ import annotations

from quicklingo.features import get_feature, save_features


def load_play_deck_ids() -> frozenset[int] | None:
    """Return None for all-decks mode, or explicit frozenset for custom selection."""
    feature = get_feature("learning.quiz")
    mode = str(feature.get("last_deck_selection_mode", "all")).strip().lower()
    if mode == "all":
        return None
    raw = feature.get("last_deck_ids", [])
    if not isinstance(raw, list):
        return frozenset()
    ids = frozenset(int(item) for item in raw if str(item).strip().isdigit())
    return ids


def save_play_deck_ids(deck_ids: frozenset[int] | None) -> None:
    current = load_play_deck_ids()
    if deck_ids is None:
        if current is None:
            return
        save_features(
            {
                "learning.quiz": {
                    "last_deck_selection_mode": "all",
                    "last_deck_ids": [],
                }
            }
        )
        return
    if current == deck_ids:
        return
    save_features(
        {
            "learning.quiz": {
                "last_deck_selection_mode": "custom",
                "last_deck_ids": sorted(deck_ids),
            }
        }
    )


def load_generation_deck_id() -> int | None:
    feature = get_feature("learning.quiz")
    raw = feature.get("last_generation_deck_id")
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def save_generation_deck_id(deck_id: int | None) -> None:
    if load_generation_deck_id() == deck_id:
        return
    save_features({"learning.quiz": {"last_generation_deck_id": deck_id if deck_id is not None else ""}})
