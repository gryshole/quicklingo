from __future__ import annotations

import time
from urllib.parse import urlencode

import httpx

from quicklingo.sync.oauth.tokens import OAuthTokens

AUTH_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
USERINFO_URL = "https://graph.microsoft.com/v1.0/me"
SCOPES = ("Files.ReadWrite.AppFolder", "offline_access", "User.Read")


def build_authorize_url(*, client_id: str, redirect_uri: str, state: str, code_verifier: str) -> str:
    from quicklingo.sync.oauth.pkce import code_challenge

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "state": state,
        "code_challenge": code_challenge(code_verifier),
        "code_challenge_method": "S256",
        "response_mode": "query",
    }
    return f"{AUTH_URL}?{urlencode(params)}"


def exchange_code(
    *,
    client_id: str,
    redirect_uri: str,
    code: str,
    code_verifier: str,
) -> OAuthTokens:
    data = {
        "client_id": client_id,
        "code": code,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
        "code_verifier": code_verifier,
    }
    response = httpx.post(TOKEN_URL, data=data, timeout=60.0)
    response.raise_for_status()
    return _tokens_from_response(response.json())


def refresh_tokens(*, client_id: str, refresh_token: str) -> OAuthTokens:
    data = {
        "client_id": client_id,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
        "scope": " ".join(SCOPES),
    }
    response = httpx.post(TOKEN_URL, data=data, timeout=60.0)
    response.raise_for_status()
    tokens = _tokens_from_response(response.json())
    if not tokens.refresh_token:
        tokens.refresh_token = refresh_token
    return tokens


def fetch_account_label(access_token: str) -> str:
    response = httpx.get(
        USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30.0,
    )
    response.raise_for_status()
    data = response.json()
    return str(data.get("userPrincipalName") or data.get("mail") or data.get("displayName") or "")


def _tokens_from_response(data: dict[str, object]) -> OAuthTokens:
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
