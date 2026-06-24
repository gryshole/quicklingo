import html
import re

_CYRILLIC = re.compile(r"[а-яА-ЯіІїЇєЄґҐ]")
_UA_EN_SPLIT = re.compile(r"\n(?=──────────────────\n|You probably meant: )")
_SEPARATOR_LINE = re.compile(r"^_+\s*$")
_CONTEXT_LINE = re.compile(r"^(.+?) — (.+)$")
_NUMBERED_LINE = re.compile(r"^(\[\d+\]\s*.+)$")


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


def _card(body: str, *, extra_style: str = "") -> str:
    return (
        '<div style="background:#f8fafc;border:1px solid #e2e8f0;'
        f'border-radius:6px;padding:10px 12px;margin-bottom:10px;{extra_style}">'
        f"{body}</div>"
    )


def _example_block(sentence: str) -> str:
    return (
        '<div style="margin-top:8px;padding:8px 10px;background:#ecfdf5;'
        'border-left:3px solid #10b981;border-radius:4px">'
        f'<span style="color:#047857;font-weight:600">Example:</span> '
        f'<span style="color:#065f46;font-style:italic">{html.escape(sentence)}</span>'
        "</div>"
    )


def _meta_line(text: str, *, typo: bool) -> str:
    color = "#b45309" if typo else "#6b7280"
    return (
        f'<div style="font-style:italic;color:{color};margin-bottom:8px">'
        f"{html.escape(text)}</div>"
    )


def _header_line(text: str) -> str:
    return (
        f'<div style="font-weight:600;font-size:1.1em;color:#1d4ed8;margin:2px 0">'
        f"{html.escape(text)}</div>"
    )


def _english_definition(text: str) -> str:
    return (
        '<div style="margin-top:4px;padding:8px 10px;background:#ecfdf5;'
        'border-left:3px solid #10b981;border-radius:4px">'
        f'<span style="color:#065f46;font-style:italic;line-height:1.5">'
        f"{html.escape(text)}</span>"
        "</div>"
    )


def _ukrainian_translation(text: str) -> str:
    return (
        '<div style="margin-top:10px;padding:6px 10px;background:#eff6ff;'
        'border-left:3px solid #3b82f6;border-radius:4px">'
        f'<span style="color:#1e3a8a;font-weight:600">{html.escape(text)}</span>'
        "</div>"
    )


def _format_ua_en_block(block: str) -> str:
    parts: list[str] = []

    for line in block.split("\n"):
        stripped = line.strip()
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

        if stripped.startswith("—") and _CYRILLIC.search(stripped):
            parts.append(
                f'<div style="color:#64748b;margin:2px 0 6px 12px">'
                f"{html.escape(stripped)}</div>"
            )
            continue

        context_match = _CONTEXT_LINE.match(stripped)
        if context_match and _CYRILLIC.search(context_match.group(2)):
            english = html.escape(context_match.group(1).strip())
            note = html.escape(context_match.group(2).strip())
            parts.append(
                f'<div style="margin:4px 0">'
                f'<span style="font-weight:600;color:#1e40af">{english}</span>'
                f'<span style="color:#64748b"> — {note}</span>'
                "</div>"
            )
            continue

        if not _CYRILLIC.search(stripped):
            parts.append(_header_line(stripped))
            continue

        parts.append(f'<div style="color:#374151">{html.escape(stripped)}</div>')

    return _card("".join(parts))


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
    __slots__ = ("meta", "header", "english", "ukrainian")

    def __init__(
        self,
        meta: str = "",
        header: str = "",
        english: str = "",
        ukrainian: str = "",
    ) -> None:
        self.meta = meta
        self.header = header
        self.english = english
        self.ukrainian = ukrainian

    def has_content(self) -> bool:
        return bool(self.meta or self.header or self.english or self.ukrainian)


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

        if header or english or ukrainian:
            entries.append(_EnUaEntry(header=header, english=english, ukrainian=ukrainian))

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

    gap = "" if first else "margin-top:12px;"
    return _card("".join(parts), extra_style=gap)


RESULT_WRAP_STYLE = "font-family:Segoe UI,sans-serif;line-height:1.45"


def _wrap(body: str) -> str:
    return (
        f'<div style="{RESULT_WRAP_STYLE}">'
        f"{body}</div>"
    )
