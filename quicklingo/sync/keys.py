from __future__ import annotations


def deck_entity_key(tag: str, direction: str) -> str:
    return f"deck:{tag}|{direction}"


def card_entity_key(sync_id: str) -> str:
    return f"card:{sync_id}"


def translation_entity_key(content_hash: str, direction: str, profile_id: str) -> str:
    return f"translation:{content_hash}|{direction}|{profile_id}"


def quiz_entity_key(card_sync_id: str, question_type: str) -> str:
    return f"quiz:{card_sync_id}|{question_type}"
