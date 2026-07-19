from __future__ import annotations

import httpx

from quicklingo.sync.oauth.pkce import code_challenge
from quicklingo.sync.oauth.providers._common import build_authorize_url as _build_authorize_url
from quicklingo.sync.oauth.providers._common import tokens_from_response
from quicklingo.sync.oauth.tokens import OAuthTokens

AUTH_URL = "https://www.dropbox.com/oauth2/authorize"
TOKEN_URL = "https://api.dropboxapi.com/oauth2/token"
ACCOUNT_URL = "https://api.dropboxapi.com/2/users/get_current_account"
SCOPES = ("files.content.read", "files.content.write")


def build_authorize_url(*, app_key: str, redirect_uri: str, state: str, code_verifier: str) -> str:
    params = {
        "client_id": app_key,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "token_access_type": "offline",
        "state": state,
        "code_challenge": code_challenge(code_verifier),
        "code_challenge_method": "S256",
    }
    return _build_authorize_url(AUTH_URL, params)


def exchange_code(
    *,
    app_key: str,
    app_secret: str,
    redirect_uri: str,
    code: str,
    code_verifier: str,
) -> OAuthTokens:
    data = {
        "client_id": app_key,
        "client_secret": app_secret,
        "code": code,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
        "code_verifier": code_verifier,
    }
    response = httpx.post(TOKEN_URL, data=data, timeout=60.0)
    response.raise_for_status()
    return tokens_from_response(response.json())


def refresh_tokens(*, app_key: str, app_secret: str, refresh_token: str) -> OAuthTokens:
    data = {
        "client_id": app_key,
        "client_secret": app_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    response = httpx.post(TOKEN_URL, data=data, timeout=60.0)
    response.raise_for_status()
    tokens = tokens_from_response(response.json())
    if not tokens.refresh_token:
        tokens.refresh_token = refresh_token
    return tokens


def fetch_account_label(access_token: str) -> str:
    response = httpx.post(
        ACCOUNT_URL,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        content="null",
        timeout=30.0,
    )
    response.raise_for_status()
    data = response.json()
    account = data.get("email")
    if account:
        return str(account)
    name = data.get("name", {})
    if isinstance(name, dict):
        return str(name.get("display_name") or "")
    return ""
