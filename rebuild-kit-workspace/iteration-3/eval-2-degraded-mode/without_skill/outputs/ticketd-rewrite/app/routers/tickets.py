import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.models import Ticket
from app.notifications import outbox
from app.schemas import CloseTicketOut, TicketCreate, TicketCreateOut, TicketOut
from app.util import slugify

router = APIRouter(prefix="/api/tickets", tags=["tickets"])


@router.get("", response_model=list[TicketOut])
async def list_tickets(
    status: str | None = None, session: AsyncSession = Depends(get_session)
) -> list[Ticket]:
    # No pagination — matches legacy (app/server.py:36); the legacy UI is
    # known to rely on getting everything and filtering client-side.
    stmt = select(Ticket).order_by(Ticket.created_at.desc())
    if status:
        stmt = stmt.where(Ticket.status == status)
    result = await session.execute(stmt)
    return list(result.scalars())


@router.post("", response_model=TicketCreateOut, status_code=201)
async def create_ticket(
    body: TicketCreate, session: AsyncSession = Depends(get_session)
) -> dict:
    title = body.title.strip()
    if not title:
        return JSONResponse({"error": "title_required"}, status_code=422)

    slug = slugify(title)
    ticket = Ticket(
        title=title,
        slug=slug,
        priority=body.priority,
        status="open",
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )
    session.add(ticket)
    await session.commit()
    await session.refresh(ticket)
    return {"id": ticket.id, "slug": slug}


@router.get("/{ticket_id}")
async def get_ticket(ticket_id: int, session: AsyncSession = Depends(get_session)):
    ticket = await session.get(Ticket, ticket_id)
    if ticket is None:
        # Historical quirk, preserved deliberately: 200 with an empty body,
        # not 404 — legacy comment says the UI depends on it (app/server.py:63).
        # See docs/OPEN_QUESTIONS.md #1 before changing this.
        return {}
    return TicketOut.model_validate(ticket)


@router.post("/{ticket_id}/close", response_model=CloseTicketOut)
async def close_ticket(ticket_id: int, session: AsyncSession = Depends(get_session)) -> dict:
    ticket = await session.get(Ticket, ticket_id)
    changed = ticket is not None and ticket.status != "closed"
    if changed:
        ticket.status = "closed"
        ticket.closed_at = datetime.datetime.now(datetime.timezone.utc)
        # Fix for the sync-email-in-request problem: enqueue instead of
        # sending inline. See docs/DESIGN.md 'Fix 1'.
        await outbox.enqueue(
            session, settings.notify_watchers_email, f"closed: {ticket.title}"
        )
    await session.commit()
    return {"closed": changed}
