#!/usr/bin/env python3
"""L2 characterization tests for Auth/Password-Reset (docs/features/draft/auth-reset.md).

Same conventions as test_tickets.py -- see that file's docstring.

Usage:
  TICKETD_BASE_URL=http://127.0.0.1:5056 python3 -m unittest verification/characterization/test_auth_reset.py -v
"""
import json
import os
import sqlite3
import unittest
import urllib.error
import urllib.request

BASE_URL = os.environ.get("TICKETD_BASE_URL", "http://127.0.0.1:5056")
# Only used by test_confirm_valid_token, which needs to read a token that isn't in any HTTP
# response body by design (non-disclosure). Optional: skips gracefully if not set, since modern/
# may not expose its DB the same way (this is legacy-only plumbing, not part of the spec).
DB_PATH = os.environ.get("TICKETD_DB_PATH")


def request(method, path, body=None, headers=None):
    url = BASE_URL + path
    data = json.dumps(body).encode() if body is not None else None
    h = dict(headers or {})
    if data is not None:
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


class AuthResetCharacterization(unittest.TestCase):

    def test_request_always_ok_even_for_unknown_email(self):
        # docs/features/draft/auth-reset.md: no `users` lookup happens in this flow at all
        status, body = request("POST", "/api/auth/reset",
                                {"email": "definitely-not-a-real-user@example.invalid"})
        self.assertEqual(status, 200)
        self.assertEqual(body, {"ok": True})

    def test_confirm_bogus_token_returns_invalid_token(self):
        status, body = request("POST", "/api/auth/reset/confirm", {"token": "not-a-real-token"})
        self.assertEqual(status, 403)
        self.assertEqual(body, {"error": "invalid_token"})

    def test_rate_limit_after_three_requests(self):
        email = "characterization-ratelimit@example.internal"
        for _ in range(3):
            status, _ = request("POST", "/api/auth/reset", {"email": email})
            self.assertEqual(status, 200)
        status, body = request("POST", "/api/auth/reset", {"email": email})
        self.assertEqual(status, 429)
        self.assertEqual(body, {"error": "rate_limited"})

    def test_bypass_header_skips_rate_limit(self):
        # docs/open-questions.md#OQ-007: undocumented, but real and evidenced -- FIXED behavior
        # until a human rules otherwise.
        email = "characterization-bypass@example.internal"
        for _ in range(4):
            status, _ = request("POST", "/api/auth/reset", {"email": email})
        # 4th above should have been rate-limited; bypass header must still succeed:
        status, body = request("POST", "/api/auth/reset", {"email": email},
                                headers={"X-Internal-Bypass": "1"})
        self.assertEqual(status, 200)
        self.assertEqual(body, {"ok": True})

    @unittest.skipUnless(DB_PATH, "set TICKETD_DB_PATH to exercise the full request->confirm flow")
    def test_confirm_valid_token_consumes_it(self):
        email = "characterization-confirm@example.internal"
        status, _ = request("POST", "/api/auth/reset", {"email": email})
        self.assertEqual(status, 200)
        conn = sqlite3.connect(DB_PATH)
        token = conn.execute(
            "SELECT token FROM reset_tokens WHERE email = ? ORDER BY created_ts DESC LIMIT 1",
            (email,)).fetchone()[0]
        conn.close()

        status, body = request("POST", "/api/auth/reset/confirm", {"token": token})
        self.assertEqual(status, 200)
        self.assertEqual(body, {"ok": True, "email": email})

        # single-use: same token again must fail
        status, body = request("POST", "/api/auth/reset/confirm", {"token": token})
        self.assertEqual(status, 403)
        self.assertEqual(body, {"error": "invalid_token"})


if __name__ == "__main__":
    unittest.main()
