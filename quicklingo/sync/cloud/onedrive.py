from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

import httpx

from quicklingo import settings
from quicklingo.sync.cloud.base import ensure_access_token, request_with_auth
from quicklingo.sync.models import MANIFEST_FILENAME, SNAPSHOT_FILENAME
from quicklingo.sync.oauth.providers import microsoft as microsoft_oauth
from quicklingo.sync.oauth.tokens import OAuthTokens
from quicklingo.sync.transport import SyncTransport

GRAPH_API = "https://graph.microsoft.com/v1.0"
REMOTE_PREFIX = "QuickLingo"


class OneDriveTransport(SyncTransport):
    def _tokens(self) -> OAuthTokens:
        tokens = settings.get_sync_oauth_tokens("onedrive")
        if not tokens.refresh_token:
            raise ValueError("Not connected")
        return tokens

    def _refresh(self) -> OAuthTokens:
        current = self._tokens()
        refreshed = microsoft_oauth.refresh_tokens(
            client_id=settings.get_sync_onedrive_client_id(),
            refresh_token=current.refresh_token,
        )
        refreshed.account_label = current.account_label or refreshed.account_label
        settings.save_sync_oauth_tokens("onedrive", refreshed)
        return refreshed

    def _access_token(self) -> str:
        tokens = self._tokens()
        return ensure_access_token(
            "onedrive",
            tokens,
            self._refresh,
            lambda value: settings.save_sync_oauth_tokens("onedrive", value),
        )

    def _retry_token(self) -> str:
        return self._refresh().access_token

    def _item_url(self, filename: str) -> str:
        path = f"{REMOTE_PREFIX}/{filename}"
        return (
            f"{GRAPH_API}/me/drive/special/approot:/{quote(path, safe='/')}:/content"
        )

    def download_snapshot(self, dest: Path) -> bool:
        access_token = self._access_token()
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            response = request_with_auth(
                "GET",
                self._item_url(SNAPSHOT_FILENAME),
                access_token=access_token,
                retry_on_unauthorized=self._retry_token,
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
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
            request_with_auth(
                "PUT",
                self._item_url(filename),
                access_token=access_token,
                content=path.read_bytes(),
                headers={"Content-Type": "application/octet-stream"},
                retry_on_unauthorized=self._retry_token,
            )
