from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

import httpx

from quicklingo import settings
from quicklingo.sync.cloud.base import request_with_auth
from quicklingo.sync.models import SNAPSHOT_FILENAME
from quicklingo.sync.oauth.providers import microsoft as microsoft_oauth
from quicklingo.sync.oauth.tokens import OAuthTokens
from quicklingo.sync.transport import OAuthCloudTransport

GRAPH_API = "https://graph.microsoft.com/v1.0"
REMOTE_PREFIX = "QuickLingo"


class OneDriveTransport(OAuthCloudTransport):
    provider_id = "onedrive"

    def _do_refresh(self, current: OAuthTokens) -> OAuthTokens:
        return microsoft_oauth.refresh_tokens(
            client_id=settings.get_sync_onedrive_client_id(),
            refresh_token=current.refresh_token,
        )

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

    def _upload_file(self, filename: str, path: Path, access_token: str) -> None:
        request_with_auth(
            "PUT",
            self._item_url(filename),
            access_token=access_token,
            content=path.read_bytes(),
            headers={"Content-Type": "application/octet-stream"},
            retry_on_unauthorized=self._retry_token,
        )
