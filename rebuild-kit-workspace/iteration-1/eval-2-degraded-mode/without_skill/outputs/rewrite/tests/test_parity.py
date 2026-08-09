"""Black-box characterization tests for the ticketd wire contract.

Run the SAME suite against legacy and the rewrite; both must pass:

    # terminal 1: legacy            # terminal 1': rewrite
    cd ticketd && python -m app.server       uvicorn app.main:app --port 5001

    TICKETD_BASE_URL=http://127.0.0.1:5000 pytest rewrite/tests -v   # legacy
    TICKETD_BASE_URL=http://127.0.0.1:5001 pytest rewrite/tests -v   # rewrite

Notes:
- Tests MUTATE the target database. Disposable environments only.
- Email side effects are not asserted here (needs a mailcatcher; legacy will 500 on
  close if SMTP is unreachable — that itself is quirk Q10, see the xfail-style
  handling in test_close_*).
- Quirk numbers reference rewrite/inventory/behavior-inventory.md.
- Deliberate non-assertions: token format (changes under ADR-002), timestamp
  sub-second precision, 404 body shape for non-integer ids (ADR-003 divergences).
"""
import os
import time
import uuid

import httpx
import pytest

BASE = os.environ.get("TICKETD_BASE_URL")

pytestmark = pytest.mark.skipif(
    not BASE, reason="set TICKETD_BASE_URL to a disposable ticketd instance")


@pytest.fixture(scope="module")
def client():
    with httpx.Client(base_url=BASE, timeout=40) as c:  # 40 > legacy's 30s SMTP block
        yield c


def _post_retrying_lock_500(client, url, **kw):
    """Legacy defect L1 (see behavior-inventory.md): after any 500-producing write,
    a leaked sqlite connection can hold a lock until GC, making unrelated writes 500
    with 'database is locked' for a while. Retry so the suite characterizes the
    contract, not the flake. Harmless against the rewrite (no such failure mode)."""
    for _ in range(5):
        r = client.post(url, **kw)
        if r.status_code != 500:
            return r
        time.sleep(1.5)
    return r


def make_ticket(client, title=None, **extra):
    title = title or f"parity {uuid.uuid4()}"
    r = _post_retrying_lock_500(client, "/api/tickets", json={"title": title, **extra})
    assert r.status_code == 201
    return r.json(), title


# --- POST /api/tickets ------------------------------------------------------

def test_create_returns_id_and_slug(client):
    body, title = make_ticket(client)
    assert set(body) == {"id", "slug"}
    assert isinstance(body["id"], int)


def test_create_missing_title_422_legacy_error_shape(client):  # Q3
    r = client.post("/api/tickets", json={})
    assert r.status_code == 422
    assert r.json() == {"error": "title_required"}


def test_create_whitespace_title_rejected(client):
    r = client.post("/api/tickets", json={"title": "   "})
    assert r.status_code == 422
    assert r.json() == {"error": "title_required"}


def test_create_malformed_json_treated_as_empty(client):  # Q5
    r = client.post("/api/tickets", content=b"not json{{",
                    headers={"Content-Type": "application/json"})
    assert r.status_code == 422
    assert r.json() == {"error": "title_required"}


@pytest.mark.parametrize("sent,stored", [
    (1, "low"), (2, "med"), (3, "high"),
    ("1", "low"), ("2", "med"), ("3", "high"),
    ("high", "high"), (None, "med"),
])
def test_priority_coercion(client, sent, stored):  # Q6
    extra = {} if sent is None else {"priority": sent}
    body, _ = make_ticket(client, **extra)
    got = client.get(f"/api/tickets/{body['id']}").json()
    assert got["priority"] == stored


def test_slug_collisions_allowed(client):  # Q7
    b1, _ = make_ticket(client, title="Fix DB zz9parity")
    b2, _ = make_ticket(client, title="fix db zz9parity!")
    assert b1["slug"] == b2["slug"]
    assert b1["id"] != b2["id"]


# --- GET /api/tickets -------------------------------------------------------

def test_list_full_row_shape_includes_assignee(client):  # Q2 column, Q4 no pagination
    make_ticket(client)
    r = client.get("/api/tickets")
    assert r.status_code == 200
    rows = r.json()
    assert isinstance(rows, list) and rows
    assert set(rows[0]) == {"id", "title", "slug", "priority", "status",
                            "assignee_id", "created_at", "closed_at"}


def test_list_status_filter(client):
    body, _ = make_ticket(client)
    open_ids = {t["id"] for t in client.get("/api/tickets",
                                            params={"status": "open"}).json()}
    closed_ids = {t["id"] for t in client.get("/api/tickets",
                                              params={"status": "closed"}).json()}
    assert body["id"] in open_ids
    assert body["id"] not in closed_ids


def test_list_ordered_created_at_desc(client):
    rows = client.get("/api/tickets").json()
    created = [t["created_at"] for t in rows]
    assert created == sorted(created, reverse=True)


# --- GET /api/tickets/{id} --------------------------------------------------

def test_get_missing_is_200_empty_object(client):  # Q8 — THE load-bearing quirk
    r = client.get("/api/tickets/99999999")
    assert r.status_code == 200
    assert r.json() == {}


