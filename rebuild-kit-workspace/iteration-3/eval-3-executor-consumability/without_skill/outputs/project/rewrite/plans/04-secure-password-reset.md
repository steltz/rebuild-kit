# ticketd rewrite — Phase 4: Secure Password Reset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Depends on:** Phase 3 (`03-async-notifications.md`) complete (this
> phase reuses `enqueue_notification`).
> **Read first:** `../DESIGN-password-reset.md` in full, and behavior
> contract section "POST /api/auth/reset" / "POST /api/auth/reset/confirm".
> **Before executing:** re-check `../03-OPEN-QUESTIONS.md` item 4
> (`X-Internal-Bypass` header) — this plan preserves that header exactly as
> a default, which may not be the right call.

**Goal:** Replace MD5-derived, plaintext-stored reset tokens with a secure
random-token + hashed-storage scheme, without changing either endpoint's
observable response contract (fixes the security team's finding).

**Architecture:** `POST /api/auth/reset` generates a random secret via
`secrets.token_urlsafe`, stores only its SHA-256 hash, and enqueues the raw
token to the notification outbox (reusing Phase 3's mechanism — so this
also fixes the same synchronous-SMTP problem for the reset flow, which
legacy has too, at lower volume). `POST /api/auth/reset/confirm` hashes the
submitted token and looks up by hash.

**Tech Stack:** stdlib `secrets` + `hashlib`, FastAPI, SQLAlchemy async.

## Global Constraints

- `POST /api/auth/reset` response is always `200 {"ok": true}` regardless
  of whether `email` corresponds to a real user (anti-enumeration,
  preserved from legacy — do not add a `users` existence check).
- `POST /api/auth/reset/confirm` returns `403 {"error": "invalid_token"}`
  — **identical body** — for: token never existed, token expired, and
  token already used. These three cases must be indistinguishable to the
  caller.
- Rate limit: `reset_rate_limit_per_hour` (default 3) per email per rolling
  hour, bypassed entirely when header `X-Internal-Bypass: 1` is present
  (preserved from legacy pending the open question above).
- Token lifetime: `reset_window_minutes` (default 30).
- No plaintext or MD5-derived token is ever written to the database.

---

### Task 1: Token service

**Files:**
- Create: `ticketd-api/app/services/tokens.py`
- Test: `ticketd-api/tests/test_tokens.py`

**Interfaces:**
- Produces: `generate_reset_token() -> tuple[str, str]` — returns
  `(raw_token, token_hash)`.
- Produces: `hash_token(raw_token: str) -> str`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tokens.py
from app.services.tokens import generate_reset_token, hash_token


def test_generate_reset_token_returns_raw_and_hash():
    raw, digest = generate_reset_token()
    assert len(raw) >= 32  # url-safe base64 of 32 random bytes
    assert digest == hash_token(raw)


def test_different_calls_produce_different_tokens():
    raw1, _ = generate_reset_token()
    raw2, _ = generate_reset_token()
    assert raw1 != raw2


def test_hash_is_not_reversible_looking_like_the_token():
    raw, digest = generate_reset_token()
    assert digest != raw
    assert len(digest) == 64  # sha256 hex digest
```

- [ ] **Step 2: Run to verify failure, then implement**

```python
# app/services/tokens.py
import hashlib
import secrets


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def generate_reset_token() -> tuple[str, str]:
    raw = secrets.token_urlsafe(32)
    return raw, hash_token(raw)
```

- [ ] **Step 3: Run tests, verify pass; commit**

```bash
pytest tests/test_tokens.py -v
git add app/services/tokens.py tests/test_tokens.py
git commit -m "feat: add secure reset-token generation (random secret, sha256-hashed storage)"
```

---

### Task 2: Auth routes

**Files:**
- Create: `ticketd-api/app/routes/auth.py`
- Create: `ticketd-api/app/schemas.py` additions (`ResetRequest`,
  `ResetConfirmRequest`)
- Modify: `ticketd-api/app/main.py` — register the router
- Test: `ticketd-api/tests/test_auth_reset.py`

**Interfaces:**
- Consumes: `app.services.tokens.{generate_reset_token, hash_token}`
  (Task 1), `app.services.outbox.enqueue_notification` (Phase 3),
  `app.config.get_settings()` (Phase 0).
- Produces: `POST /api/auth/reset`, `POST /api/auth/reset/confirm`.

- [ ] **Step 1: Add request schemas to `app/schemas.py`**

```python
class ResetRequest(BaseModel):
    email: str = ""


class ResetConfirmRequest(BaseModel):
    token: str = ""
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_auth_reset.py
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from app.main import app
from app.models import ResetToken, NotificationOutbox
from app.services.tokens import hash_token


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_reset_request_returns_ok_for_any_email(client, db_session):
    resp = await client.post("/api/auth/reset", json={"email": "nobody@corp.example.com"})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


@pytest.mark.asyncio
async def test_reset_request_stores_hash_not_plaintext(client, db_session):
    await client.post("/api/auth/reset", json={"email": "a@corp.example.com"})
    row = (await db_session.execute(select(ResetToken))).scalar_one()
    assert row.token_hash is not None
    assert len(row.token_hash) == 64  # sha256 hex -- not a raw token, not MD5 (32 hex chars)


@pytest.mark.asyncio
async def test_reset_request_enqueues_email_not_sends_inline(client, db_session, monkeypatch):
    def fail_if_called(*a, **kw):
        raise AssertionError("must not call SMTP directly")
    monkeypatch.setattr("smtplib.SMTP", fail_if_called)

    resp = await client.post("/api/auth/reset", json={"email": "a@corp.example.com"})
    assert resp.status_code == 200
    outbox = (await db_session.execute(select(NotificationOutbox))).scalars().all()
    assert len(outbox) == 1
    assert "a@corp.example.com" == outbox[0].to_address


@pytest.mark.asyncio
async def test_reset_rate_limited_after_three_per_hour(client, db_session):
    email = "ratelimited@corp.example.com"
    for _ in range(3):
        resp = await client.post("/api/auth/reset", json={"email": email})
        assert resp.status_code == 200
    resp = await client.post("/api/auth/reset", json={"email": email})
    assert resp.status_code == 429
    assert resp.json() == {"error": "rate_limited"}


@pytest.mark.asyncio
async def test_reset_bypass_header_skips_rate_limit(client, db_session):
    email = "bypass@corp.example.com"
    for _ in range(5):
        resp = await client.post(
            "/api/auth/reset", json={"email": email}, headers={"X-Internal-Bypass": "1"})
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_confirm_with_valid_token_succeeds(client, db_session, monkeypatch):
    captured = {}
    original_generate = __import__("app.services.tokens", fromlist=["generate_reset_token"]).generate_reset_token

    def capturing_generate():
        raw, digest = original_generate()
        captured["raw"] = raw
        return raw, digest
    monkeypatch.setattr("app.routes.auth.generate_reset_token", capturing_generate)

    await client.post("/api/auth/reset", json={"email": "a@corp.example.com"})
    resp = await client.post("/api/auth/reset/confirm", json={"token": captured["raw"]})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "email": "a@corp.example.com"}


