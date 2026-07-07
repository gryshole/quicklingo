from __future__ import annotations

import json
from pathlib import Path

import httpx

from quicklingo import settings
from quicklingo.sync.cloud.base import ensure_access_token, request_with_auth
from quicklingo.sync.models import MANIFEST_FILENAME, SNAPSHOT_FILENAME
from quicklingo.sync.oauth.providers import dropbox as dropbox_oauth
from quicklingo.sync.oauth.tokens import OAuthTokens
from quicklingo.sync.transport import SyncTransport

DROPBOX_API = "https://api.dropboxapi.com/2"
DROPBOX_CONTENT = "https://content.dropboxapi.com/2"
REMOTE_PREFIX = "/QuickLingo"


class DropboxTransport(SyncTransport):
    def _tokens(self) -> OAuthTokens:
        tokens = settings.get_sync_oauth_tokens("dropbox")
        if not tokens.refresh_token:
            raise ValueError("Not connected")
        return tokens

    def _refresh(self) -> OAuthTokens:
        current = self._tokens()
        refreshed = dropbox_oauth.refresh_tokens(
            app_key=settings.get_sync_dropbox_app_key(),
            app_secret=settings.get_sync_dropbox_app_secret(),
            refresh_token=current.refresh_token,
        )
        refreshed.account_label = current.account_label or refreshed.account_label
        settings.save_sync_oauth_tokens("dropbox", refreshed)
        return refreshed

    def _access_token(self) -> str:
        tokens = self._tokens()
        return ensure_access_token(
            "dropbox",
            tokens,
            self._refresh,
            lambda value: settings.save_sync_oauth_tokens("dropbox", value),
        )

    def _retry_token(self) -> str:
        return self._refresh().access_token

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

    def upload_snapshot(self, snapshot: Path, manifest_path: Path) -> None:
        access_token = self._access_token()
        for filename, path in (
            (SNAPSHOT_FILENAME, snapshot),
            (MANIFEST_FILENAME, manifest_path),
        ):
            self._upload_file(filename, path, access_token)

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
