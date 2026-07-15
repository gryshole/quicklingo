import unittest
from unittest.mock import MagicMock

from quicklingo.sync.cloud.base import format_http_status_error


class SyncHttpErrorTests(unittest.TestCase):
    def test_insufficient_scopes_returns_actionable_message(self) -> None:
        response = MagicMock()
        response.json.return_value = {
            "error": {
                "code": 403,
                "message": "The granted scopes do not give access to all of the requested spaces.",
                "errors": [
                    {
                        "reason": "insufficientScopes",
                        "message": "The granted scopes do not give access to all of the requested spaces.",
                    }
                ],
            }
        }
        message = format_http_status_error(response)
        self.assertIn("drive.appdata", message)


if __name__ == "__main__":
    unittest.main()
