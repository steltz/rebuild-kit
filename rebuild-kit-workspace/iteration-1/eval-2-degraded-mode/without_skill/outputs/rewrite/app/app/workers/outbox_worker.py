"""Outbox delivery worker (ADR-001). Run as its own process:

    python -m app.workers.outbox_worker

Polls outbox_emails for unsent rows, delivers via SMTP, retries with backoff-by-poll,
gives up after MAX_ATTEMPTS (rows stay with last_error for inspection). Also purges
expired reset tokens (ADR-002 hygiene).
"""
import logging
import smtplib
import time
from datetime import timedelta

from sqlalchemy import delete, select

from app.compat import now_utc
from app.config import settings
from app.db import SessionLocal
from app.models import OutboxEmail, ResetToken

log = logging.getLogger("outbox_worker")

POLL_SECONDS = 2.0
MAX_ATTEMPTS = 10
BATCH = 50
TOKEN_PURGE_AFTER = timedelta(hours=24)  # well past the 30-min validity window


def _send(recipient: str, body: str) -> None:
    # Matches legacy notify.py: plain SMTP, no TLS/auth. With smtp_legacy_headerless
    # (default true) the payload is the bare body, envelope-only, exactly like legacy;
    # flip the flag once a captured production email shows what recipients expect.
    payload = body
    if not settings.smtp_legacy_headerless:
        payload = (
            f"From: {settings.mail_from}\r\nTo: {recipient}\r\n"
            f"Subject: ticketd notification\r\n\r\n{body}"
        )
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port,
                      timeout=settings.smtp_timeout) as s:
        s.sendmail(settings.mail_from, [recipient], payload)


def process_once() -> int:
    """One drain pass. Returns number of rows attempted."""
    with SessionLocal() as session:
        rows = session.scalars(
            select(OutboxEmail)
            .where(OutboxEmail.sent_at.is_(None), OutboxEmail.attempts < MAX_ATTEMPTS)
            .order_by(OutboxEmail.id)
            .limit(BATCH)
            .with_for_update(skip_locked=True)  # safe with multiple workers
        ).all()
        for row in rows:
            row.attempts += 1
            try:
                _send(row.recipient, row.body)
                row.sent_at = now_utc()
                row.last_error = None
            except Exception as exc:  # noqa: BLE001 — record and retry next pass
                row.last_error = repr(exc)[:500]
                log.warning("send failed (attempt %s) to %s: %r",
                            row.attempts, row.recipient, exc)
        session.commit()
        return len(rows)


def purge_expired_tokens() -> None:
    with SessionLocal() as session:
        session.execute(
            delete(ResetToken).where(
                ResetToken.created_at < now_utc() - TOKEN_PURGE_AFTER
            )
        )
        session.commit()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    log.info("outbox worker started (poll=%ss)", POLL_SECONDS)
    last_purge = 0.0
    while True:
        attempted = process_once()
        if time.monotonic() - last_purge > 3600:
            purge_expired_tokens()
            last_purge = time.monotonic()
        if attempted < BATCH:
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
