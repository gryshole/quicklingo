from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

SCHEMA_VERSION = 1
SNAPSHOT_FILENAME = "history.snapshot.db"
MANIFEST_FILENAME = "sync_manifest.json"


@dataclass
class SyncManifest:
    schema_version: int = SCHEMA_VERSION
    device_id: str = ""
    updated_at: str = ""
    db_sha256: str = ""
    seq: int = 0

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "device_id": self.device_id,
            "updated_at": self.updated_at,
            "db_sha256": self.db_sha256,
            "seq": self.seq,
        }

    @classmethod
    def from_dict(cls, data: dict) -> SyncManifest:
        return cls(
            schema_version=int(data.get("schema_version", SCHEMA_VERSION)),
            device_id=str(data.get("device_id", "")),
            updated_at=str(data.get("updated_at", "")),
            db_sha256=str(data.get("db_sha256", "")),
            seq=int(data.get("seq", 0)),
        )


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def read_manifest(path: Path) -> SyncManifest | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return SyncManifest.from_dict(data)


def write_manifest(path: Path, manifest: SyncManifest) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


@dataclass
class SyncMergeStats:
    translations_added: int = 0
    decks_added: int = 0
    cards_added: int = 0
    cards_updated: int = 0
    quiz_added: int = 0
    quiz_updated: int = 0
    deletions_applied: int = 0
    tombstones_merged: int = 0


@dataclass
class SyncResult:
    ok: bool
    message: str = ""
    merge: SyncMergeStats = field(default_factory=SyncMergeStats)
    upload: SyncMergeStats = field(default_factory=SyncMergeStats)
    uploaded: bool = False
    downloaded: bool = False


def file_sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_sync_ts(value: str) -> datetime | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = f"{raw[:-1]}+00:00"
        parsed = datetime.fromisoformat(raw)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%f"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def _max_ts(left: str, right: str) -> str:
    left_dt = _parse_sync_ts(left)
    right_dt = _parse_sync_ts(right)
    if left_dt is None and right_dt is None:
        return left or right or ""
    if left_dt is None:
        return right or ""
    if right_dt is None:
        return left or ""
    return left if left_dt >= right_dt else right


def _pick_side(local_ts: str, remote_ts: str) -> str:
    local_dt = _parse_sync_ts(local_ts)
    remote_dt = _parse_sync_ts(remote_ts)
    if remote_dt is None:
        return "local"
    if local_dt is None:
        return "remote"
    if remote_dt > local_dt:
        return "remote"
    return "local"


def _pick_remote_when_newer_or_tie(local_ts: str, remote_ts: str) -> str:
    """Prefer remote on ties — used for deck placement during download merge."""
    local_dt = _parse_sync_ts(local_ts)
    remote_dt = _parse_sync_ts(remote_ts)
    if remote_dt is None:
        return "local"
    if local_dt is None:
        return "remote"
    if remote_dt >= local_dt:
        return "remote"
    return "local"
