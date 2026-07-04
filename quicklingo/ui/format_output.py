import html
import re

_CYRILLIC = re.compile(r"[а-яА-ЯіІїЇєЄґҐ]")
_UA_EN_SPLIT = re.compile(r"\n(?=──────────────────\n|You probably meant: )")
_SEPARATOR_LINE = re.compile(r"^_+\s*$")
_CONTEXT_LINE = re.compile(r"^(.+?) — (.+)$")
_GLOSS_DASH_PREFIX = re.compile(r"^[\-—–]\s*(.+)$")
_NUMBERED_LINE = re.compile(r"^(\[\d+\]\s*.+)$")
_NUMBERED_HEADER = re.compile(r"^\[(\d+)\]\s*(.+)$")
_UA_EN_META_PREFIXES = ("Example:", "You probably meant:", "Also, if you meant:")


def _is_ua_en_continuation_line(stripped: str) -> bool:
    """Ukrainian gloss continued on the next line after an API soft-wrap."""
    if not stripped or stripped == "──────────────────":
        return False
    if not _CYRILLIC.search(stripped):
        return False
    if _CONTEXT_LINE.match(stripped):
        return False
    if stripped.startswith(_UA_EN_META_PREFIXES):
        return False
    if stripped.startswith("—"):
        return False
    if _NUMBERED_LINE.match(stripped):
        return False
    return True


def _can_merge_ua_en_previous_line(prev_stripped: str) -> bool:
    if not prev_stripped:
        return False
    if _CONTEXT_LINE.match(prev_stripped):
        return True
    if prev_stripped.startswith("—") and _CYRILLIC.search(prev_stripped):
        return True
    return _is_ua_en_continuation_line(prev_stripped)


def _is_english_gloss_header(stripped: str) -> bool:
    if not stripped or _CYRILLIC.search(stripped):
        return False
    if _CONTEXT_LINE.match(stripped):
        return False
    if stripped.startswith(_UA_EN_META_PREFIXES):
        return False
    if _NUMBERED_LINE.match(stripped):
        return False
    if stripped.startswith(("—", "-")):
        return False
    return True


def _normalize_gloss_line(stripped: str) -> str:
    if _CONTEXT_LINE.match(stripped):
        return stripped
    match = re.match(r"^(.+?) [\-\–] (.+)$", stripped)
    if match and not _CYRILLIC.search(match.group(1)) and _CYRILLIC.search(match.group(2)):
        return f"{match.group(1).strip()} — {match.group(2).strip()}"
    return stripped


def _strip_leading_dash(text: str) -> str:
    match = _GLOSS_DASH_PREFIX.match(text.strip())
    if match:
        return match.group(1).strip()
    return text.strip()


def _next_nonempty_line(lines: list[str], start: int) -> tuple[int, str] | None:
    index = start
    while index < len(lines):
        stripped = lines[index].strip()
        if stripped:
            return index, stripped
        index += 1
    return None


def merge_ua_en_wrapped_lines(block: str) -> str:
    """Join split headers and soft-wrapped gloss lines into single entries."""
    merged: list[str] = []
    lines = block.split("\n")
    index = 0
    while index < len(lines):
        stripped = _normalize_gloss_line(lines[index].strip())
        if not stripped:
            if merged and merged[-1] != "":
                merged.append("")
            index += 1
            continue

        if _is_english_gloss_header(stripped):
            nxt = _next_nonempty_line(lines, index + 1)
            if nxt is not None:
                next_index, next_stripped = nxt
                next_stripped = _normalize_gloss_line(next_stripped)
                dash_body = (
                    _strip_leading_dash(next_stripped)
                    if _GLOSS_DASH_PREFIX.match(next_stripped)
                    else ""
                )
                if dash_body and _CYRILLIC.search(dash_body):
                    merged.append(f"{stripped} — {dash_body}")
                    index = next_index + 1
                    continue

        if (
            merged
            and _is_ua_en_continuation_line(stripped)
            and _can_merge_ua_en_previous_line(merged[-1].strip())
        ):
            merged[-1] = f"{merged[-1].rstrip()} {stripped}"
            index += 1
            continue

        merged.append(stripped)
        index += 1
    return "\n".join(merged)


def format_plain_output(text: str) -> str:
    """Escape raw API text as simple HTML with line breaks."""
    return _wrap(html.escape(text).replace("\n", "<br>"))


def format_ua_en_output(text: str) -> str:
    """Turn ua-en API text into HTML cards for variants, context notes, and examples."""
    normalized = _normalize_ua_en_separators(text)
    chunks = _UA_EN_SPLIT.split(normalized)
    parts = [
        _format_ua_en_block(chunk.strip().removeprefix("──────────────────").strip())
        for chunk in chunks
        if chunk.strip()
    ]

    if not parts:
        return _wrap(html.escape(text).replace("\n", "<br>"))

    return _wrap("".join(parts))


def _normalize_separators(text: str) -> str:
    lines: list[str] = []
    for line in text.split("\n"):
        if _SEPARATOR_LINE.match(line.strip()):
            lines.append("──────────────────")
        else:
            lines.append(line)
    return "\n".join(lines).strip()


