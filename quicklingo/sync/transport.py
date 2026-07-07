from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse

import httpx

from quicklingo.sync.models import MANIFEST_FILENAME, SNAPSHOT_FILENAME

SYNC_TRANSPORTS = frozenset(
    {"webdav", "google_drive", "dropbox", "onedrive"}
)


class SyncTransport(ABC):
    @abstractmethod
    def download_snapshot(self, dest: Path) -> bool:
        """Return True if a remote snapshot was downloaded."""

    @abstractmethod
    def upload_snapshot(self, snapshot: Path, manifest_path: Path) -> None:
        ...


class WebDavTransport(SyncTransport):
    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/") + "/"
        self._auth = (username, password)
        self._client = client

    def _url(self, name: str) -> str:
        return urljoin(self._base_url, quote(name))

    def _open_client(self) -> httpx.Client:
        if self._client is not None:
            return self._client
        return httpx.Client(timeout=120.0, auth=self._auth)

    def download_snapshot(self, dest: Path) -> bool:
        dest.parent.mkdir(parents=True, exist_ok=True)
        client = self._open_client()
        owns_client = self._client is None
        try:
            response = client.get(self._url(SNAPSHOT_FILENAME))
            if response.status_code == 404:
                return False
            response.raise_for_status()
            dest.write_bytes(response.content)
        finally:
            if owns_client:
                client.close()
        return True

    def upload_snapshot(self, snapshot: Path, manifest_path: Path) -> None:
        client = self._open_client()
        owns_client = self._client is None
        try:
            for name, path in (
                (SNAPSHOT_FILENAME, snapshot),
                (MANIFEST_FILENAME, manifest_path),
            ):
                with path.open("rb") as handle:
                    response = client.put(self._url(name), content=handle.read())
                response.raise_for_status()
        finally:
            if owns_client:
                client.close()


def build_transport(*, transport: str) -> SyncTransport:
    from quicklingo import settings
    from quicklingo.sync.cloud.dropbox import DropboxTransport
    from quicklingo.sync.cloud.google_drive import GoogleDriveTransport
    from quicklingo.sync.cloud.onedrive import OneDriveTransport

    if transport not in SYNC_TRANSPORTS:
        raise ValueError("Sync transport is not configured")

    if transport == "webdav":
        webdav_url = settings.get_sync_webdav_url()
        parsed = urlparse(webdav_url.strip())
        if not parsed.scheme or not parsed.netloc:
            raise ValueError("Invalid WebDAV URL")
        return WebDavTransport(
            webdav_url.strip(),
            settings.get_sync_webdav_username().strip(),
            settings.get_sync_webdav_password(),
        )
    if transport == "google_drive":
        return GoogleDriveTransport()
    if transport == "dropbox":
        return DropboxTransport()
    if transport == "onedrive":
        return OneDriveTransport()
    raise ValueError("Sync transport is not configured")
