from __future__ import annotations

import json
from pathlib import Path

import httpx

from quicklingo import settings
from quicklingo.sync.cloud.base import request_with_auth
from quicklingo.sync.models import SNAPSHOT_FILENAME
from quicklingo.sync.oauth.providers import dropbox as dropbox_oauth
from quicklingo.sync.oauth.tokens import OAuthTokens
from quicklingo.sync.transport import OAuthCloudTransport

DROPBOX_CONTENT = "https://content.dropboxapi.com/2"
REMOTE_PREFIX = "/QuickLingo"


class DropboxTransport(OAuthCloudTransport):
    provider_id = "dropbox"

    def _do_refresh(self, current: OAuthTokens) -> OAuthTokens:
        return dropbox_oauth.refresh_tokens(
            app_key=settings.get_sync_dropbox_app_key(),
            app_secret=settings.get_sync_dropbox_app_secret(),
            refresh_token=current.refresh_token,
        )

    def _remote_path(self, filename: str) -> str:
        return f"{REMOTE_PREFIX}/{filename}"

    def download_snapshot(self, dest: Path) -> bool:
        access_token = self._access_token()
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            response = request_with_auth(
                "POST",
                f"{DROPBOX_CONTENT}/files/download",
                access_token=access_token,
                headers={
                    "Dropbox-API-Arg": json.dumps(
                        {"path": self._remote_path(SNAPSHOT_FILENAME)}
                    ),
                },
                retry_on_unauthorized=self._retry_token,
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 409:
                return False
            raise
        dest.write_bytes(response.content)
        return True

    def _upload_file(self, filename: str, path: Path, access_token: str) -> None:
        request_with_auth(
            "POST",
            f"{DROPBOX_CONTENT}/files/upload",
            access_token=access_token,
            headers={
                "Content-Type": "application/octet-stream",
                "Dropbox-API-Arg": json.dumps(
                    {
                        "path": self._remote_path(filename),
                        "mode": "overwrite",
                        "autorename": False,
                    }
                ),
            },
            content=path.read_bytes(),
            retry_on_unauthorized=self._retry_token,
        )
