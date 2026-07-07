from __future__ import annotations

import json
from typing import Callable

import httpx

from quicklingo.sync.oauth.tokens import OAuthTokens

OAuthProvider = str


def ensure_access_token(
    provider: OAuthProvider,
    tokens: OAuthTokens,
    refresh_fn: Callable[[], OAuthTokens],
    save_fn: Callable[[OAuthTokens], None],
) -> str:
    if not tokens.refresh_token and tokens.is_expired:
        raise ValueError("Not connected")
    if not tokens.is_expired:
        return tokens.access_token
    refreshed = refresh_fn()
    if refreshed.account_label:
        tokens.account_label = refreshed.account_label
    tokens.access_token = refreshed.access_token
    if refreshed.refresh_token:
        tokens.refresh_token = refreshed.refresh_token
    tokens.expires_at = refreshed.expires_at
    tokens.token_type = refreshed.token_type
    save_fn(tokens)
    return tokens.access_token


def auth_headers(access_token: str, token_type: str = "Bearer") -> dict[str, str]:
    return {"Authorization": f"{token_type} {access_token}"}


def request_with_auth(
    method: str,
    url: str,
    *,
    access_token: str,
    token_type: str = "Bearer",
    retry_on_unauthorized: Callable[[], str] | None = None,
    **kwargs: object,
) -> httpx.Response:
    headers = dict(kwargs.pop("headers", {}) or {})
    headers.update(auth_headers(access_token, token_type))
    response = httpx.request(method, url, headers=headers, timeout=120.0, **kwargs)
    if response.status_code == 401 and retry_on_unauthorized is not None:
        new_token = retry_on_unauthorized()
        headers.update(auth_headers(new_token, token_type))
        response = httpx.request(method, url, headers=headers, timeout=120.0, **kwargs)
    response.raise_for_status()
    return response


def encode_json(data: dict[str, object]) -> bytes:
    return json.dumps(data).encode("utf-8")
