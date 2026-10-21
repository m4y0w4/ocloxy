import io
import json
import os
import unittest
from unittest.mock import patch

import ocloxy


def body(messages):
    return json.dumps({"messages": messages}).encode("utf-8")


class DerivedSessionTests(unittest.TestCase):
    def setUp(self):
        self.old_mode = ocloxy.SESSION_MODE
        self.old_include_system = ocloxy.SESSION_DERIVE_INCLUDE_SYSTEM
        self.old_session = ocloxy.SESSION
        ocloxy.SESSION_MODE = "derive"
        ocloxy.SESSION_DERIVE_INCLUDE_SYSTEM = True
        ocloxy.SESSION = "fallback-session"

    def tearDown(self):
        ocloxy.SESSION_MODE = self.old_mode
        ocloxy.SESSION_DERIVE_INCLUDE_SYSTEM = self.old_include_system
        ocloxy.SESSION = self.old_session

    def test_same_opening_is_stable_across_turns(self):
        first = body([
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Plan a trip."},
        ])
        later = body([
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Plan a trip."},
            {"role": "assistant", "content": "Where to?"},
            {"role": "user", "content": "Lisbon."},
        ])
        self.assertEqual(
            ocloxy._derive_session(first),
            ocloxy._derive_session(later),
        )

    def test_different_first_user_message_changes_id(self):
        one = body([{"role": "user", "content": "Plan a trip."}])
        two = body([{"role": "user", "content": "Plan a meal."}])
        self.assertNotEqual(
            ocloxy._derive_session(one),
            ocloxy._derive_session(two),
        )

    def test_system_and_developer_messages_contribute(self):
        one = body([
            {"role": "system", "content": "System A"},
            {"role": "developer", "content": "Developer A"},
            {"role": "user", "content": "Hello"},
        ])
        two = body([
            {"role": "system", "content": "System B"},
            {"role": "developer", "content": "Developer A"},
            {"role": "user", "content": "Hello"},
        ])
        self.assertNotEqual(
            ocloxy._derive_session(one),
            ocloxy._derive_session(two),
        )

    def test_system_can_be_excluded(self):
        ocloxy.SESSION_DERIVE_INCLUDE_SYSTEM = False
        one = body([
            {"role": "system", "content": "System A"},
            {"role": "user", "content": "Hello"},
        ])
        two = body([
            {"role": "system", "content": "System B"},
            {"role": "user", "content": "Hello"},
        ])
        self.assertEqual(
            ocloxy._derive_session(one),
            ocloxy._derive_session(two),
        )

    def test_text_parts_are_supported(self):
        message = body([{
            "role": "user",
            "content": [
                {"type": "text", "text": "Hello "},
                {"type": "text", "text": "world"},
            ],
        }])
        expected = body([{"role": "user", "content": "Hello \nworld"}])
        self.assertEqual(
            ocloxy._derive_session(message),
            ocloxy._derive_session(expected),
        )

    def test_invalid_body_falls_back(self):
        self.assertEqual(
            ocloxy._session_for_request(b"not-json"),
            "fallback-session",
        )

    def test_no_messages_falls_back(self):
        self.assertEqual(
            ocloxy._session_for_request(b'{"model": "x"}'),
            "fallback-session",
        )

    def test_image_only_message_falls_back(self):
        payload = body([{
            "role": "user",
            "content": [{"type": "image_url", "image_url": {"url": "x"}}],
        }])
        self.assertEqual(
            ocloxy._session_for_request(payload),
            "fallback-session",
        )

    def test_fixed_mode_uses_fallback(self):
        ocloxy.SESSION_MODE = "fixed"
        payload = body([{"role": "user", "content": "Hello"}])
        self.assertEqual(
            ocloxy._session_for_request(payload),
            "fallback-session",
        )

    def test_derived_id_format(self):
        session = ocloxy._derive_session(
            body([{"role": "user", "content": "Hello"}])
        )
        self.assertIsNotNone(session)
        self.assertTrue(session.startswith("ocloxy-"))
        self.assertEqual(len(session), 39)


