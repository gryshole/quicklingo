"""Declarative formatter rules engine (rules:v1)."""

from __future__ import annotations

import html
import re
from typing import Any

from quicklingo.ui.format_output import (
    RESULT_WRAP_STYLE,
    format_en_ua_output,
    format_plain_output,
    format_ua_en_output,
)

_CYRILLIC = re.compile(r"[а-яА-ЯіІїЇєЄґҐ]")
_SEPARATOR_CHARS = frozenset("-─_=")


def _is_separator_line(line: str) -> bool:
    stripped = line.strip()
    return len(stripped) >= 3 and all(ch in _SEPARATOR_CHARS for ch in stripped)


def _parse_context_line(line: str) -> tuple[str, str] | None:
    parts = line.split(" — ", 1)
    if len(parts) != 2:
        return None
    left, right = parts[0].strip(), parts[1].strip()
    if not left or not right or len(left) > 200 or len(right) > 500:
        return None
    return left, right


def _is_numbered_line(line: str) -> bool:
    if not line.startswith("["):
        return False
    end = line.find("]")
    if end <= 1:
        return False
    return line[1:end].isdigit()


def run_rules_v1(rules: list[dict[str, Any]], text: str) -> str:
    ctx: dict[str, Any] = {"text": text, "blocks": [text], "html_parts": []}
    for rule in rules:
        _apply_rule(rule, ctx)
    if ctx.get("document_html"):
        return ctx["document_html"]
    parts = ctx.get("html_parts") or []
    if parts:
        body = "".join(parts)
        return f'<div style="{RESULT_WRAP_STYLE}">{body}</div>'
    return format_plain_output(text)


def _apply_rule(rule: dict[str, Any], ctx: dict[str, Any]) -> None:
    rtype = rule.get("type", "")
    if rtype == "escape_plain":
        ctx["document_html"] = format_plain_output(ctx["text"])
    elif rtype == "normalize_separators":
        ctx["text"] = _normalize_separators(ctx["text"])
        ctx["blocks"] = [ctx["text"]]
    elif rtype == "split_blocks":
        pattern = rule.get("pattern", r"\n(?=──────────────────\n)")
        ctx["blocks"] = [b for b in re.split(pattern, ctx["text"]) if b.strip()]
    elif rtype == "foreach_block":
        child_rules = rule.get("rules", [])
        html_parts: list[str] = []
        for i, block in enumerate(ctx["blocks"]):
            block_ctx: dict[str, Any] = {
                "text": block.strip().removeprefix("──────────────────").strip(),
                "blocks": [block],
                "html_parts": [],
                "block_index": i,
            }
            for child in child_rules:
                _apply_rule(child, block_ctx)
            if block_ctx.get("block_html"):
                html_parts.append(block_ctx["block_html"])
            elif block_ctx.get("html_parts"):
                html_parts.extend(block_ctx["html_parts"])
        ctx["html_parts"] = html_parts
    elif rtype == "format_ua_en_block":
        ctx["block_html"] = _format_ua_en_block_rules(ctx["text"])
    elif rtype == "format_en_ua_blocks":
        ctx["html_parts"] = _format_en_ua_blocks_rules(ctx["text"])
    elif rtype == "wrap_card":
        body = rule.get("body_from") or "block_html"
        content = ctx.get(body) or "".join(ctx.get("html_parts", []))
        if content:
            margin = rule.get("margin_top", "")
            extra = f"margin-top:{margin};" if margin else ""
            ctx["block_html"] = _card(content, extra_style=extra)
    elif rtype == "line_style":
        _apply_line_style(rule, ctx)
    elif rtype == "wrap_document":
        body = "".join(ctx.get("html_parts", []))
        if not body:
            body = ctx.get("block_html", "")
        ctx["document_html"] = f'<div style="{RESULT_WRAP_STYLE}">{body}</div>'


def _apply_line_style(rule: dict[str, Any], ctx: dict[str, Any]) -> None:
    parts: list[str] = ctx.setdefault("html_parts", [])
    for line in ctx["text"].split("\n"):
        stripped = line.strip()
        if not stripped or stripped == "──────────────────":
            continue
        pattern = rule.get("pattern", "")
        template = rule.get("template", "")
        if pattern:
            match = re.match(pattern, stripped)
            if match:
                rendered = template
                for i, group in enumerate(match.groups(), start=1):
                    rendered = rendered.replace(f"${i}", html.escape(group))
                parts.append(rendered)
                continue
        prefix = rule.get("prefix", "")
        if prefix and stripped.startswith(prefix):
            rest = stripped.removeprefix(prefix).strip()
            parts.append(template.replace("$1", html.escape(rest)))
            continue
        if rule.get("fallback_header") and not _CYRILLIC.search(stripped):
            parts.append(_header_line(stripped))
        elif rule.get("fallback_text"):
            parts.append(f'<div style="color:#374151">{html.escape(stripped)}</div>')


