from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from quicklingo.sync.cloud.google_drive import UPLOAD_API, GoogleDriveTransport
from quicklingo.sync.models import MANIFEST_FILENAME, SNAPSHOT_FILENAME
from quicklingo.sync.oauth.tokens import OAuthTokens


class GoogleDriveTransportTests(unittest.TestCase):
    def test_download_returns_false_when_missing(self) -> None:
        transport = GoogleDriveTransport()
        tokens = OAuthTokens(
            access_token="access-token",
            refresh_token="refresh-token",
            account_label="user@example.com",
        )
        with (
            patch(
                "quicklingo.sync.cloud.google_drive.settings.get_sync_oauth_tokens",
                return_value=tokens,
            ),
            patch.object(transport, "_find_file_id", return_value=None),
        ):
            dest = Path(tempfile.mkdtemp()) / "remote.db"
            self.assertFalse(transport.download_snapshot(dest))

    def test_not_connected_without_refresh_token(self) -> None:
        transport = GoogleDriveTransport()
        with patch(
            "quicklingo.sync.cloud.google_drive.settings.get_sync_oauth_tokens",
            return_value=OAuthTokens(access_token="", refresh_token=""),
        ):
            with self.assertRaises(ValueError):
                transport.download_snapshot(Path(tempfile.mkdtemp()) / SNAPSHOT_FILENAME)

    def test_upload_updates_existing_file_via_upload_endpoint(self) -> None:
        transport = GoogleDriveTransport()
        tokens = OAuthTokens(
            access_token="access-token",
            refresh_token="refresh-token",
            account_label="user@example.com",
        )
        with tempfile.TemporaryDirectory() as tmp:
            snapshot = Path(tmp) / SNAPSHOT_FILENAME
            manifest = Path(tmp) / MANIFEST_FILENAME
            snapshot.write_bytes(b"sqlite-bytes")
            manifest.write_text('{"seq": 1}', encoding="utf-8")

            with (
                patch(
                    "quicklingo.sync.cloud.google_drive.settings.get_sync_oauth_tokens",
                    return_value=tokens,
                ),
                patch.object(transport, "_find_file_id", return_value="file-123"),
                patch(
                    "quicklingo.sync.cloud.google_drive.request_with_auth"
                ) as request_with_auth,
            ):
                transport.upload_snapshot(snapshot, manifest)

            self.assertEqual(request_with_auth.call_count, 2)
            for call in request_with_auth.call_args_list:
                self.assertEqual(call.args[0], "PATCH")
                self.assertTrue(
                    call.args[1].startswith(f"{UPLOAD_API}/"),
                    call.args[1],
                )
                self.assertEqual(call.kwargs["params"], {"uploadType": "media"})


if __name__ == "__main__":
    unittest.main()
