import unittest
from unittest.mock import patch

import httpx

from quicklingo.sync.oauth.providers import google as google_oauth


class GoogleOAuthProviderTests(unittest.TestCase):
    def test_scopes_include_email_for_userinfo(self) -> None:
        self.assertIn("openid", google_oauth.SCOPES)
        self.assertIn("email", google_oauth.SCOPES)
        self.assertIn("https://www.googleapis.com/auth/drive.appdata", google_oauth.SCOPES)

    def test_fetch_account_label_returns_empty_on_http_error(self) -> None:
        with patch(
            "quicklingo.sync.oauth.providers.google.httpx.get",
            side_effect=httpx.HTTPError("unauthorized"),
        ):
            self.assertEqual(google_oauth.fetch_account_label("token"), "")


if __name__ == "__main__":
    unittest.main()
