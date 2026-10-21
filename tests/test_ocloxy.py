import json
import unittest

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
        self.assertTrue(session.startswith("osm-"))
        self.assertEqual(len(session), 36)


if __name__ == "__main__":
    unittest.main()
