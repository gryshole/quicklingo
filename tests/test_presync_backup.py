from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from quicklingo.sync.presync_backup import (
    _archive_db_max_compression,
    create_presync_backup,
    rotate_presync_backups,
)


class PresyncBackupTests(unittest.TestCase):
    def test_rotate_keeps_newest_25(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            for i in range(26):
                (directory / f"history-20260101-{i:06d}.zip").write_bytes(b"x")
            rotate_presync_backups(directory, keep=25)
            remaining = sorted(p.name for p in directory.glob("history-*.zip"))
            self.assertEqual(len(remaining), 25)
            self.assertNotIn("history-20260101-000000.zip", remaining)
            self.assertEqual(remaining[0], "history-20260101-000001.zip")
            self.assertEqual(remaining[-1], "history-20260101-000025.zip")

    def test_rotate_counts_legacy_db_and_zip_together(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            for i in range(20):
                (directory / f"history-20260101-{i:06d}.db").write_bytes(b"x")
            for i in range(20, 30):
                (directory / f"history-20260101-{i:06d}.zip").write_bytes(b"x")
            rotate_presync_backups(directory, keep=25)
            remaining = list(directory.glob("history-*"))
            self.assertEqual(len(remaining), 25)

    def test_archive_uses_max_compression(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            db_path = directory / "history.db"
            # Compressible payload so the compressor has work to do.
            db_path.write_bytes(b"SQLite format 3\x00" + (b"\x00" * 50_000))
            archive = directory / "history-test.zip"
            _archive_db_max_compression(db_path, archive)
            self.assertTrue(archive.is_file())
            self.assertLess(archive.stat().st_size, db_path.stat().st_size)
            with zipfile.ZipFile(archive, "r") as zf:
                info = zf.getinfo("history.db")
                self.assertIn(
                    info.compress_type,
                    (zipfile.ZIP_LZMA, zipfile.ZIP_DEFLATED),
                )
                self.assertEqual(zf.read("history.db"), db_path.read_bytes())

    def test_create_presync_backup_writes_zip_under_user_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            def _fake_snapshot(dest: Path, **_kwargs: object) -> None:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(b"SQLite format 3\x00" + (b"a" * 2000))

            with patch("quicklingo.sync.presync_backup.user_data_dir", return_value=root):
                with patch(
                    "quicklingo.sync.presync_backup.create_snapshot",
                    side_effect=_fake_snapshot,
                ):
                    path = create_presync_backup(keep=25)
            self.assertIsNotNone(path)
            assert path is not None
            self.assertTrue(path.is_file())
            self.assertEqual(path.parent, root / "backups" / "presync")
            self.assertTrue(path.name.startswith("history-"))
            self.assertTrue(path.name.endswith(".zip"))
            with zipfile.ZipFile(path, "r") as zf:
                self.assertIn("history.db", zf.namelist())


if __name__ == "__main__":
    unittest.main()
