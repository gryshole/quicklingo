from __future__ import annotations

import time
from urllib.parse import urlencode

import httpx

from quicklingo.sync.oauth.pkce import code_challenge, generate_code_verifier, generate_state
from quicklingo.sync.oauth.tokens import OAuthTokens

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
DRIVE_APPDATA_SCOPE = "https://www.googleapis.com/auth/drive.appdata"
SCOPES = (
    "openid",
    "email",
    DRIVE_APPDATA_SCOPE,
)

SCOPE_NOT_GRANTED_MESSAGE = (
    "Google did not grant Drive app data access. In Google Cloud Console open "
    "APIs & Services → OAuth consent screen → Scopes, add "
    "https://www.googleapis.com/auth/drive.appdata, save, then Disconnect and "
    "Connect again in QuickLingo."
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
    payload = response.json()
    _ensure_drive_appdata_scope(payload)
    return _tokens_from_response(payload)


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
    payload = response.json()
    _ensure_drive_appdata_scope(payload)
    tokens = _tokens_from_response(payload)
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


def _ensure_drive_appdata_scope(data: dict[str, object]) -> None:
    scope = str(data.get("scope", "") or "")
    if scope and DRIVE_APPDATA_SCOPE in scope.split():
        return
    access_token = str(data.get("access_token", "") or "")
    if access_token and _tokeninfo_has_drive_appdata(access_token):
        return
    raise ValueError(SCOPE_NOT_GRANTED_MESSAGE)


def _tokeninfo_has_drive_appdata(access_token: str) -> bool:
    try:
        response = httpx.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"access_token": access_token},
            timeout=30.0,
        )
        response.raise_for_status()
        scope = str(response.json().get("scope", "") or "")
    except httpx.HTTPError:
        return False
    return DRIVE_APPDATA_SCOPE in scope.split()


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
