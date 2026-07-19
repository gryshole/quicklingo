from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

from quicklingo import settings
from quicklingo.sync.cloud.base import request_with_auth
from quicklingo.sync.models import SNAPSHOT_FILENAME
from quicklingo.sync.oauth.providers import google as google_oauth
from quicklingo.sync.oauth.tokens import OAuthTokens
from quicklingo.sync.transport import OAuthCloudTransport

DRIVE_API = "https://www.googleapis.com/drive/v3"
UPLOAD_API = "https://www.googleapis.com/upload/drive/v3/files"


class GoogleDriveTransport(OAuthCloudTransport):
    provider_id = "google_drive"

    def _do_refresh(self, current: OAuthTokens) -> OAuthTokens:
        return google_oauth.refresh_tokens(
            client_id=settings.get_sync_google_client_id(),
            client_secret=settings.get_sync_google_client_secret(),
            refresh_token=current.refresh_token,
        )

    def _find_file_id(self, filename: str, access_token: str) -> str | None:
        response = request_with_auth(
            "GET",
            DRIVE_API + "/files",
            access_token=access_token,
            params={
                "spaces": "appDataFolder",
                "fields": "files(id,name)",
                "pageSize": 100,
            },
            retry_on_unauthorized=self._retry_token,
        )
        for item in response.json().get("files", []):
            if str(item.get("name", "")) == filename:
                return str(item["id"])
        return None

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
        request_with_auth(
            "POST",
            UPLOAD_API,
            access_token=access_token,
            params={"uploadType": "multipart"},
            files={
                "metadata": (
                    None,
                    json.dumps(metadata),
                    "application/json; charset=UTF-8",
                ),
                "file": (filename, content, "application/octet-stream"),
            },
            retry_on_unauthorized=self._retry_token,
        )
