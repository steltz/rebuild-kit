import datetime

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.models import ResetToken
from app.notifications import outbox
from app.schemas import ResetConfirmIn, ResetConfirmOut, ResetRequestIn, ResetRequestOut
from app.security import generate_reset_token, hash_token

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/reset", response_model=ResetRequestOut)
async def request_reset(
    body: ResetRequestIn,
    session: AsyncSession = Depends(get_session),
    x_internal_bypass: str | None = Header(default=None, alias="X-Internal-Bypass"),
) -> dict:
    email = body.email

    # Preserved as-is from legacy (app/server.py:84): an unauthenticated
    # header bypasses rate limiting. This is a real security concern — see
    # docs/OPEN_QUESTIONS.md #2 — but it's carried forward unchanged because
    # we don't know what currently depends on it working exactly this way.
    if x_internal_bypass != "1":
        window_start = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)
        recent = await session.scalar(
            select(func.count())
            .select_from(ResetToken)
            .where(ResetToken.email == email, ResetToken.created_at > window_start)
        )
        if recent >= settings.rate_limit_per_hour:
            # Matches legacy body shape ({"error": ...}), not FastAPI's
            # default {"detail": ...} — see app/server.py:88-89.
            return JSONResponse({"error": "rate_limited"}, status_code=429)

    # Fix for the MD5-token problem: random plaintext token, only its hash
    # is persisted. See docs/DESIGN.md 'Fix 2'.
    token = generate_reset_token()
    session.add(
        ResetToken(
            email=email,
            token_hash=hash_token(token),
            created_at=datetime.datetime.now(datetime.timezone.utc),
        )
    )
    # Fix for the sync-email-in-request problem: enqueue instead of sending
    # inline. See docs/DESIGN.md 'Fix 1'.
    await outbox.enqueue(session, email, f"reset token: {token}")
    await session.commit()
    return {"ok": True}


@router.post("/reset/confirm", response_model=ResetConfirmOut)
async def confirm_reset(
    body: ResetConfirmIn, session: AsyncSession = Depends(get_session)
) -> dict:
    token_hash = hash_token(body.token)
    result = await session.execute(select(ResetToken).where(ResetToken.token_hash == token_hash))
    row = result.scalar_one_or_none()

    expiry = datetime.timedelta(minutes=settings.reset_window_minutes)
    now = datetime.datetime.now(datetime.timezone.utc)
    if row is None or now - row.created_at > expiry:
        # Deliberate, preserved from legacy: expired and invalid tokens
        # return the SAME body, to avoid disclosing which case applies
        # (app/server.py:104-105). Body shape matches legacy ({"error": ...}).
        return JSONResponse({"error": "invalid_token"}, status_code=403)

    await session.delete(row)
    await session.commit()
    return {"ok": True, "email": row.email}
