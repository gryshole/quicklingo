from __future__ import annotations

import logging
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from quicklingo.paths import user_data_dir
from quicklingo.sync.snapshot import create_snapshot

_logger = logging.getLogger("quicklingo.sync.presync_backup")

PRESYNC_KEEP = 25
_BACKUP_GLOBS = ("history-*.zip", "history-*.db")


def presync_backup_dir() -> Path:
    path = user_data_dir() / "backups" / "presync"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _list_presync_backups(directory: Path) -> list[Path]:
    files: list[Path] = []
    for pattern in _BACKUP_GLOBS:
        files.extend(p for p in directory.glob(pattern) if p.is_file())
    # Sort by filename so history-YYYYMMDD-HHMMSS… order is chronological.
    return sorted(files, key=lambda p: p.name)


def rotate_presync_backups(directory: Path, *, keep: int = PRESYNC_KEEP) -> None:
    files = _list_presync_backups(directory)
    excess = len(files) - keep
    if excess <= 0:
        return
    for path in files[:excess]:
        try:
            path.unlink()
        except OSError:
            _logger.warning("Failed to remove old presync backup %s", path, exc_info=True)


def _archive_db_max_compression(db_path: Path, archive_path: Path) -> None:
    """Pack snapshot into a zip using the strongest stdlib compressor available."""
    if archive_path.exists():
        archive_path.unlink()
    # LZMA typically shrinks SQLite dumps far more than DEFLATE; fall back if unsupported.
    try:
        with zipfile.ZipFile(
            archive_path,
            mode="w",
            compression=zipfile.ZIP_LZMA,
        ) as zf:
            zf.write(db_path, arcname="history.db")
        return
    except Exception:
        if archive_path.exists():
            archive_path.unlink()
    with zipfile.ZipFile(
        archive_path,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as zf:
        zf.write(db_path, arcname="history.db")


def create_presync_backup(*, keep: int = PRESYNC_KEEP) -> Path | None:
    """Snapshot history.db before sync, store as max-compressed zip. Returns path or None."""
    try:
        directory = presync_backup_dir()
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        dest = directory / f"history-{stamp}.zip"
        if dest.exists():
            stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
            dest = directory / f"history-{stamp}.zip"

        with tempfile.TemporaryDirectory(prefix="quicklingo-presync-") as tmp:
            raw = Path(tmp) / "history.db"
            create_snapshot(raw)
            _archive_db_max_compression(raw, dest)

        rotate_presync_backups(directory, keep=keep)
        return dest
    except Exception:
        _logger.warning("Pre-sync backup failed; continuing sync", exc_info=True)
        return None
