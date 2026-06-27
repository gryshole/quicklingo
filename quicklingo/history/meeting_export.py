from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from quicklingo.db import history


@dataclass
class _Session:
    records: list[history.TranslationRecord]

    def append(self, record: history.TranslationRecord) -> None:
        self.records.append(record)


def _parse_ts(value: str) -> datetime:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return datetime.min


def group_sessions(
    records: list[history.TranslationRecord],
    *,
    gap_minutes: int,
) -> list[list[history.TranslationRecord]]:
    if not records:
        return []
    ordered = sorted(records, key=lambda r: r.id)
    sessions: list[_Session] = [_Session([ordered[0]])]
    gap_seconds = max(1, gap_minutes) * 60
    for record in ordered[1:]:
        prev = sessions[-1].records[-1]
        delta = (_parse_ts(record.created_at) - _parse_ts(prev.created_at)).total_seconds()
        if delta > gap_seconds:
            sessions.append(_Session([record]))
        else:
            sessions[-1].append(record)
    return [session.records for session in sessions]


def export_transcript_markdown(
    records: list[history.TranslationRecord],
    *,
    gap_minutes: int,
) -> str:
    sessions = group_sessions(records, gap_minutes=gap_minutes)
    lines: list[str] = ["# QuickLingo meeting transcript", ""]
    for index, session in enumerate(sessions, start=1):
        if not session:
            continue
        start = session[0].created_at
        end = session[-1].created_at
        lines.append(f"## Session {index} ({start} — {end})")
        lines.append("")
        for record in session:
            lines.append(f"**[{record.created_at}]** ({record.direction})")
            lines.append("")
            lines.append(record.source_text.strip())
            lines.append("")
            lines.append("> " + record.result_text.strip().replace("\n", "\n> "))
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def export_transcript_text(
    records: list[history.TranslationRecord],
    *,
    gap_minutes: int,
) -> str:
    sessions = group_sessions(records, gap_minutes=gap_minutes)
    lines: list[str] = ["QuickLingo meeting transcript", ""]
    for index, session in enumerate(sessions, start=1):
        if not session:
            continue
        start = session[0].created_at
        end = session[-1].created_at
        lines.append(f"--- Session {index} ({start} — {end}) ---")
        lines.append("")
        for record in session:
            lines.append(f"[{record.created_at}] ({record.direction})")
            lines.append(record.source_text.strip())
            lines.append("---")
            lines.append(record.result_text.strip())
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"
