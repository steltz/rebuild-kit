import pytest
from sqlalchemy import select

from app.db import async_session
from app.models import ResetToken


@pytest.mark.asyncio
async def test_request_reset_creates_hashed_token_not_plaintext(client):
    resp = await client.post("/api/auth/reset", json={"email": "a@example.com"})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    async with async_session() as session:
        result = await session.execute(select(ResetToken))
        rows = list(result.scalars())
    assert len(rows) == 1
    # Fix for the MD5-plaintext problem: token_hash is a sha256 hex digest,
    # never the raw token. See docs/DESIGN.md 'Fix 2'.
    assert len(rows[0].token_hash) == 64
    assert rows[0].token_hash != "a@example.com"


@pytest.mark.asyncio
async def test_confirm_reset_round_trip(client):
    await client.post("/api/auth/reset", json={"email": "b@example.com"})

    # The plaintext token isn't in the API response (it's only in the
    # notification body) — reach into the outbox to get it, the way a real
    # email would deliver it to the user.
    from app.models import OutboxMessage

    async with async_session() as session:
        result = await session.execute(select(OutboxMessage))
        message = result.scalars().one()
    token = message.body.removeprefix("reset token: ")

    resp = await client.post("/api/auth/reset/confirm", json={"token": token})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "email": "b@example.com"}

    # Token is single-use, matches legacy.
    resp = await client.post("/api/auth/reset/confirm", json={"token": token})
    assert resp.status_code == 403
    assert resp.json() == {"error": "invalid_token"}


@pytest.mark.asyncio
async def test_confirm_reset_invalid_token_matches_expired_response(client):
    # Deliberate: same body/status for invalid vs. expired, to avoid
    # disclosure — see docs/DESIGN.md and app/routers/auth.py.
    resp = await client.post("/api/auth/reset/confirm", json={"token": "not-a-real-token"})
    assert resp.status_code == 403
    assert resp.json() == {"error": "invalid_token"}


@pytest.mark.asyncio
async def test_reset_rate_limited_after_threshold(client):
    for _ in range(3):
        resp = await client.post("/api/auth/reset", json={"email": "c@example.com"})
        assert resp.status_code == 200

    resp = await client.post("/api/auth/reset", json={"email": "c@example.com"})
    assert resp.status_code == 429
    assert resp.json() == {"error": "rate_limited"}


@pytest.mark.asyncio
async def test_internal_bypass_header_skips_rate_limit(client):
    # Preserved legacy behavior — flagged as a security concern, not fixed
    # silently. See docs/OPEN_QUESTIONS.md #2.
    for _ in range(5):
        resp = await client.post(
            "/api/auth/reset",
            json={"email": "d@example.com"},
            headers={"X-Internal-Bypass": "1"},
        )
        assert resp.status_code == 200