@pytest.mark.asyncio
async def test_confirm_with_unknown_token_fails(client, db_session):
    resp = await client.post("/api/auth/reset/confirm", json={"token": "not-a-real-token"})
    assert resp.status_code == 403
    assert resp.json() == {"error": "invalid_token"}


@pytest.mark.asyncio
async def test_confirm_token_is_single_use(client, db_session, monkeypatch):
    captured = {}
    original_generate = __import__("app.services.tokens", fromlist=["generate_reset_token"]).generate_reset_token

    def capturing_generate():
        raw, digest = original_generate()
        captured["raw"] = raw
        return raw, digest
    monkeypatch.setattr("app.routes.auth.generate_reset_token", capturing_generate)

    await client.post("/api/auth/reset", json={"email": "a@corp.example.com"})
    first = await client.post("/api/auth/reset/confirm", json={"token": captured["raw"]})
    assert first.status_code == 200

    second = await client.post("/api/auth/reset/confirm", json={"token": captured["raw"]})
    assert second.status_code == 403
    # same body as an unknown token -- non-disclosure preserved
    assert second.json() == {"error": "invalid_token"}


@pytest.mark.asyncio
async def test_confirm_expired_token_fails_same_as_invalid(client, db_session):
    from datetime import datetime, timedelta, timezone
    from app.models import ResetToken
    from app.services.tokens import generate_reset_token

    raw, digest = generate_reset_token()
    db_session.add(ResetToken(
        email="a@corp.example.com",
        token_hash=digest,
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    ))
    await db_session.commit()

    resp = await client.post("/api/auth/reset/confirm", json={"token": raw})
    assert resp.status_code == 403
    assert resp.json() == {"error": "invalid_token"}
