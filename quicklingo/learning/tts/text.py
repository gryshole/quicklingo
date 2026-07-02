from __future__ import annotations

import re

_BLANK_MARKERS_RE = re.compile(r"_+")


def prepare_text_for_tts(text: str) -> str:
    """Replace fill-in-the-blank underscore runs with the word 'blank' for natural speech."""
    cleaned = text.strip()
    if not cleaned:
        return cleaned
    spoken = _BLANK_MARKERS_RE.sub(" blank ", cleaned)
    return re.sub(r"\s+", " ", spoken).strip()
