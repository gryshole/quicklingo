import unittest
from unittest.mock import patch

from quicklingo.sync.transport import build_transport


class BuildTransportTests(unittest.TestCase):
    def test_empty_transport_raises(self) -> None:
        with self.assertRaises(ValueError):
            build_transport(transport="")

    def test_invalid_webdav_url_raises(self) -> None:
        with patch("quicklingo.settings.get_sync_webdav_url", return_value="not-a-url"):
            with self.assertRaises(ValueError):
                build_transport(transport="webdav")


if __name__ == "__main__":
    unittest.main()