def test_get_non_integer_id_is_404(client):  # status-only parity (ADR-003)
    assert client.get("/api/tickets/abc").status_code == 404


# --- POST /api/tickets/{id}/close ------------------------------------------

def _close(client, tid):
    r = client.post(f"/api/tickets/{tid}/close")
    if r.status_code == 500:
        # Legacy quirk Q10: close commits, then SMTP fails -> 500 with the ticket
        # already closed. Tolerated for legacy runs without an SMTP server; the
        # rewrite must never hit this branch.
        pytest.xfail("legacy Q10: SMTP failure after commit (run a mailcatcher "
                     "for full parity)")
    return r


def test_close_open_ticket(client):
    body, _ = make_ticket(client)
    r = _close(client, body["id"])
    assert r.status_code == 200
    assert r.json() == {"closed": True}
    got = client.get(f"/api/tickets/{body['id']}").json()
    assert got["status"] == "closed"
    assert got["closed_at"] is not None


def test_close_twice_reports_false(client):  # Q9
    body, _ = make_ticket(client)
    _close(client, body["id"])
    r = client.post(f"/api/tickets/{body['id']}/close")
    assert r.status_code == 200
    assert r.json() == {"closed": False}


def test_close_missing_ticket_reports_false_not_404(client):  # Q9
    # No email is possible here (nothing closes), so any 500 is legacy defect L1;
    # safe to retry.
    r = _post_retrying_lock_500(client, "/api/tickets/99999999/close")
    assert r.status_code == 200
    assert r.json() == {"closed": False}


# --- password reset ---------------------------------------------------------

def _reset(client, email, **kw):
    r = client.post("/api/auth/reset", json={"email": email}, **kw)
    if r.status_code == 500:
        pytest.xfail("legacy: synchronous reset email failed (SMTP unreachable); "
                     "run a mailcatcher for full parity")
    return r


def test_reset_ok_for_any_email(client):
    r = _reset(client, f"nobody-{uuid.uuid4()}@example.internal")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_reset_rate_limit_3_per_hour_per_email(client):
    email = f"rl-{uuid.uuid4()}@example.internal"
    for _ in range(3):
        assert _reset(client, email).status_code == 200
    r = client.post("/api/auth/reset", json={"email": email})
    assert r.status_code == 429
    assert r.json() == {"error": "rate_limited"}


def test_reset_bypass_header(client):
    """Q11: legacy honors X-Internal-Bypass: 1 unconditionally; the rewrite defaults
    it OFF (ADR-002). Passes against legacy, and against the rewrite only with
    TICKETD_ALLOW_INTERNAL_BYPASS=true — an intentional, recorded divergence."""
    if os.environ.get("PARITY_EXPECT_BYPASS_DISABLED") == "1":
        pytest.skip("target configured with bypass disabled (rewrite default)")
    email = f"bp-{uuid.uuid4()}@example.internal"
    for _ in range(3):
        assert _reset(client, email).status_code == 200
    r = client.post("/api/auth/reset", json={"email": email},
                    headers={"X-Internal-Bypass": "1"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_confirm_invalid_token_403_same_body(client):  # Q12
    r = client.post("/api/auth/reset/confirm", json={"token": "definitely-wrong"})
    assert r.status_code == 403
    assert r.json() == {"error": "invalid_token"}


def test_confirm_empty_body_403(client):  # Q5 + Q12
    r = client.post("/api/auth/reset/confirm",
                    content=b"", headers={"Content-Type": "application/json"})
    assert r.status_code == 403
    assert r.json() == {"error": "invalid_token"}


# NOTE on the happy confirm path: it requires reading the token out of the reset
# email, so it needs a mailcatcher in the loop. Contract to assert once wired up:
#   200 {"ok": true, "email": <requested email>} ; second confirm with the same
#   token -> 403 {"error": "invalid_token"} (single use).


# --- CSV export -------------------------------------------------------------

def test_csv_export_header_and_content_type(client):
    r = client.get("/internal/export/csv")
    if r.status_code == 404:
        pytest.skip("target has ENABLE_LEGACY_CSV_EXPORT=false")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert r.text.splitlines()[0] == "id,title,status"


def test_csv_export_comma_corruption_preserved(client):
    """The comma bug is part of the byte contract until intake A1 says the endpoint
    is dead (ADR-003)."""
    marker = f"a,b {uuid.uuid4().hex[:8]}"
    body, _ = make_ticket(client, title=marker)
    r = client.get("/internal/export/csv")
    if r.status_code == 404:
        pytest.skip("target has ENABLE_LEGACY_CSV_EXPORT=false")
    line = next(l for l in r.text.splitlines()
                if l.startswith(f"{body['id']},"))
    assert line == f"{body['id']},{marker},open"  # unquoted comma: 4 naive fields


# --- deliberately LAST -------------------------------------------------------

def test_invalid_priority_is_500(client):  # Q6: de facto contract via CHECK constraint
    """Runs last: against legacy, the IntegrityError this provokes leaks a locked
    sqlite connection (defect L1) that can 500 subsequent writes until GC."""
    r = client.post("/api/tickets", json={"title": f"bad prio {uuid.uuid4()}",
                                          "priority": "urgent"})
    assert r.status_code == 500
