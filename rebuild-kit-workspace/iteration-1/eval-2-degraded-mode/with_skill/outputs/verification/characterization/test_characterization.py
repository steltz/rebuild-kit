"""L2 characterization suite — fast, modern-only (no legacy boot; goldens are the oracle).

Run: MODERN_BASE_URL=http://127.0.0.1:5002 python3 -m pytest test_characterization.py -q
     (boot modern via ../harness/run-modern.sh first; fresh seed per session)

Grouped per feature so work orders can reference their slice:
  WO-003 → TestCreateTicket   WO-002 → TestListGet   WO-005 → TestCloseTicket
  WO-006 → TestResetFlow      WO-007 → TestExportCsv (skipped while OQ-001 is open)

Expectations are derived from the golden traces (../replay/traces/core.legacy.jsonl) with
expected-divergence adjustments applied inline (ED-004a/b: 500→422 bodies). Email/state
assertions live in L3 (diff-run.sh), not here.
"""
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

import pytest

BASE = os.environ.get("MODERN_BASE_URL")
GOLDENS = {t["id"]: t for t in (
    json.loads(l) for l in
    (Path(__file__).parent / ".." / "replay" / "traces" / "core.legacy.jsonl")
    .read_text().splitlines() if l.strip())}

pytestmark = pytest.mark.skipif(not BASE, reason="MODERN_BASE_URL not set")


def call(method, path, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    h = dict(headers or {})
    if data:
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, headers=h, method=method)
    try:
        r = urllib.request.urlopen(req, timeout=10)
        return r.status, json.loads(r.read()) if "json" in r.headers.get("Content-Type", "") else r.read().decode()
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, None


class TestCreateTicket:  # WO-003
    def test_priority_alias_string(self):
        s, b = call("POST", "/api/tickets", {"title": "alias str", "priority": "2"})
        assert s == 201 and set(b) == {"id", "slug"}

    def test_priority_alias_int(self):
        s, b = call("POST", "/api/tickets", {"title": "alias int", "priority": 3})
        assert s == 201

    def test_extra_fields_ignored(self):
        s, _ = call("POST", "/api/tickets", {"title": "extra ok", "bogus_field": 1})
        assert s == 201

    def test_slug_derivation_matches_legacy(self):
        s, b = call("POST", "/api/tickets", {"title": "  Fix DB!!  NOW  "})
        assert s == 201 and b["slug"] == "fix-db-now"

    def test_symbol_only_title_empty_slug(self):
        s, b = call("POST", "/api/tickets", {"title": "!!!"})
        assert s == 201 and b["slug"] == ""

    def test_missing_title_422(self):
        s, b = call("POST", "/api/tickets", {"priority": "high"})
        assert (s, b) == (422, {"error": "title_required"})

    def test_blank_title_422(self):
        s, b = call("POST", "/api/tickets", {"title": "   "})
        assert (s, b) == (422, {"error": "title_required"})

    def test_bad_priority_422_ed004a(self):  # legacy 500s; sanctioned FREE deviation
        s, b = call("POST", "/api/tickets", {"title": "x", "priority": "urgent"})
        assert (s, b) == (422, {"error": "priority_invalid"})

    def test_nonstring_title_422_ed004b(self):  # legacy 500s; sanctioned FREE deviation
        s, b = call("POST", "/api/tickets", {"title": 123})
        assert (s, b) == (422, {"error": "title_invalid"})


class TestListGet:  # WO-002
    def test_missing_ticket_is_200_empty_object(self):  # the load-bearing quirk
        s, b = call("GET", "/api/tickets/99999")
        assert (s, b) == (200, {})

    def test_list_returns_full_rows_newest_first(self):
        call("POST", "/api/tickets", {"title": "older"})
        call("POST", "/api/tickets", {"title": "newer"})
        s, b = call("GET", "/api/tickets")
        assert s == 200 and isinstance(b, list)
        assert set(b[0]) == {"id", "title", "slug", "priority", "status",
                             "assignee_id", "created_at", "closed_at"}
        titles = [t["title"] for t in b]
        assert titles.index("newer") < titles.index("older")

    def test_bogus_status_filter_empty_200(self):
        s, b = call("GET", "/api/tickets?status=bogus")
        assert (s, b) == (200, [])

    def test_empty_status_filter_disables_filter(self):  # audit A-03
        call("POST", "/api/tickets", {"title": "empty-status probe"})
        s, b = call("GET", "/api/tickets?status=")
        assert s == 200 and any(t["title"] == "empty-status probe" for t in b)


