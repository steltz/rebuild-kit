"""
Ported from ticketd/app/server.py:111-115 (`/internal/export/csv`).

Legacy comment: "written for the 2020 audit; no caller since." We have no
access logs to confirm that, so it is ported rather than dropped — see
docs/03-OPEN-QUESTIONS-AND-RISK-REGISTER.md. Also note it is unauthenticated
in the source as handed over; that is preserved here too (not hardened),
again for lack of evidence about what calls it or how it's fronted in
production. This is flagged as a priority item to resolve once logs exist.
"""
from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models import Ticket

router = APIRouter(prefix="/internal/export", tags=["export"])


@router.get("/csv")
def export_csv(db: Session = Depends(get_db)):
    rows = db.scalars(select(Ticket)).all()
    lines = ["id,title,status"] + [f"{t.id},{t.title},{t.status}" for t in rows]
    return PlainTextResponse("\n".join(lines), media_type="text/csv")
