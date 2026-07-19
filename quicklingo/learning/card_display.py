from __future__ import annotations

import html
import json
import re

from quicklingo.config.loader import resolve_learning_direction

_EXAMPLE_COUNT = 3
_CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")


def display_term(term: str) -> str:
    return term.strip().lower()


def phonetic_display_text(phonetic: str) -> str:
    inner = phonetic.strip().strip("/").strip()
    return phonetic.strip() if inner else ""


def highlight_term_in_context(context: str, front: str) -> str:
    """Return HTML with the first case-insensitive match of front bolded."""
    context = context.strip()
    front = front.strip()
    if not context or not front:
        return html.escape(context)

    pattern = re.compile(re.escape(front), re.IGNORECASE | re.UNICODE)
    match = pattern.search(context)
    if not match:
        return html.escape(context)

    start, end = match.span()
    return (
        html.escape(context[:start])
        + f"<b>{html.escape(context[start:end])}</b>"
        + html.escape(context[end:])
    )


def is_english_example(text: str) -> bool:
    cleaned = text.strip()
    if not cleaned:
        return False
    latin = sum(1 for char in cleaned if char.isascii() and char.isalpha())
    cyrillic = len(_CYRILLIC_RE.findall(cleaned))
    if cyrillic >= 2 or cyrillic > latin:
        return False
    return bool(re.findall(r"[\w']+", cleaned, flags=re.UNICODE))


def parse_context(raw: str, *, direction: str = "ua-en") -> list[str]:
    cleaned = (raw or "").strip()
    if not cleaned:
        return []
    if cleaned.startswith("["):
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, list):
            return [str(item).strip() for item in data if str(item).strip()]
    if (
        resolve_learning_direction(direction) == "ua-en"
        and len(_CYRILLIC_RE.findall(cleaned)) >= 2
    ):
        return []
    return [cleaned]


def serialize_context(examples: list[str] | str, *, direction: str = "ua-en") -> str:
    del direction  # both kinds store JSON arrays
    if isinstance(examples, str):
        parsed = parse_context(examples, direction="ua-en")
        items = parsed if parsed else [examples.strip()] if examples.strip() else []
    else:
        items = [item.strip() for item in examples if item.strip()]
    return json.dumps(items[:_EXAMPLE_COUNT], ensure_ascii=False)


def format_example_pills_html(examples: list[str], highlight_term: str) -> str:
    if not examples:
        return ""
    pills: list[str] = []
    for index, sentence in enumerate(examples):
        margin = "margin-bottom:8px;" if index < len(examples) - 1 else ""
        style = f"background:#f0f0f0;border-radius:8px;padding:8px 12px;text-align:left;{margin}"
        pills.append(
            f'<div style="{style}">'
            f"{highlight_term_in_context(sentence, highlight_term)}"
            "</div>"
        )
    return (
        '<div style="margin:0 auto;width:fit-content;text-align:left;">'
        + "".join(pills)
        + "</div>"
    )


def highlight_term_styled(
    text: str,
    term: str,
    *,
    style: str = "font-weight:600;color:#1565c0;",
) -> str:
    """Return HTML with the first case-insensitive match styled."""
    text = text.strip()
    term = term.strip()
    if not text or not term:
        return html.escape(text)

    pattern = re.compile(re.escape(term), re.IGNORECASE | re.UNICODE)
    match = pattern.search(text)
    if not match:
        return html.escape(text)

    start, end = match.span()
    return (
        html.escape(text[:start])
        + f'<span style="{style}">{html.escape(text[start:end])}</span>'
        + html.escape(text[end:])
    )