def _normalize_ua_en_separators(text: str) -> str:
    return _normalize_separators(text)


def _meaning_block(body: str, *, extra_style: str = "") -> str:
    return f'<div style="margin-bottom:20px;{extra_style}">{body}</div>'


_EMERALD_50 = "#ecfdf5"
_EMERALD_100 = "#d1fae5"
_SLATE_700 = "#334155"
_SKY_50 = "#eff6ff"
_SKY_200 = "#bfdbfe"
_SKY_700 = "#1d4ed8"


def _definition_pill(inner_html: str) -> str:
    """Qt QTextDocument ignores div padding/radius — use a table for the emerald chip."""
    return (
        '<table width="100%" cellpadding="6" cellspacing="0" '
        f'style="background-color:{_EMERALD_50}; border:1px solid {_EMERALD_100}; '
        'margin-top:6px; margin-bottom:6px;">'
        f'<tr><td style="margin:0;padding:0;">'
        f'<span style="color:{_SLATE_700}; line-height:{RESULT_LINE_HEIGHT};">'
        f"{inner_html}</span></td></tr></table>"
    )


def _example_pill(inner_html: str) -> str:
    """Example sentences — blue tint, left accent (distinct from green definition)."""
    return (
        '<table width="100%" cellpadding="6" cellspacing="0" '
        f'style="background-color:{_SKY_50}; border:1px solid {_SKY_200}; '
        'margin-top:4px; margin-bottom:2px;">'
        f'<tr><td style="margin:0;padding:0;border-left:3px solid #3b82f6;">'
        f'<span style="color:{_SLATE_700}; line-height:{RESULT_LINE_HEIGHT};">'
        f"{inner_html}</span></td></tr></table>"
    )


def _example_block(sentence: str) -> str:
    return _example_pill(
        f'<span style="color:{_SKY_700};font-weight:600">Example:</span> '
        f'<span style="color:#334155;font-style:italic">{html.escape(sentence)}</span>'
    )


def _meta_line(text: str, *, typo: bool) -> str:
    color = "#b45309" if typo else "#64748b"
    return (
        f'<div style="font-style:italic;color:{color};margin-bottom:8px">'
        f"{html.escape(text)}</div>"
    )


def _header_line(text: str) -> str:
    stripped = text.strip()
    numbered = _NUMBERED_HEADER.match(stripped)
    if numbered:
        index = html.escape(numbered.group(1))
        word = html.escape(numbered.group(2))
        return (
            '<div style="margin:0 0 8px 0;line-height:1.35">'
            f'<span style="color:#9ca3af;font-weight:400;margin-right:8px">[{index}]</span>'
            f'<span style="font-size:1.125em;font-weight:700;color:#1e293b">{word}</span>'
            "</div>"
        )
    return (
        f'<div style="font-size:1.125em;font-weight:700;color:#1e293b;'
        f'margin:0 0 8px 0">'
        f"{html.escape(stripped)}</div>"
    )


def _english_definition(text: str) -> str:
    return _definition_pill(html.escape(text))


def _ukrainian_translation(text: str) -> str:
    return (
        '<div style="margin-top:12px">'
        f'<span style="color:#1e40af;font-weight:600;font-size:1.05em">'
        f"{html.escape(text)}</span>"
        "</div>"
    )


def _ua_en_gloss_row(english: str, note: str) -> str:
    return (
        f'<p style="{_UA_EN_GLOSS_STYLE}">'
        f'<span style="font-weight:600;color:#1e40af">{english}</span>'
        f'<span style="color:#64748b"> — {note}</span>'
        "</p>"
    )


def _format_ua_en_block(block: str) -> str:
    parts: list[str] = []

    for line in merge_ua_en_wrapped_lines(block).split("\n"):
        stripped = _normalize_gloss_line(line.strip())
        if not stripped or stripped == "──────────────────":
            continue

        if stripped.startswith("You probably meant:"):
            parts.append(_meta_line(stripped, typo=True))
            continue

        if stripped.startswith("Example:"):
            parts.append(_example_block(stripped.removeprefix("Example:").strip()))
            continue

        if _NUMBERED_LINE.match(stripped):
            parts.append(_header_line(stripped))
            continue

        if _GLOSS_DASH_PREFIX.match(stripped) and _CYRILLIC.search(stripped):
            parts.append(
                f'<p style="{_UA_EN_GLOSS_STYLE}">'
                f'<span style="color:#64748b">{html.escape(stripped)}</span></p>'
            )
            continue

        context_match = _CONTEXT_LINE.match(stripped)
        if context_match and _CYRILLIC.search(context_match.group(2)):
            english = html.escape(context_match.group(1).strip())
            note = html.escape(context_match.group(2).strip())
            parts.append(_ua_en_gloss_row(english, note))
            continue

        if not _CYRILLIC.search(stripped):
            parts.append(_header_line(stripped))
            continue

        parts.append(f'<div style="color:#374151">{html.escape(stripped)}</div>')

    return _meaning_block("".join(parts))


