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


def _max_ts(left: str, right: str) -> str:
    left = left or ""
    right = right or ""
    return left if left >= right else right


def _pick_side(local_ts: str, remote_ts: str) -> str:
    if (remote_ts or "") > (local_ts or ""):
        return "remote"
    return "local"
