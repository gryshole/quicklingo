from __future__ import annotations


def normalize_source(text: str) -> str:
    return " ".join(text.split()).lower()


def normalize_for_hash(text: str) -> str:
    return " ".join(text.split())
