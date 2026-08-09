"""Enqueue email in the caller's transaction (ADR-001). Delivery: workers/outbox_worker.py."""
from sqlalchemy.orm import Session

from app.compat import now_utc
from app.models import OutboxEmail


def enqueue_email(session: Session, recipient: str, body: str) -> None:
    """Adds an outbox row to the session WITHOUT committing — commits atomically with
    whatever state change caused the email (fixes Q10 partial failure)."""
    session.add(OutboxEmail(recipient=recipient, body=body, created_at=now_utc()))
