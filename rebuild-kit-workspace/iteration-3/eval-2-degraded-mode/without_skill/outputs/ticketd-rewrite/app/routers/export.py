from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Ticket

router = APIRouter(prefix="/internal/export", tags=["export"])


@router.get("/csv")
async def export_csv(session: AsyncSession = Depends(get_session)) -> PlainTextResponse:
    # Ported as-is; legacy comment says "no caller since [2020]" — see
    # docs/OPEN_QUESTIONS.md #4 before removing.
    result = await session.execute(select(Ticket))
    tickets = result.scalars()
    lines = ["id,title,status"] + [f"{t.id},{t.title},{t.status}" for t in tickets]
    return PlainTextResponse("\n".join(lines), media_type="text/csv")
