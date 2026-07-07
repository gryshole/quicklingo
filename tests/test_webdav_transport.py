from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import httpx

from quicklingo.sync.models import MANIFEST_FILENAME, SNAPSHOT_FILENAME
from quicklingo.sync.transport import WebDavTransport


class WebDavTransportTests(unittest.TestCase):
    def test_download_returns_false_on_404(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.method, "GET")
            self.assertTrue(request.url.path.endswith(SNAPSHOT_FILENAME))
            return httpx.Response(404)

        transport = WebDavTransport(
            "https://example.com/dav/",
            "user",
            "pass",
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
        dest = Path(tempfile.mkdtemp()) / "remote.db"
        self.assertFalse(transport.download_snapshot(dest))

    def test_download_writes_bytes(self) -> None:
        payload = b"sqlite-bytes"

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=payload)

        transport = WebDavTransport(
            "https://example.com/dav",
            "user",
            "pass",
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
        dest = Path(tempfile.mkdtemp()) / "remote.db"
        self.assertTrue(transport.download_snapshot(dest))
        self.assertEqual(dest.read_bytes(), payload)

    def test_upload_puts_both_files(self) -> None:
        uploaded: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            uploaded.append(request.url.path.rsplit("/", 1)[-1])
            self.assertEqual(request.method, "PUT")
            return httpx.Response(201)

        transport = WebDavTransport(
            "https://example.com/dav/",
            "user",
            "pass",
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
        tmp = Path(tempfile.mkdtemp())
        snapshot = tmp / SNAPSHOT_FILENAME
        manifest = tmp / MANIFEST_FILENAME
        snapshot.write_bytes(b"db")
        manifest.write_text("{}", encoding="utf-8")
        transport.upload_snapshot(snapshot, manifest)
        self.assertEqual(uploaded, [SNAPSHOT_FILENAME, MANIFEST_FILENAME])


if __name__ == "__main__":
    unittest.main()
