"""
Ported from ticketd/app/server.py's /api/auth/reset* endpoints.

Fixed (Known Problem #2): tokens are `secrets.token_urlsafe` instead of
MD5(email + time.time()); only a SHA-256 hash is persisted
(app/services/tokens.py, app/models.ResetToken).

Fixed (Known Problem #1): the reset email is enqueued to the outbox instead
of sent synchronously (server.py:94).

Preserved verbatim (no evidence to justify changing):
  - Rate limit of `settings.rate_limit_per_hour` per email per rolling hour
    (server.py:85-89).
  - The `X-Internal-Bypass: 1` header skips the rate limit entirely
    (server.py:84). This is undocumented anywhere except this code and we
    have no log evidence of who/what sends it. Preserving it verbatim rather
    than removing it, because removing an auth-adjacent bypass without
    knowing what depends on it is its own kind of risk. Comparison is
    constant-time (tokens.constant_time_eq) as a no-behavior-change security
    hardening. See docs/03-OPEN-QUESTIONS-AND-RISK-REGISTER.md — this is the
    single highest-priority item to resolve once logs are available.
  - Reset window of `settings.reset_window_minutes` (server.py:103).
  - Expired and invalid tokens return the IDENTICAL 403 body
    (server.py:104-105, deliberate non-disclosure per the original comment).

Minor internal (non-contract) change: a used token is marked `used_at`
instead of being DELETEd (server.py:106). External behavior is identical
(the token can't be reused either way); the soft-delete just leaves an
audit trail. Flagged here for visibility even though it doesn't change the
API.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.deps import get_db
from app.models import ResetToken
from app.schemas import ResetConfirm, ResetConfirmResponse, ResetRequest, ResetRequestResponse
from app.services import notify
from app.services.tokens import constant_time_eq, generate_token, hash_token

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _as_utc(dt: datetime) -> datetime:
    """Postgres (TIMESTAMPTZ) round-trips tz-aware datetimes; SQLite (used
    only by the test suite, tests/conftest.py) stores/returns naive ones.
    Normalize so comparisons work identically against either backend."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


@router.post("/reset", response_model=ResetRequestResponse)
def request_reset(body: ResetRequest, request: Request, db: Session = Depends(get_db)):
    bypass = constant_time_eq(
        request.headers.get(settings.internal_bypass_header, ""),
        settings.internal_bypass_value,
    )
    if not bypass:
        window_start = datetime.now(timezone.utc) - timedelta(hours=1)
        recent = db.scalar(
            select(func.count())
            .select_from(ResetToken)
            .where(ResetToken.email == body.email)
            .where(ResetToken.created_at > window_start)
        )
        if recent >= settings.rate_limit_per_hour:
            raise HTTPException(status_code=429, detail={"error": "rate_limited"})

    token = generate_token()
    db.add(ResetToken(email=body.email, token_hash=hash_token(token)))
    notify.enqueue(db, body.email, "password reset", f"reset token: {token}")
    db.commit()
    return ResetRequestResponse(ok=True)


@router.post("/reset/confirm", response_model=ResetConfirmResponse)
def confirm_reset(body: ResetConfirm, db: Session = Depends(get_db)):
    token_hash = hash_token(body.token)
    row = db.scalar(select(ResetToken).where(ResetToken.token_hash == token_hash))

    expired = row is not None and (
        datetime.now(timezone.utc) - _as_utc(row.created_at) > timedelta(minutes=settings.reset_window_minutes)
    )
    already_used = row is not None and row.used_at is not None

    if row is None or expired or already_used:
        # Same body for "doesn't exist", "expired", and "already used" —
        # matches the legacy non-disclosure behavior at server.py:104-105.
        raise HTTPException(status_code=403, detail={"error": "invalid_token"})

    row.used_at = datetime.now(timezone.utc)
    db.commit()
    return ResetConfirmResponse(ok=True, email=row.email)
