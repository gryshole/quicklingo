from __future__ import annotations


def collapse_whitespace(text: str) -> str:
    """Collapse runs of whitespace into single spaces and trim the ends."""
    return " ".join(text.split())


def normalize_source(text: str) -> str:
    return collapse_whitespace(text).lower()


def normalize_for_hash(text: str) -> str:
    return collapse_whitespace(text)