def format_en_ua_output(text: str) -> str:
    """Turn en-ua API text into HTML cards — one card per meaning block."""
    normalized = _normalize_separators(text)
    entries = _parse_en_ua_entries(normalized)
    parts = [
        _format_en_ua_entry(entry, first=(i == 0))
        for i, entry in enumerate(entries)
        if entry.has_content()
    ]

    if not parts:
        return _wrap(html.escape(text).replace("\n", "<br>"))

    return _wrap("".join(parts))


class _EnUaEntry:
    __slots__ = ("meta", "header", "english", "ukrainian", "example")

    def __init__(
        self,
        meta: str = "",
        header: str = "",
        english: str = "",
        ukrainian: str = "",
        example: str = "",
    ) -> None:
        self.meta = meta
        self.header = header
        self.english = english
        self.ukrainian = ukrainian
        self.example = example

    def has_content(self) -> bool:
        return bool(self.meta or self.header or self.english or self.ukrainian or self.example)


def _parse_en_ua_entries(text: str) -> list[_EnUaEntry]:
    entries: list[_EnUaEntry] = []
    lines = text.split("\n")
    i = 0

    while i < len(lines):
        stripped = lines[i].strip()
        if not stripped or stripped == "──────────────────":
            i += 1
            continue

        if stripped.startswith("You probably meant:") or stripped.startswith("Also, if you meant:"):
            entries.append(_EnUaEntry(meta=stripped))
            i += 1
            continue

        header = ""
        if _NUMBERED_LINE.match(stripped) or _is_en_ua_header(lines, i):
            header = stripped
            i += 1

        if i < len(lines) and lines[i].strip() == "→":
            i += 1

        english, ukrainian, consumed = _read_en_ua_definition(lines, i)
        i += consumed

        example = ""
        while i < len(lines) and not lines[i].strip():
            i += 1
        if i < len(lines) and lines[i].strip().startswith("Example:"):
            example = lines[i].strip().removeprefix("Example:").strip()
            i += 1

        if header or english or ukrainian or example:
            entries.append(
                _EnUaEntry(
                    header=header,
                    english=english,
                    ukrainian=ukrainian,
                    example=example,
                )
            )

    return entries


def _is_en_ua_header(lines: list[str], index: int) -> bool:
    stripped = lines[index].strip()
    if not stripped or stripped == "→" or stripped.startswith("Also,"):
        return False
    if _CYRILLIC.search(stripped):
        return False
    if _NUMBERED_LINE.match(stripped):
        return True
    next_idx = index + 1
    while next_idx < len(lines) and not lines[next_idx].strip():
        next_idx += 1
    return next_idx < len(lines) and lines[next_idx].strip() == "→"


def _read_en_ua_definition(lines: list[str], start: int) -> tuple[str, str, int]:
    english_parts: list[str] = []
    ukrainian_parts: list[str] = []
    phase = "english"
    i = start

    while i < len(lines):
        stripped = lines[i].strip()
        if not stripped:
            if phase == "ukrainian":
                break
            i += 1
            continue

        if stripped == "──────────────────":
            break
        if stripped.startswith("Also, if you meant:") or stripped.startswith("You probably meant:"):
            break
        if phase == "english" and (_NUMBERED_LINE.match(stripped) or _is_en_ua_header(lines, i)):
            break

        if phase == "english":
            if _CYRILLIC.search(stripped):
                ukrainian_parts.append(stripped)
                phase = "ukrainian"
            elif stripped == "→":
                pass
            else:
                english_parts.append(stripped)
        elif _CYRILLIC.search(stripped):
            ukrainian_parts.append(stripped)
        else:
            break
        i += 1

    english = " ".join(english_parts)
    ukrainian = " ".join(ukrainian_parts)
    return english, ukrainian, i - start


def _format_en_ua_entry(entry: _EnUaEntry, *, first: bool = True) -> str:
    parts: list[str] = []

    if entry.meta:
        parts.append(_meta_line(entry.meta, typo=entry.meta.startswith("You probably")))

    if entry.header:
        parts.append(_header_line(entry.header))

    if entry.english:
        parts.append(_english_definition(entry.english))

    if entry.ukrainian:
        parts.append(_ukrainian_translation(entry.ukrainian))

    if entry.example:
        parts.append(_example_block(entry.example))

    gap = "" if first else "margin-top:20px;"
    return _meaning_block("".join(parts), extra_style=gap)


RESULT_LINE_HEIGHT = "1"
RESULT_WRAP_STYLE = f"font-family:Segoe UI,sans-serif;line-height:{RESULT_LINE_HEIGHT};color:#334155"

_UA_EN_GLOSS_STYLE = (
    f"margin:0 0 2px 0; padding:0; line-height:{RESULT_LINE_HEIGHT}; "
    "-qt-block-indent:0; text-indent:0px;"
)


def _wrap(body: str) -> str:
    return (
        f'<div style="{RESULT_WRAP_STYLE}">'
        f"{body}</div>"
    )
