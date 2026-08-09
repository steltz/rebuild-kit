#!/usr/bin/env python3
"""L2 characterization tests for the Tickets feature (docs/features/draft/tickets-*.md).

Stdlib-only unittest, run against whatever TICKETD_BASE_URL points at (legacy today; modern once
WO-001/WO-002/WO-004 land). This is intentionally faster/lighter than L3 twin-boot replay
(verification/harness/) -- no state diffing, just per-endpoint response-shape assertions against
docs/contracts/fixtures. Fast enough to run on every change; L3 is the ground truth, this is the
everyday check. Point at legacy to confirm the suite itself is correct (self-consistency), same
principle as the harness's own baseline check.

Usage:
  TICKETD_BASE_URL=http://127.0.0.1:5056 python3 -m unittest verification/characterization/test_tickets.py -v
"""
import json
import os
import unittest
import urllib.error
import urllib.request

BASE_URL = os.environ.get("TICKETD_BASE_URL", "http://127.0.0.1:5056")


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


class TicketsCharacterization(unittest.TestCase):
    """Each test cites the draft spec behavior it characterizes."""

    def test_create_requires_title(self):
        # docs/features/draft/tickets-list-create-get.md: title required, 422 on blank
        status, body = request("POST", "/api/tickets", {})
        self.assertEqual(status, 422)
        self.assertEqual(body, {"error": "title_required"})

        status, body = request("POST", "/api/tickets", {"title": "   "})
        self.assertEqual(status, 422, "whitespace-only title must be rejected same as missing")

    def test_create_numeric_priority_coercion(self):
        # "1"/"2"/"3" map to low/med/high -- a real, undocumented client dependency
        # (integration-notes.md: "clients send both, both must keep working")
        status, body = request("POST", "/api/tickets",
                                {"title": "Characterization: numeric priority", "priority": "3"})
        self.assertEqual(status, 201)
        self.assertIn("id", body)
        self.assertIn("slug", body)
        tid = body["id"]
        status, ticket = request("GET", f"/api/tickets/{tid}")
        self.assertEqual(ticket["priority"], "high", "'3' must coerce to 'high'")

    def test_create_default_priority_is_med(self):
        status, body = request("POST", "/api/tickets",
                                {"title": "Characterization: default priority"})
        self.assertEqual(status, 201)
        status, ticket = request("GET", f"/api/tickets/{body['id']}")
        self.assertEqual(ticket["priority"], "med")

    def test_get_missing_ticket_returns_200_empty_object(self):
        # docs/domain/ticket.md: the one behavior explicitly asserted as a caller dependency --
        # NOT a 404. This is the single most important regression to catch.
        status, body = request("GET", "/api/tickets/999999999")
        self.assertEqual(status, 200, "missing ticket must be 200, never 404")
        self.assertEqual(body, {}, "missing ticket body must be an empty object")

    def test_close_is_idempotent(self):
        status, body = request("POST", "/api/tickets",
                                {"title": "Characterization: close idempotency"})
        tid = body["id"]
        status, body = request("POST", f"/api/tickets/{tid}/close")
        self.assertEqual(status, 200)
        self.assertEqual(body, {"closed": True})
        status, body = request("POST", f"/api/tickets/{tid}/close")
        self.assertEqual(body, {"closed": False}, "closing an already-closed ticket is a no-op")

    def test_close_nonexistent_ticket(self):
        status, body = request("POST", "/api/tickets/999999999/close")
        self.assertEqual(status, 200)
        self.assertEqual(body, {"closed": False})

    def test_list_filters_by_exact_status(self):
        status, body = request("GET", "/api/tickets?status=open")
        self.assertEqual(status, 200)
        self.assertTrue(all(t["status"] == "open" for t in body))
        status, body = request("GET", "/api/tickets?status=nonexistent-status")
        self.assertEqual(body, [], "unrecognized status silently returns zero rows, not an error")

    def test_export_csv_shape(self):
        req = urllib.request.Request(BASE_URL + "/internal/export/csv", method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            text = resp.read().decode()
        lines = text.strip().splitlines()
        self.assertEqual(lines[0], "id,title,status")


if __name__ == "__main__":
    unittest.main()
