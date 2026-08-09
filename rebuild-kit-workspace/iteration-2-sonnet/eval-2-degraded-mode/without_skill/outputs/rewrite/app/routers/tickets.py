"""
Ported from ticketd/app/server.py's ticket endpoints. See
docs/01-LEGACY-BEHAVIOR-INVENTORY.md for the full behavior table this file
is required to match.

Deliberately preserved oddities (NOT fixed — no evidence to justify
changing them):
  - GET /api/tickets returns the full unpaginated list (server.py:35 comment:
    UI fetches everything and filters client-side).
  - GET /api/tickets/{id} returns 200 {} for a missing ticket, not 404
    (server.py:62-63 comment: legacy UI depends on it).
  - POST /api/tickets accepts priority as "low/med/high" OR "1/2/3"
    (server.py:46-49).

Fixed (Known Problem #1): ticket-close notification is enqueued to the
outbox instead of sent synchronously (server.py:76).
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models import Ticket
from app.schemas import TicketCloseResponse, TicketCreate, TicketCreateResponse, TicketOut
from app.services import notify
from app.services.slug import slugify

router = APIRouter(prefix="/api/tickets", tags=["tickets"])


@router.get("", response_model=list[TicketOut])
def list_tickets(status: Optional[str] = None, db: Session = Depends(get_db)):
    # EVIDENCE-NEEDED: no pagination, matching legacy server.py:27-37.
    # See docs/03-OPEN-QUESTIONS-AND-RISK-REGISTER.md — do not add
    # pagination without confirming the client can handle it.
    stmt = select(Ticket)
    if status:
        stmt = stmt.where(Ticket.status == status)
    stmt = stmt.order_by(Ticket.created_at.desc())
    return db.scalars(stmt).all()


@router.post("", response_model=TicketCreateResponse, status_code=201)
def create_ticket(body: TicketCreate, db: Session = Depends(get_db)):
    if not body.title:
        # Matches server.py:44-45 (422 title_required). FastAPI's own
        # validation-error shape differs from Flask's jsonify({"error":...}),
        # so this is raised explicitly to keep the response body identical
        # for existing clients.
        raise HTTPException(status_code=422, detail={"error": "title_required"})

    slug = slugify(body.title)
    ticket = Ticket(title=body.title, slug=slug, priority=body.priority, status="open")
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return TicketCreateResponse(id=ticket.id, slug=ticket.slug)


@router.get("/{ticket_id}")
def get_ticket(ticket_id: int, db: Session = Depends(get_db)):
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        # server.py:62-63: 200 with an empty object, not 404. Preserved
        # verbatim — flagged as unconfirmed-but-load-bearing in the
        # behavior inventory.
        return {}
    return TicketOut.model_validate(ticket)


@router.post("/{ticket_id}/close", response_model=TicketCloseResponse)
def close_ticket(ticket_id: int, db: Session = Depends(get_db)):
    ticket = db.get(Ticket, ticket_id)
    if ticket is None or ticket.status == "closed":
        return TicketCloseResponse(closed=False)

    ticket.status = "closed"
    ticket.closed_at = datetime.now(timezone.utc)

    # Fix for Known Problem #1: enqueue instead of sending inline. Enqueued
    # in the SAME transaction/commit as the ticket update below, so the two
    # can't diverge (either both persist or neither does).
    notify.enqueue(db, "watchers@example.internal", "ticket closed", f"closed: {ticket.title}")

    db.commit()
    return TicketCloseResponse(closed=True)
