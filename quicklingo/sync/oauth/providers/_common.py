from __future__ import annotations

import time
from urllib.parse import urlencode

from quicklingo.sync.oauth.tokens import OAuthTokens


def build_authorize_url(auth_url: str, params: dict[str, str]) -> str:
    """Compose an OAuth2 authorization URL from a base endpoint and query params."""
    return f"{auth_url}?{urlencode(params)}"


def tokens_from_response(data: dict[str, object]) -> OAuthTokens:
    """Build OAuthTokens from a token endpoint JSON payload (shared across providers)."""
    expires_in = data.get("expires_in", 0)
    try:
        expires_in = int(expires_in)
    except (TypeError, ValueError):
        expires_in = 0
    return OAuthTokens(
        access_token=str(data.get("access_token", "") or ""),
        refresh_token=str(data.get("refresh_token", "") or ""),
        expires_at=time.time() + expires_in if expires_in else 0.0,
        token_type=str(data.get("token_type", "Bearer") or "Bearer"),
    )
