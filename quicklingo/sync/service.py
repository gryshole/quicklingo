from __future__ import annotations

import tempfile
from pathlib import Path

from quicklingo import settings
from quicklingo.sync.manifest import read_manifest, write_manifest
from quicklingo.sync.merge import compute_upload_stats, merge_remote_into_local
from quicklingo.sync.models import SyncManifest, SyncResult, file_sha256, utc_now_iso
from quicklingo.sync.snapshot import checkpoint_database, create_snapshot
from quicklingo.sync.transport import build_transport


def sync_now() -> SyncResult:
    try:
        transport = build_transport(transport=settings.get_sync_transport())
    except ValueError as exc:
        return SyncResult(ok=False, message=str(exc))
    except Exception as exc:
        settings.save_sync_status(
            last_sync_at=utc_now_iso(),
            last_sync_status=str(exc),
        )
        return SyncResult(ok=False, message=str(exc))

    device_id = settings.get_sync_device_id()
    merge_stats = None
    downloaded = False
    remote_snapshot_path: Path | None = None

    try:
        with tempfile.TemporaryDirectory(prefix="quicklingo-sync-") as tmp:
            tmp_dir = Path(tmp)
            remote_snapshot = tmp_dir / "remote.snapshot.db"
            local_upload = tmp_dir / "upload.snapshot.db"
            manifest_path = tmp_dir / "sync_manifest.json"

            checkpoint_database()
            if transport.download_snapshot(remote_snapshot):
                downloaded = True
                remote_snapshot_path = remote_snapshot
                merge_stats = merge_remote_into_local(remote_snapshot)
                checkpoint_database()

            create_snapshot(local_upload)
            upload_stats = compute_upload_stats(
                local_upload,
                remote_snapshot_path,
            )
            manifest = SyncManifest()
            manifest.schema_version = 1
            manifest.device_id = device_id
            manifest.updated_at = utc_now_iso()
            manifest.db_sha256 = file_sha256(local_upload)
            manifest.seq = settings.get_sync_manifest_seq() + 1
            write_manifest(manifest_path, manifest)
            transport.upload_snapshot(local_upload, manifest_path)
            settings.save_sync_manifest_seq(manifest.seq)
    except Exception as exc:
        settings.save_sync_status(
            last_sync_at=utc_now_iso(),
            last_sync_status=str(exc),
        )
        return SyncResult(ok=False, message=str(exc))

    settings.save_sync_status(
        last_sync_at=utc_now_iso(),
        last_sync_status="ok",
    )
    stats = merge_stats
    if stats is None:
        from quicklingo.sync.models import SyncMergeStats

        stats = SyncMergeStats()
    message = (
        f"down +{stats.translations_added}/up +{upload_stats.translations_added} translations, "
        f"down +{stats.cards_added}/up +{upload_stats.cards_added} cards"
    )
    return SyncResult(
        ok=True,
        message=message,
        merge=stats,
        upload=upload_stats,
        uploaded=True,
        downloaded=downloaded,
    )