class ConfigTests(unittest.TestCase):
    def load(self, **env):
        with patch.dict(os.environ, env, clear=True):
            return ocloxy._load_config()

    def test_defaults_are_valid(self):
        config = self.load()
        self.assertEqual(config["upstream"], "https://opencode.ai")
        self.assertEqual(config["host"], "127.0.0.1")
        self.assertEqual(config["port"], 47123)
        self.assertEqual(config["session"], "ocloxy-local")
        self.assertEqual(config["session_mode"], "fixed")
        self.assertEqual(config["max_body_bytes"], 16 * 1024 * 1024)
        self.assertEqual(config["allowed_prefixes"], ("/inference/", "/zen/"))

    def test_version_is_early_release(self):
        self.assertEqual(ocloxy.__version__, "0.1.0")

    def test_non_loopback_host_is_rejected(self):
        with self.assertRaises(ocloxy.ConfigError):
            self.load(LISTEN_HOST="0.0.0.0")

    def test_remote_plain_http_upstream_is_rejected(self):
        with self.assertRaises(ocloxy.ConfigError):
            self.load(UPSTREAM_BASE="http://example.com")

    def test_loopback_plain_http_upstream_is_allowed(self):
        config = self.load(UPSTREAM_BASE="http://127.0.0.1:1234")
        self.assertEqual(config["upstream"], "http://127.0.0.1:1234")

    def test_upstream_with_credentials_is_rejected(self):
        with self.assertRaises(ocloxy.ConfigError):
            self.load(UPSTREAM_BASE="https://user:pass@example.com")

    def test_invalid_port_is_rejected(self):
        with self.assertRaises(ocloxy.ConfigError):
            self.load(LISTEN_PORT="not-a-port")

    def test_invalid_session_mode_is_rejected(self):
        with self.assertRaises(ocloxy.ConfigError):
            self.load(SESSION_MODE="sometimes")

    def test_invalid_boolean_is_rejected(self):
        with self.assertRaises(ocloxy.ConfigError):
            self.load(SESSION_DERIVE_INCLUDE_SYSTEM="maybe")

    def test_root_prefix_is_rejected(self):
        with self.assertRaises(ocloxy.ConfigError):
            self.load(ALLOWED_PREFIXES="/")

    def test_prefix_traversal_is_rejected(self):
        with self.assertRaises(ocloxy.ConfigError):
            self.load(ALLOWED_PREFIXES="/inference/../zen/")


class PathTests(unittest.TestCase):
    def test_normal_path_is_kept(self):
        self.assertEqual(
            ocloxy._normalize_path("/inference/go/v1/chat/completions"),
            "/inference/go/v1/chat/completions",
        )

    def test_redundant_segments_are_normalized(self):
        self.assertEqual(
            ocloxy._normalize_path("/inference//go/./v1"),
            "/inference/go/v1",
        )

    def test_traversal_is_rejected(self):
        with self.assertRaises(ValueError):
            ocloxy._normalize_path("/inference/../zen/chat")

    def test_encoded_traversal_is_rejected(self):
        with self.assertRaises(ValueError):
            ocloxy._normalize_path("/inference/%2e%2e/zen/chat")

    def test_null_byte_is_rejected(self):
        with self.assertRaises(ValueError):
            ocloxy._normalize_path("/inference/%00")

    def test_backslash_is_rejected(self):
        with self.assertRaises(ValueError):
            ocloxy._normalize_path("/inference\\go")

    def test_relative_path_is_rejected(self):
        with self.assertRaises(ValueError):
            ocloxy._normalize_path("inference/go")


class FakeRequest:
    _read_chunked_body = ocloxy.Handler._read_chunked_body
    _read_request_body = ocloxy.Handler._read_request_body

    def __init__(self, headers, body=b""):
        self.headers = headers
        self.rfile = io.BytesIO(body)


class BodyTests(unittest.TestCase):
    def setUp(self):
        self.old_max_body = ocloxy.MAX_BODY_BYTES

    def tearDown(self):
        ocloxy.MAX_BODY_BYTES = self.old_max_body

    def read(self, headers, body=b""):
        return FakeRequest(headers, body)._read_request_body()

    def test_content_length_body(self):
        self.assertEqual(
            self.read({"Content-Length": "5"}, b"hello"),
            b"hello",
        )

    def test_missing_length_is_empty(self):
        self.assertEqual(self.read({}), b"")

    def test_invalid_length_is_rejected(self):
        with self.assertRaises(ocloxy.InvalidBody):
            self.read({"Content-Length": "nope"})

    def test_negative_length_is_rejected(self):
        with self.assertRaises(ocloxy.InvalidBody):
            self.read({"Content-Length": "-1"})

    def test_early_end_is_rejected(self):
        with self.assertRaises(ocloxy.InvalidBody):
            self.read({"Content-Length": "5"}, b"hi")

    def test_oversized_body_is_rejected(self):
        ocloxy.MAX_BODY_BYTES = 4
        with self.assertRaises(ocloxy.BodyTooLarge):
            self.read({"Content-Length": "5"}, b"hello")

    def test_ambiguous_framing_is_rejected(self):
        with self.assertRaises(ocloxy.InvalidBody):
            self.read(
                {"Content-Length": "5", "Transfer-Encoding": "chunked"},
                b"hello",
            )

    def test_unsupported_transfer_encoding_is_rejected(self):
        with self.assertRaises(ocloxy.InvalidBody):
            self.read({"Transfer-Encoding": "gzip"})

    def test_chunked_body_is_decoded(self):
        self.assertEqual(
            self.read(
                {"Transfer-Encoding": "chunked"},
                b"5\r\nhello\r\n0\r\n\r\n",
            ),
            b"hello",
        )

    def test_oversized_chunked_body_is_rejected(self):
        ocloxy.MAX_BODY_BYTES = 4
        with self.assertRaises(ocloxy.BodyTooLarge):
            self.read(
                {"Transfer-Encoding": "chunked"},
                b"5\r\nhello\r\n0\r\n\r\n",
            )

    def test_malformed_chunk_is_rejected(self):
        with self.assertRaises(ocloxy.InvalidBody):
            self.read(
                {"Transfer-Encoding": "chunked"},
                b"zz\r\nhello\r\n0\r\n\r\n",
            )


if __name__ == "__main__":
    unittest.main()
