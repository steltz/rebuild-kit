"""GET/POST /api/tickets -- WO-001 (Milestone 0 walking skeleton).

Both routes are FIXED fidelity per docs/features/WO-001-walking-skeleton.md: they reproduce
legacy/app/server.py's observable behavior exactly, including two gaps the spec explicitly
says to reproduce rather than silently harden:
  - an invalid `priority` value hits an uncaught DB CHECK violation (500), not a handled 4xx
  - a non-dict JSON body, or a `title` that is present-but-null/non-string, raises an uncaught
    AttributeError (via `body.get("title", "").strip()`) -> 500

Both surface as FastAPI's registered `Exception` handler (see app/main.py), which reproduces
Werkzeug's default production 500 page byte-for-byte -- the legacy app has no error handling
of its own, so any uncaught exception in *any* route falls through to that same generic page.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Ticket
from app.schemas import TicketOut
from app.services.slug import slugify

router = APIRouter()

# "1"/"2"/"3" -> low/med/high (docs/features/draft/tickets-create.md); any other string is
# passed through unchanged and either matches low/med/high directly or hits the CHECK
# constraint uncaught, per FIXED fidelity.
_PRIORITY_ALIASES = {"1": "low", "2": "med", "3": "high"}


@router.get("/api/tickets")
def list_tickets(
    status: str | None = None, session: Session = Depends(get_session)
) -> list[TicketOut]:
    stmt = select(Ticket).order_by(Ticket.created_at.desc())
    if status is not None:
        stmt = stmt.where(Ticket.status == status)
    rows = session.scalars(stmt).all()
    return [TicketOut.model_validate(r) for r in rows]


@router.post("/api/tickets", status_code=201)
async def create_ticket(request: Request, session: Session = Depends(get_session)):
    try:
        raw = await request.json()
    except Exception:
        raw = None
    body = raw if raw else {}
    # Literal port of legacy's `body.get("title", "").strip()` -- deliberately NOT
    # type-guarded: a non-dict body or a non-string title raises AttributeError here,
    # exactly as legacy does, and is left to propagate to the global 500 handler.
    title = body.get("title", "").strip()
    if not title:
        return JSONResponse({"error": "title_required"}, status_code=422)

    priority = body.get("priority", "med")
    priority = _PRIORITY_ALIASES.get(priority, priority)
    slug = slugify(title)

    ticket = Ticket(
        title=title,
        slug=slug,
        priority=priority,
        status="open",
        created_at=datetime.now(timezone.utc),
    )
    session.add(ticket)
    session.flush()  # assigns ticket.id; raises IntegrityError uncaught on a bad `priority`
    return JSONResponse({"id": ticket.id, "slug": ticket.slug}, status_code=201)
