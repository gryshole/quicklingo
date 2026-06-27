from __future__ import annotations

import json
from datetime import datetime, timezone

from quicklingo.db import history


def _record_to_dict(record: history.TranslationRecord) -> dict:
    return {
        "id": record.id,
        "created_at": record.created_at,
        "direction": record.direction,
        "source_text": record.source_text,
        "result_text": record.result_text,
        "model": record.model,
        "profile_id": record.profile_id,
        "content_hash": record.content_hash,
        "is_starred": record.is_starred,
        "tags": history.parse_tags(record.tags),
    }


def export_json(records: list[history.TranslationRecord]) -> str:
    payload = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "count": len(records),
        "records": [_record_to_dict(record) for record in records],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def export_markdown(records: list[history.TranslationRecord]) -> str:
    lines: list[str] = ["# QuickLingo history export", ""]
    if not records:
        lines.append("_No records._")
        lines.append("")
        return "\n".join(lines)

    for record in records:
        tags = history.format_tags(history.parse_tags(record.tags))
        star = " ★" if record.is_starred else ""
        lines.append(
            f"## [{record.id}] {record.created_at} · {record.direction} · {record.model}{star}"
        )
        lines.append("")
        lines.append("**Source**")
        lines.append("")
        lines.append(record.source_text.strip())
        lines.append("")
        lines.append("**Translation**")
        lines.append("")
        quoted = record.result_text.strip().replace("\n", "\n> ")
        lines.append("> " + quoted)
        lines.append("")
        if tags:
            lines.append(f"**Tags:** {tags}")
            lines.append("")
        if record.profile_id:
            lines.append(f"_Profile: {record.profile_id}_")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"
