from __future__ import annotations

import webbrowser

from quicklingo import settings
from quicklingo.i18n.translator import TranslatableError
from quicklingo.sync.oauth.loopback import pick_loopback_port, wait_for_oauth_callback
from quicklingo.sync.oauth.pkce import generate_code_verifier, generate_state
from quicklingo.sync.oauth.providers import dropbox as dropbox_oauth
from quicklingo.sync.oauth.providers import google as google_oauth
from quicklingo.sync.oauth.providers import microsoft as microsoft_oauth
from quicklingo.sync.oauth.tokens import OAuthTokens

OAUTH_PROVIDERS = frozenset({"google_drive", "dropbox", "onedrive"})


def connect_provider(provider: str) -> OAuthTokens:
    if provider not in OAUTH_PROVIDERS:
        raise TranslatableError("errors.oauth_unsupported_provider", provider=provider)

    port = pick_loopback_port()
    redirect_uri = f"http://127.0.0.1:{port}/callback"
    state = generate_state()
    verifier = generate_code_verifier()

    if provider == "google_drive":
        client_id = settings.get_sync_google_client_id().strip()
        if not client_id:
            raise TranslatableError("errors.oauth_google_client_id_required")
        url = google_oauth.build_authorize_url(
            client_id=client_id,
            redirect_uri=redirect_uri,
            state=state,
            code_verifier=verifier,
        )
    elif provider == "dropbox":
        app_key = settings.get_sync_dropbox_app_key().strip()
        app_secret = settings.get_sync_dropbox_app_secret().strip()
        if not app_key or not app_secret:
            raise TranslatableError("errors.oauth_dropbox_credentials_required")
        url = dropbox_oauth.build_authorize_url(
            app_key=app_key,
            redirect_uri=redirect_uri,
            state=state,
            code_verifier=verifier,
        )
    else:
        client_id = settings.get_sync_onedrive_client_id().strip()
        if not client_id:
            raise TranslatableError("errors.oauth_onedrive_client_id_required")
        url = microsoft_oauth.build_authorize_url(
            client_id=client_id,
            redirect_uri=redirect_uri,
            state=state,
            code_verifier=verifier,
        )

    if not webbrowser.open(url):
        raise TranslatableError("errors.oauth_browser_open_failed")

    callback = wait_for_oauth_callback(expected_state=state, port=port)
    return _exchange_provider_code(provider, redirect_uri, callback.code, verifier)


def _exchange_provider_code(
    provider: str,
    redirect_uri: str,
    code: str,
    verifier: str,
) -> OAuthTokens:
    if provider == "google_drive":
        tokens = google_oauth.exchange_code(
            client_id=settings.get_sync_google_client_id(),
            client_secret=settings.get_sync_google_client_secret(),
            redirect_uri=redirect_uri,
            code=code,
            code_verifier=verifier,
        )
        tokens.account_label = google_oauth.fetch_account_label(tokens.access_token)
        if not tokens.refresh_token:
            raise TranslatableError("errors.oauth_google_no_refresh_token")
        return tokens
    if provider == "dropbox":
        tokens = dropbox_oauth.exchange_code(
            app_key=settings.get_sync_dropbox_app_key(),
            app_secret=settings.get_sync_dropbox_app_secret(),
            redirect_uri=redirect_uri,
            code=code,
            code_verifier=verifier,
        )
        tokens.account_label = dropbox_oauth.fetch_account_label(tokens.access_token)
        return tokens
    tokens = microsoft_oauth.exchange_code(
        client_id=settings.get_sync_onedrive_client_id(),
        redirect_uri=redirect_uri,
        code=code,
        code_verifier=verifier,
    )
    tokens.account_label = microsoft_oauth.fetch_account_label(tokens.access_token)
    return tokens