def _normalize_separators(text: str) -> str:
    lines: list[str] = []
    for line in text.split("\n"):
        if _is_separator_line(line):
            lines.append("──────────────────")
        else:
            lines.append(line)
    return "\n".join(lines).strip()


def _card(body: str, *, extra_style: str = "") -> str:
    return (
        '<div style="background:#f8fafc;border:1px solid #e2e8f0;'
        f'border-radius:6px;padding:10px 12px;margin-bottom:10px;{extra_style}">'
        f"{body}</div>"
    )


def _header_line(text: str) -> str:
    return (
        f'<div style="font-weight:600;font-size:1.1em;color:#1d4ed8;margin:2px 0">'
        f"{html.escape(text)}</div>"
    )


def _meta_line(text: str, *, typo: bool) -> str:
    color = "#b45309" if typo else "#6b7280"
    return (
        f'<div style="font-style:italic;color:{color};margin-bottom:8px">'
        f"{html.escape(text)}</div>"
    )


def _example_block(sentence: str) -> str:
    return (
        '<div style="margin-top:8px;padding:8px 10px;background:#ecfdf5;'
        'border-left:3px solid #10b981;border-radius:4px">'
        f'<span style="color:#047857;font-weight:600">Example:</span> '
        f'<span style="color:#065f46;font-style:italic">{html.escape(sentence)}</span>'
        "</div>"
    )


def _format_ua_en_block_rules(block: str) -> str:
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
        if _is_numbered_line(stripped):
            parts.append(_header_line(stripped))
            continue
        if stripped.startswith("—") and _CYRILLIC.search(stripped):
            parts.append(
                f'<div style="color:#64748b;margin:2px 0 6px 12px">'
                f"{html.escape(stripped)}</div>"
            )
            continue
        context_match = _parse_context_line(stripped)
        if context_match and _CYRILLIC.search(context_match[1]):
            english = html.escape(context_match[0])
            note = html.escape(context_match[1])
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


def _format_en_ua_blocks_rules(text: str) -> list[str]:
    from quicklingo.ui.format_output import _parse_en_ua_entries, _format_en_ua_entry

    normalized = _normalize_separators(text)
    entries = _parse_en_ua_entries(normalized)
    return [
        _format_en_ua_entry(entry, first=(i == 0))
        for i, entry in enumerate(entries)
        if entry.has_content()
    ]


# Preset rule sets for UI "duplicate from preset"
PRESET_RULES: dict[str, list[dict[str, Any]]] = {
    "plain": [{"type": "escape_plain"}],
    "ua_en_cards": [
        {"type": "normalize_separators"},
        {
            "type": "split_blocks",
            "pattern": r"\n(?=──────────────────\n|You probably meant: )",
        },
        {
            "type": "foreach_block",
            "rules": [{"type": "format_ua_en_block"}],
        },
        {"type": "wrap_document"},
    ],
    "en_ua_cards": [
        {"type": "normalize_separators"},
        {"type": "format_en_ua_blocks"},
        {"type": "wrap_document"},
    ],
}

BUILTIN_ENGINES = {
    "builtin:plain": "plain",
    "builtin:ua_en_cards": "ua_en_cards",
    "builtin:en_ua_cards": "en_ua_cards",
}


def preset_rules_for_engine(engine: str) -> list[dict[str, Any]]:
    key = BUILTIN_ENGINES.get(engine)
    if key:
        return [dict(r) for r in PRESET_RULES[key]]
    return [{"type": "escape_plain"}]


def preview_formatter(engine: str, rules: list[dict[str, Any]], text: str) -> str:
    if engine.startswith("rules:v1"):
        return run_rules_v1(rules, text)
    if engine == "builtin:plain":
        return format_plain_output(text)
    if engine == "builtin:ua_en_cards":
        return format_ua_en_output(text)
    if engine == "builtin:en_ua_cards":
        return format_en_ua_output(text)
    return format_plain_output(text)
