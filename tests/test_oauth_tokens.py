import time
import unittest

from quicklingo.sync.oauth.tokens import OAuthTokens


class OAuthTokensTests(unittest.TestCase):
    def test_unknown_expiry_with_refresh_token_is_expired(self) -> None:
        tokens = OAuthTokens(
            access_token="access",
            refresh_token="refresh",
            expires_at=0.0,
        )
        self.assertTrue(tokens.is_expired)

    def test_unknown_expiry_without_refresh_token_is_not_expired(self) -> None:
        tokens = OAuthTokens(access_token="access", refresh_token="", expires_at=0.0)
        self.assertFalse(tokens.is_expired)

    def test_future_expiry_is_not_expired(self) -> None:
        tokens = OAuthTokens(
            access_token="access",
            refresh_token="refresh",
            expires_at=time.time() + 3600,
        )
        self.assertFalse(tokens.is_expired)


if __name__ == "__main__":
    unittest.main()