class TestCloseTicket:  # WO-005
    def test_close_then_close_again(self):
        _, created = call("POST", "/api/tickets", {"title": "to close"})
        s1, b1 = call("POST", f"/api/tickets/{created['id']}/close")
        s2, b2 = call("POST", f"/api/tickets/{created['id']}/close")
        assert (s1, b1) == (200, {"closed": True})
        assert (s2, b2) == (200, {"closed": False})

    def test_close_missing_id_no_404(self):
        s, b = call("POST", "/api/tickets/99999/close")
        assert (s, b) == (200, {"closed": False})


class TestResetFlow:  # WO-006
    def test_unknown_email_still_ok(self):
        s, b = call("POST", "/api/auth/reset", {"email": "ghost@nowhere.example"})
        assert (s, b) == (200, {"ok": True})

    def test_rate_limit_third_ok_fourth_429(self):
        email = "rl-probe@example.internal"
        for _ in range(3):
            s, b = call("POST", "/api/auth/reset", {"email": email})
            assert (s, b) == (200, {"ok": True})
        s, b = call("POST", "/api/auth/reset", {"email": email})
        assert (s, b) == (429, {"error": "rate_limited"})

    def test_confirm_refunds_rate_limit(self):  # audit A-01: count is over SURVIVING rows
        email = "refund-l2@example.internal"
        for _ in range(3):
            assert call("POST", "/api/auth/reset", {"email": email})[0] == 200
        # fetch the issued tokens via the harness seam and confirm one
        import urllib.request as _u
        events = json.loads(_u.urlopen(BASE + "/__harness__/emails", timeout=10).read())
        tok = next(e["data"].split("reset token: ", 1)[1].split()[0]
                   for e in reversed(events) if email in str(e.get("to")))
        assert call("POST", "/api/auth/reset/confirm", {"token": tok})[0] == 200
        s, b = call("POST", "/api/auth/reset", {"email": email})
        assert (s, b) == (200, {"ok": True})  # quota freed by the confirm
        s, _ = call("POST", "/api/auth/reset", {"email": email})
        assert s == 429  # back at 3 surviving rows

    def test_bypass_header_skips_limit(self):  # parity behavior; OQ-004 pending
        email = "rl-bypass@example.internal"
        for _ in range(3):
            call("POST", "/api/auth/reset", {"email": email})
        s, b = call("POST", "/api/auth/reset", {"email": email},
                    headers={"X-Internal-Bypass": "1"})
        assert (s, b) == (200, {"ok": True})

    def test_unknown_and_expired_tokens_same_403_body(self):  # deliberate non-disclosure
        s1, b1 = call("POST", "/api/auth/reset/confirm",
                      {"token": "ffffffffffffffffffffffffffffffff"})
        s2, b2 = call("POST", "/api/auth/reset/confirm",
                      {"token": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"})  # seeded expired
        assert (s1, b1) == (403, {"error": "invalid_token"})
        assert (s2, b2) == (403, {"error": "invalid_token"})
        assert b1 == b2

    def test_seeded_live_token_confirm_and_single_use(self):
        s, b = call("POST", "/api/auth/reset/confirm",
                    {"token": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"})
        assert (s, b) == (200, {"ok": True, "email": "live-seed@example.internal"})
        s2, b2 = call("POST", "/api/auth/reset/confirm",
                      {"token": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"})
        assert (s2, b2) == (403, {"error": "invalid_token"})


class TestExportCsv:  # WO-007 — blocked on OQ-001
    @pytest.mark.skip(reason="OQ-001 open: port decision pending; enable if ruled live")
    def test_csv_shape(self):
        s, body = call("GET", "/internal/export/csv")
        assert s == 200 and body.splitlines()[0] == "id,title,status"
