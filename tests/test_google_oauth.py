import unittest
from unittest.mock import MagicMock, patch

import httpx

from quicklingo.sync.oauth.providers import google as google_oauth


class GoogleOAuthProviderTests(unittest.TestCase):
    def test_scopes_include_email_for_userinfo(self) -> None:
        self.assertIn("openid", google_oauth.SCOPES)
        self.assertIn("email", google_oauth.SCOPES)
        self.assertIn(google_oauth.DRIVE_APPDATA_SCOPE, google_oauth.SCOPES)

    def test_fetch_account_label_returns_empty_on_http_error(self) -> None:
        with patch(
            "quicklingo.sync.oauth.providers.google.httpx.get",
            side_effect=httpx.HTTPError("unauthorized"),
        ):
            self.assertEqual(google_oauth.fetch_account_label("token"), "")

    def test_exchange_code_requires_drive_appdata_scope(self) -> None:
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "access_token": "access",
            "refresh_token": "refresh",
            "expires_in": 3600,
            "scope": "openid email",
        }
        with (
            patch(
                "quicklingo.sync.oauth.providers.google.httpx.post",
                return_value=response,
            ),
            patch(
                "quicklingo.sync.oauth.providers.google._tokeninfo_has_drive_appdata",
                return_value=False,
            ),
        ):
            with self.assertRaises(ValueError) as ctx:
                google_oauth.exchange_code(
                    client_id="id",
                    client_secret="secret",
                    redirect_uri="http://127.0.0.1:1/callback",
                    code="code",
                    code_verifier="verifier",
                )
        self.assertIn("drive.appdata", str(ctx.exception))

    def test_exchange_code_accepts_drive_appdata_scope(self) -> None:
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "access_token": "access",
            "refresh_token": "refresh",
            "expires_in": 3600,
            "scope": (
                "openid email https://www.googleapis.com/auth/drive.appdata"
            ),
        }
        with patch(
            "quicklingo.sync.oauth.providers.google.httpx.post",
            return_value=response,
        ):
            tokens = google_oauth.exchange_code(
                client_id="id",
                client_secret="secret",
                redirect_uri="http://127.0.0.1:1/callback",
                code="code",
                code_verifier="verifier",
            )
        self.assertEqual(tokens.access_token, "access")


if __name__ == "__main__":
    unittest.main()
