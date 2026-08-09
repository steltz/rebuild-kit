"""
Parity + fix tests for the reset flow. See
docs/01-LEGACY-BEHAVIOR-INVENTORY.md and app/routers/auth.py.
"""
import re

from app.models import NotificationOutbox, ResetToken


def _requested_token(db_session, email):
    outbox_row = db_session.query(NotificationOutbox).filter_by(to_email=email).first()
    m = re.search(r"reset token: (\S+)", outbox_row.body)
    return m.group(1)


def test_reset_request_enqueues_and_does_not_store_plaintext(client, db_session):
    r = client.post("/api/auth/reset", json={"email": "a@example.com"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}

    token_row = db_session.query(ResetToken).filter_by(email="a@example.com").first()
    assert token_row is not None
    # Known Problem #2 fix: no MD5, and the raw token is never persisted.
    plaintext = _requested_token(db_session, "a@example.com")
    assert token_row.token_hash != plaintext
    assert len(token_row.token_hash) == 64  # sha256 hex digest


def test_reset_rate_limit(client):
    # server.py:85-89 — RATE_LIMIT_PER_HOUR = 3
    for _ in range(3):
        r = client.post("/api/auth/reset", json={"email": "limited@example.com"})
        assert r.status_code == 200
    r = client.post("/api/auth/reset", json={"email": "limited@example.com"})
    assert r.status_code == 429
    assert r.json()["detail"] == {"error": "rate_limited"}


def test_reset_bypass_header_skips_rate_limit(client):
    # server.py:84 — undocumented bypass header, preserved verbatim.
    for _ in range(5):
        r = client.post(
            "/api/auth/reset",
            json={"email": "bypassed@example.com"},
            headers={"X-Internal-Bypass": "1"},
        )
        assert r.status_code == 200


def test_confirm_reset_success(client, db_session):
    client.post("/api/auth/reset", json={"email": "b@example.com"})
    token = _requested_token(db_session, "b@example.com")

    r = client.post("/api/auth/reset/confirm", json={"token": token})
    assert r.status_code == 200
    assert r.json() == {"ok": True, "email": "b@example.com"}


def test_confirm_reset_invalid_and_expired_return_identical_body(client, db_session):
    # server.py:104-105 — deliberate non-disclosure.
    r_invalid = client.post("/api/auth/reset/confirm", json={"token": "does-not-exist"})
    assert r_invalid.status_code == 403
    assert r_invalid.json()["detail"] == {"error": "invalid_token"}

    client.post("/api/auth/reset", json={"email": "c@example.com"})
    token = _requested_token(db_session, "c@example.com")
    row = db_session.query(ResetToken).filter_by(email="c@example.com").first()
    from datetime import datetime, timedelta, timezone

    row.created_at = datetime.now(timezone.utc) - timedelta(minutes=31)
    db_session.commit()

    r_expired = client.post("/api/auth/reset/confirm", json={"token": token})
    assert r_expired.status_code == 403
    assert r_expired.json()["detail"] == r_invalid.json()["detail"]


def test_confirm_reset_token_not_reusable(client, db_session):
    client.post("/api/auth/reset", json={"email": "d@example.com"})
    token = _requested_token(db_session, "d@example.com")

    first = client.post("/api/auth/reset/confirm", json={"token": token})
    assert first.status_code == 200

    second = client.post("/api/auth/reset/confirm", json={"token": token})
    assert second.status_code == 403
