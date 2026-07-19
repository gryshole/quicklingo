from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import quote

import httpx

from quicklingo.db import learning
from quicklingo.db.learning import LearningCard
from quicklingo.learning.audio_storage import (
    allocate_pronunciation_path,
    relative_path,
    resolve_stored_pronunciation_path,
)
from quicklingo.learning.card_display import phonetic_display_text
from quicklingo.learning.review_queue import english_side_text

_DICTIONARY_API = "https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
_TTS_VOICE = "en-US-AriaNeural"
_WORD_RE = re.compile(r"^[\w'-]+$", re.UNICODE)


def resolve_audio_path(card: LearningCard) -> Path | None:
    path = resolve_stored_pronunciation_path(card.audio_path, card_id=card.id)
    if path is None:
        return None
    expected_rel = relative_path(path)
    if card.audio_path != expected_rel:
        learning.update_card(card.id, audio_path=expected_rel)
    return path


def is_single_english_word(text: str) -> bool:
    cleaned = text.strip()
    return bool(cleaned) and " " not in cleaned and bool(_WORD_RE.match(cleaned))


def fetch_pronunciation(
    card: LearningCard,
    *,
    direction: str,
) -> tuple[str, str] | None:
    """Fetch phonetic + relative audio_path. Returns None on failure."""
    english = english_side_text(card, direction)
    if not english.strip():
        return None
    if card.audio_path and resolve_audio_path(card):
        return card.phonetic, card.audio_path
    if is_single_english_word(english):
        result = _fetch_dictionary_audio(english.lower())
        if result:
            phonetic, data = result
            rel_path = _save_audio_bytes(card.id, data)
            return phonetic, rel_path
    phonetic = _resolve_phonetic_text(english) or card.phonetic
    rel_path = _synthesize_tts(card.id, english)
    if rel_path:
        return phonetic, rel_path
    return None


def _resolve_phonetic_text(english: str) -> str:
    cleaned = english.strip().lower()
    if not cleaned:
        return ""
    for query in (cleaned, cleaned.replace(" ", "-")):
        phonetic = _fetch_phonetic_from_api(query)
        if phonetic:
            return phonetic
    words = cleaned.split()
    if words:
        return _fetch_phonetic_from_api(words[0])
    return ""


def _fetch_phonetic_from_api(word: str) -> str:
    url = _DICTIONARY_API.format(word=quote(word))
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(url)
            if response.status_code != 200:
                return ""
            entries = response.json()
    except (httpx.HTTPError, ValueError):
        return ""
    if not entries:
        return ""
    phonetics = entries[0].get("phonetics", [])
    for item in phonetics:
        text = phonetic_display_text(str(item.get("text", "")).strip())
        if text:
            return text
    return ""


def ensure_card_pronunciation(card_id: int, *, direction: str) -> LearningCard | None:
    card = learning.get_card(card_id)
    if card is None:
        return None
    if card.audio_path and resolve_audio_path(card):
        return card
    result = fetch_pronunciation(card, direction=direction)
    if not result:
        return card
    phonetic, rel_path = result
    learning.update_card(
        card_id,
        phonetic=phonetic_display_text(phonetic or card.phonetic),
        audio_path=rel_path,
    )
    return learning.get_card(card_id)


def _fetch_dictionary_audio(word: str) -> tuple[str, bytes] | None:
    url = _DICTIONARY_API.format(word=quote(word))
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(url)
            if response.status_code != 200:
                return None
            entries = response.json()
    except (httpx.HTTPError, ValueError):
        return None
    if not entries:
        return None
    phonetics = entries[0].get("phonetics", [])
    phonetic_text = ""
    audio_url = ""
    for item in phonetics:
        text = str(item.get("text", "")).strip()
        audio = str(item.get("audio", "")).strip()
        if audio.startswith("//"):
            audio = "https:" + audio
        if audio and ("-us" in audio.lower() or "us.mp3" in audio.lower()):
            phonetic_text = phonetic_display_text(text or phonetic_text)
            audio_url = audio
            break
    if not audio_url:
        for item in phonetics:
            audio = str(item.get("audio", "")).strip()
            if audio.startswith("//"):
                audio = "https:" + audio
            if audio:
                phonetic_text = phonetic_display_text(
                    str(item.get("text", "")).strip() or phonetic_text
                )
                audio_url = audio
                break
    if not audio_url:
        return None
    try:
        with httpx.Client(timeout=20.0) as client:
            audio_response = client.get(audio_url)
            audio_response.raise_for_status()
            return phonetic_text, audio_response.content
    except httpx.HTTPError:
        return None


def _synthesize_tts(card_id: int, text: str) -> str | None:
    try:
        import asyncio

        import edge_tts  # noqa: F401  # availability probe
    except ImportError:
        return None

    output = allocate_pronunciation_path(card_id)
    try:
        asyncio.run(_edge_tts_save(text, output))
    except Exception:
        return None
    if not output.is_file():
        return None
    return relative_path(output)


async def _edge_tts_save(text: str, output: Path) -> None:
    import edge_tts

    communicate = edge_tts.Communicate(text, _TTS_VOICE)
    await communicate.save(str(output))


def _save_audio_bytes(card_id: int, data: bytes) -> str:
    output = allocate_pronunciation_path(card_id)
    output.write_bytes(data)
    return relative_path(output)
