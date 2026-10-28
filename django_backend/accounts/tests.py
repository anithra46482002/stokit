import bcrypt
from argon2 import PasswordHasher
from django.test import SimpleTestCase

from .hashers import hash_password, verify_php_password
from .services import new_token, parse_bearer, hash_token


class PasswordCompatibilityTests(SimpleTestCase):
    def test_argon2id_hash_round_trip(self):
        encoded = hash_password("correct horse battery staple")
        self.assertTrue(encoded.startswith("$argon2id$"))
        self.assertTrue(verify_php_password("correct horse battery staple", encoded))
        self.assertFalse(verify_php_password("incorrect", encoded))

    def test_php_bcrypt_2y_hash(self):
        encoded = bcrypt.hashpw(b"legacy-password", bcrypt.gensalt()).decode("ascii")
        encoded = "$2y$" + encoded[4:]
        self.assertTrue(verify_php_password("legacy-password", encoded))
        self.assertFalse(verify_php_password("wrong-password", encoded))

    def test_empty_or_unknown_hash_is_rejected(self):
        self.assertFalse(verify_php_password("anything", ""))
        self.assertFalse(verify_php_password("anything", "unknown-format"))


class LegacyTokenTests(SimpleTestCase):
    def test_new_token_matches_php_shape_and_is_hashed(self):
        token = new_token()
        self.assertEqual(len(token), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in token))
        self.assertNotEqual(token, hash_token(token))

    def test_bearer_parser_is_case_insensitive(self):
        self.assertEqual(parse_bearer("Bearer abc123"), "abc123")
        self.assertEqual(parse_bearer("bEaReR abc123"), "abc123")
        self.assertEqual(parse_bearer("Basic abc123"), "")
        self.assertEqual(parse_bearer(""), "")
