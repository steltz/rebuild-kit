"""Password-reset endpoints — legacy semantics preserved, crypto replaced (ADR-002)."""
from datetime import timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.compat import lenient_json, now_utc
from app.config import settings
from app.db import get_session
from app.models import ResetToken
from app.services.outbox import enqueue_email
from app.services.tokens import hash_token, new_token

router = APIRouter()


@router.post("/api/auth/reset")
async def request_reset(request: Request, session: Session = Depends(get_session)):
    body = await lenient_json(request)
    email = str(body.get("email", ""))

    # Q11: legacy honored an undocumented X-Internal-Bypass header unconditionally.
    # Ported behind a flag, DEFAULT OFF (ADR-002) — unknown callers, known hole.
    bypass = (
        settings.allow_internal_bypass
        and request.headers.get("X-Internal-Bypass") == "1"
    )
    if not bypass:
        # Same policy as legacy: 3/rolling-hour keyed by (attacker-supplied) email,
        # counted from the tokens table. Runs in the same tx as the insert below,
        # which legacy's check-then-insert did not guarantee.
        recent = session.scalar(
            select(func.count())
            .select_from(ResetToken)
            .where(
                ResetToken.email == email,
                ResetToken.created_at > now_utc() - timedelta(hours=1),
            )
        )
        if recent >= settings.rate_limit_per_hour:
            return JSONResponse({"error": "rate_limited"}, status_code=429)

    # ADR-002: CSPRNG token, hash at rest. Legacy: predictable md5(email+time),
    # stored in plaintext.
    token = new_token()
    session.add(ResetToken(email=email, token_hash=hash_token(token), created_at=now_utc()))
    # Legacy semantics preserved: token minted+mailed for ANY email, no user check,
    # response always ok (no enumeration). Email async via outbox (ADR-001).
    enqueue_email(session, email, f"reset token: {token}")
    session.commit()
    return {"ok": True}


@router.post("/api/auth/reset/confirm")
async def confirm_reset(request: Request, session: Session = Depends(get_session)):
    body = await lenient_json(request)
    token = str(body.get("token", ""))
    row = session.scalars(
        select(ResetToken).where(ResetToken.token_hash == hash_token(token))
    ).first()
    window = timedelta(minutes=settings.reset_window_min)
    if row is None or now_utc() - row.created_at > window:
        # Q12: expired and invalid tokens return the SAME body (deliberate
        # non-disclosure, legacy server.py:104). Preserve.
        return JSONResponse({"error": "invalid_token"}, status_code=403)
    # Single use. (Legacy deleted by token value, nuking duplicates too; duplicates
    # are cryptographically impossible now, so delete by pk.)
    session.execute(delete(ResetToken).where(ResetToken.id == row.id))
    session.commit()
    # The email field is consumed by an unidentified downstream system that actually
    # changes the password — frozen contract (dead-code-and-unknowns.md #1).
    return {"ok": True, "email": row.email}
