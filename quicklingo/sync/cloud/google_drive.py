from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

import httpx

from quicklingo import settings
from quicklingo.sync.cloud.base import ensure_access_token, request_with_auth
from quicklingo.sync.models import MANIFEST_FILENAME, SNAPSHOT_FILENAME
from quicklingo.sync.oauth.providers import google as google_oauth
from quicklingo.sync.oauth.tokens import OAuthTokens
from quicklingo.sync.transport import SyncTransport

DRIVE_API = "https://www.googleapis.com/drive/v3"
UPLOAD_API = "https://www.googleapis.com/upload/drive/v3/files"


class GoogleDriveTransport(SyncTransport):
    def _tokens(self) -> OAuthTokens:
        tokens = settings.get_sync_oauth_tokens("google_drive")
        if not tokens.refresh_token:
            raise ValueError("Not connected")
        return tokens

    def _refresh(self) -> OAuthTokens:
        current = self._tokens()
        refreshed = google_oauth.refresh_tokens(
            client_id=settings.get_sync_google_client_id(),
            client_secret=settings.get_sync_google_client_secret(),
            refresh_token=current.refresh_token,
        )
        refreshed.account_label = current.account_label or refreshed.account_label
        settings.save_sync_oauth_tokens("google_drive", refreshed)
        return refreshed

    def _access_token(self) -> str:
        tokens = self._tokens()
        return ensure_access_token(
            "google_drive",
            tokens,
            self._refresh,
            lambda value: settings.save_sync_oauth_tokens("google_drive", value),
        )

    def _retry_token(self) -> str:
        return self._refresh().access_token

    def _find_file_id(self, filename: str, access_token: str) -> str | None:
        query = (
            f"name = '{filename}' and "
            "trashed = false and "
            "'appDataFolder' in parents"
        )
        response = request_with_auth(
            "GET",
            DRIVE_API + "/files",
            access_token=access_token,
            params={
                "spaces": "appDataFolder",
                "fields": "files(id,name)",
                "q": query,
            },
            retry_on_unauthorized=self._retry_token,
        )
        files = response.json().get("files", [])
        if not files:
            return None
        return str(files[0]["id"])

    def download_snapshot(self, dest: Path) -> bool:
        access_token = self._access_token()
        file_id = self._find_file_id(SNAPSHOT_FILENAME, access_token)
        if not file_id:
            return False
        dest.parent.mkdir(parents=True, exist_ok=True)
        response = request_with_auth(
            "GET",
            f"{DRIVE_API}/files/{quote(file_id)}",
            access_token=access_token,
            params={"alt": "media"},
            retry_on_unauthorized=self._retry_token,
        )
        dest.write_bytes(response.content)
        return True

    def upload_snapshot(self, snapshot: Path, manifest_path: Path) -> None:
        access_token = self._access_token()
        for filename, path in (
            (SNAPSHOT_FILENAME, snapshot),
            (MANIFEST_FILENAME, manifest_path),
        ):
            self._upload_file(filename, path, access_token)

    def _upload_file(self, filename: str, path: Path, access_token: str) -> None:
        file_id = self._find_file_id(filename, access_token)
        content = path.read_bytes()
        if file_id:
            request_with_auth(
                "PATCH",
                f"{UPLOAD_API}/{quote(file_id)}",
                access_token=access_token,
                params={"uploadType": "media"},
                content=content,
                headers={"Content-Type": "application/octet-stream"},
                retry_on_unauthorized=self._retry_token,
            )
            return
        metadata = {
            "name": filename,
            "parents": ["appDataFolder"],
        }
        response = httpx.post(
            UPLOAD_API,
            params={"uploadType": "multipart"},
            headers={"Authorization": f"Bearer {access_token}"},
            files={
                "metadata": (
                    None,
                    json.dumps(metadata),
                    "application/json; charset=UTF-8",
                ),
                "file": (filename, content, "application/octet-stream"),
            },
            timeout=120.0,
        )
        if response.status_code == 401:
            access_token = self._retry_token()
            response = httpx.post(
                UPLOAD_API,
                params={"uploadType": "multipart"},
                headers={"Authorization": f"Bearer {access_token}"},
                files={
                    "metadata": (
                        None,
                        json.dumps(metadata),
                        "application/json; charset=UTF-8",
                    ),
                    "file": (filename, content, "application/octet-stream"),
                },
                timeout=120.0,
            )
        response.raise_for_status()
