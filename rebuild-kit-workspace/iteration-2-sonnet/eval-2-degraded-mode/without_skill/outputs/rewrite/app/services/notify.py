"""
Fixes Known Problem #1: notification email sent synchronously inside the
request (ticketd/app/notify.py, ticketd/app/server.py:76,94 — the module
docstring itself says "~2s typical, 30s on provider trouble").

Replacement: transactional outbox pattern.

- `enqueue()` is called from request handlers and does nothing but INSERT a
  row into notification_outbox using the SAME db session/transaction as the
  handler's primary write (e.g. closing a ticket). No network I/O happens on
  the request path at all. The row is committed atomically with the ticket
  update, so a crash between "ticket closed" and "email queued" can't happen
  — either both happened or neither did.
- `send_due_notifications()` is run by app/worker.py, a separate process, on
  a poll loop. It does the actual SMTP call.

Why an outbox table instead of FastAPI's BackgroundTasks or an external
queue (Celery/RQ/SQS)? We have no evidence about what infra will be
available in the new environment, and BackgroundTasks runs in-process — a
pod restart between "response sent" and "task executed" silently drops the
email, which is a worse failure mode than the one we're fixing. The outbox
survives process restarts using only the Postgres database this service
already depends on. If evidence later shows a message queue is available
and preferred, swap the worker's polling loop for a queue consumer; the
`enqueue()` call sites in routers/ don't need to change.
"""
from __future__ import annotations

import smtplib
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import NotificationOutbox


def enqueue(db: Session, to_email: str, subject: str, body: str) -> None:
    """Queue a notification. Caller is responsible for committing the
    surrounding transaction (or letting FastAPI's request-scoped session
    commit it) — this function only adds to the session."""
    db.add(NotificationOutbox(to_email=to_email, subject=subject, body=body))


def send_due_notifications(db: Session) -> int:
    """Send up to `worker_batch_size` unsent notifications. Returns count
    sent. Intended to be called in a loop by app/worker.py, not from request
    handlers."""
    rows = db.scalars(
        select(NotificationOutbox)
        .where(NotificationOutbox.sent_at.is_(None))
        .where(NotificationOutbox.attempts < settings.worker_max_attempts)
        .order_by(NotificationOutbox.created_at)
        .limit(settings.worker_batch_size)
    ).all()

    sent = 0
    for row in rows:
        try:
            _send_smtp(row.to_email, row.subject, row.body)
        except Exception as exc:  # noqa: BLE001 - persist failure, keep looping
            row.attempts += 1
            row.last_error = str(exc)[:2000]
        else:
            row.sent_at = datetime.now(timezone.utc)
            sent += 1
        db.commit()
    return sent


def _send_smtp(to_email: str, subject: str, body: str) -> None:
    message = f"Subject: {subject}\n\n{body}"
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_seconds) as s:
        s.sendmail(settings.mail_from, [to_email], message)