```

- [ ] **Step 3: Run to verify failure**

```bash
pytest tests/test_auth_reset.py -v
```
Expected: FAIL.

- [ ] **Step 4: Implement `app/routes/auth.py`**

```python
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.models import ResetToken
from app.schemas import ResetRequest, ResetConfirmRequest
from app.services.outbox import enqueue_notification
from app.services.tokens import generate_reset_token, hash_token

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/reset")
async def request_reset(
    body: ResetRequest,
    session: AsyncSession = Depends(get_session),
    x_internal_bypass: str | None = Header(default=None),
):
    settings = get_settings()
    email = body.email

    if x_internal_bypass != "1":
        window_start = datetime.now(timezone.utc) - timedelta(hours=1)
        recent = (
            await session.execute(
                select(func.count())
                .select_from(ResetToken)
                .where(ResetToken.email == email, ResetToken.created_at > window_start)
            )
        ).scalar_one()
        if recent >= settings.reset_rate_limit_per_hour:
            return JSONResponse(status_code=429, content={"error": "rate_limited"})

    raw_token, token_hash = generate_reset_token()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.reset_window_minutes)
    session.add(ResetToken(email=email, token_hash=token_hash, expires_at=expires_at))
    await enqueue_notification(session, to_address=email, body=f"reset token: {raw_token}")
    await session.commit()
    return {"ok": True}


@router.post("/reset/confirm")
async def confirm_reset(body: ResetConfirmRequest, session: AsyncSession = Depends(get_session)):
    digest = hash_token(body.token)
    row = (
        await session.execute(select(ResetToken).where(ResetToken.token_hash == digest))
    ).scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if row is None or row.used_at is not None or row.expires_at < now:
        # SAME body for "never existed", "already used", "expired" -- non-disclosure.
        return JSONResponse(status_code=403, content={"error": "invalid_token"})

    row.used_at = now
    await session.commit()
    return {"ok": True, "email": row.email}
```

- [ ] **Step 5: Register the router in `app/main.py`**

```python
from app.routes import auth
app.include_router(auth.router)
```

- [ ] **Step 6: Run tests, verify pass**

```bash
pytest tests/test_auth_reset.py -v
```
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add app/routes/auth.py app/schemas.py app/main.py tests/test_auth_reset.py
git commit -m "feat: implement secure password-reset flow (fixes MD5 token finding)"
```

---

## Definition of done for this phase

- No MD5 anywhere in `ticketd-api/`.
- `reset_tokens.token_hash` is unique and no raw token is ever persisted.
- Rate limiting and the `X-Internal-Bypass` header behave exactly as
  legacy (pending resolution of `../03-OPEN-QUESTIONS.md` item 4).
- The three-way non-disclosure property (unknown/expired/used all return
  identical `403` bodies) is directly tested.
- Reset emails go through the same outbox as ticket-close notifications —
  no synchronous SMTP call anywhere in this phase either.
