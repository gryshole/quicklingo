import unittest

from quicklingo.sync.oauth.pkce import code_challenge, generate_code_verifier, generate_state


class PkceTests(unittest.TestCase):
    def test_code_challenge_is_stable(self) -> None:
        verifier = "test-verifier-value"
        self.assertEqual(code_challenge(verifier), code_challenge(verifier))

    def test_generated_values_are_unique(self) -> None:
        self.assertNotEqual(generate_code_verifier(), generate_code_verifier())
        self.assertNotEqual(generate_state(), generate_state())


if __name__ == "__main__":
    unittest.main()
