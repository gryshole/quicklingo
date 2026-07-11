"""Early Qt / FFmpeg environment tweaks.

Import this module before creating QApplication or loading QtMultimedia.
FFmpeg otherwise dumps priming-sample warnings and stream dumps to the console
when short card MP3s are played (harmless, but very noisy).
"""

from __future__ import annotations

import os

_FFMPEG_SILENCE_RULE = "qt.multimedia.ffmpeg*=false"


def configure_qt_env() -> None:
    """Silence Qt FFmpeg backend chatter unless the user already set rules."""
    rules = os.environ.get("QT_LOGGING_RULES", "").strip()
    if "qt.multimedia.ffmpeg" in rules:
        return
    os.environ["QT_LOGGING_RULES"] = (
        f"{rules};{_FFMPEG_SILENCE_RULE}" if rules else _FFMPEG_SILENCE_RULE
    )


def apply_qt_logging_filters() -> None:
    """Re-apply filters after QApplication exists (covers late plugin loads)."""
    from PySide6.QtCore import QLoggingCategory

    QLoggingCategory.setFilterRules(_FFMPEG_SILENCE_RULE)


configure_qt_env()
