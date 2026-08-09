"""Ticket endpoints — wire-compatible with legacy server.py (ADR-003).

Compat routes parse JSON by hand: legacy error bodies and lenient parsing (Q3/Q5)
are part of the contract, so no Pydantic request models here.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.compat import lenient_json, now_utc, ticket_to_dict
from app.config import settings
from app.db import get_session
from app.models import Ticket
from app.services.outbox import enqueue_email
from app.services.slug import slugify

router = APIRouter()

# Legacy accepted "1"/"2"/"3" (or ints, via str()) as well as names (Q6, server.py:46-49).
_PRIORITY_NUMERIC = {"1": "low", "2": "med", "3": "high"}


def _int_or_404(tid: str) -> int:
    """Flask's <int:tid> converter 404s on non-digit ids; FastAPI's int param would
    422. Preserve the 404 (status-only parity, ADR-003)."""
    if not tid.isdigit():
        raise HTTPException(status_code=404)
    return int(tid)


@router.get("/api/tickets")
def list_tickets(status: str | None = None, session: Session = Depends(get_session)):
    q = select(Ticket)
    if status:
        q = q.where(Ticket.status == status)
    # Q4: no pagination — legacy UI depends on the full list.
    rows = session.scalars(q.order_by(Ticket.created_at.desc())).all()
    return [ticket_to_dict(t) for t in rows]


@router.post("/api/tickets")
async def create_ticket(request: Request, session: Session = Depends(get_session)):
    body = await lenient_json(request)
    title = str(body.get("title", "") or "").strip()
    if not title:
        return JSONResponse({"error": "title_required"}, status_code=422)  # Q3 shape

    priority = str(body.get("priority", "med"))
    priority = _PRIORITY_NUMERIC.get(priority, priority)
    # Any other value violates the CHECK constraint -> 500, same as legacy (Q6).

    ticket = Ticket(
        title=title,
        slug=slugify(title),
        priority=priority,
        status="open",
        created_at=now_utc(),
    )
    session.add(ticket)
    session.commit()
    return JSONResponse({"id": ticket.id, "slug": ticket.slug}, status_code=201)


@router.get("/api/tickets/{tid}")
def get_ticket(tid: str, session: Session = Depends(get_session)):
    ticket = session.get(Ticket, _int_or_404(tid))
    if ticket is None:
        return {}  # Q8: 200 with empty object, NOT 404 — legacy UI depends on it
    return ticket_to_dict(ticket)


@router.post("/api/tickets/{tid}/close")
def close_ticket(tid: str, session: Session = Depends(get_session)):
    tid_int = _int_or_404(tid)
    # Conditional update, same predicate as legacy (Q9): closing a closed or missing
    # ticket is a 200 {"closed": false}.
    result = session.execute(
        update(Ticket)
        .where(Ticket.id == tid_int, Ticket.status != "closed")
        .values(status="closed", closed_at=now_utc())
        .returning(Ticket.title)
    )
    row = result.first()
    if row is not None:
        # ADR-001: email enqueued in the SAME transaction as the close — no more
        # committed-but-unnotified 500s (Q10).
        enqueue_email(session, settings.watchers_addr, f"closed: {row.title}")
    session.commit()
    return {"closed": row is not None}


@router.get("/internal/export/csv")
def export_csv(session: Session = Depends(get_session)):
    # Dead-code candidate ("no caller since the 2020 audit" [S], unverified [U]).
    # Kept byte-compatible behind a flag (ADR-003) — including the naive comma-join
    # that corrupts output for titles containing commas/newlines. Deliberate.
    if not settings.enable_legacy_csv_export:
        raise HTTPException(status_code=404)
    # order_by(id) approximates SQLite's implicit rowid order in the legacy SELECT *.
    rows = session.scalars(select(Ticket).order_by(Ticket.id)).all()
    lines = ["id,title,status"] + [f"{t.id},{t.title},{t.status}" for t in rows]
    return PlainTextResponse("\n".join(lines), media_type="text/csv")
