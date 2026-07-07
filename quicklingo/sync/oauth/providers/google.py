from __future__ import annotations

import time
from urllib.parse import urlencode

import httpx

from quicklingo.sync.oauth.pkce import code_challenge, generate_code_verifier, generate_state
from quicklingo.sync.oauth.tokens import OAuthTokens

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
SCOPES = (
    "openid",
    "email",
    "https://www.googleapis.com/auth/drive.appdata",
)


def build_authorize_url(*, client_id: str, redirect_uri: str, state: str, code_verifier: str) -> str:
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "state": state,
        "code_challenge": code_challenge(code_verifier),
        "code_challenge_method": "S256",
        "access_type": "offline",
        "prompt": "consent",
    }
    return f"{AUTH_URL}?{urlencode(params)}"


def exchange_code(
    *,
    client_id: str,
    client_secret: str,
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
    if client_secret:
        data["client_secret"] = client_secret
    response = httpx.post(TOKEN_URL, data=data, timeout=60.0)
    response.raise_for_status()
    return _tokens_from_response(response.json())


def refresh_tokens(*, client_id: str, client_secret: str, refresh_token: str) -> OAuthTokens:
    data = {
        "client_id": client_id,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    if client_secret:
        data["client_secret"] = client_secret
    response = httpx.post(TOKEN_URL, data=data, timeout=60.0)
    response.raise_for_status()
    tokens = _tokens_from_response(response.json())
    if not tokens.refresh_token:
        tokens.refresh_token = refresh_token
    return tokens


def fetch_account_label(access_token: str) -> str:
    if not access_token:
        return ""
    try:
        response = httpx.get(
            USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        return str(data.get("email") or data.get("name") or "")
    except httpx.HTTPError:
        return ""


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
