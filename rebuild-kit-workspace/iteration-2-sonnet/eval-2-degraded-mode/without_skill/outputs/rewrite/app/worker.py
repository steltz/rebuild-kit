"""
Outbox worker: polls notification_outbox and sends due emails via SMTP.

Run as a separate process/deployment from the API
(`python -m app.worker`). This is what actually fixes Known Problem #1 —
without this process running, notifications queue up but never send, which
is deliberately loud (rows just sit with sent_at IS NULL) rather than
silently dropping them the way an in-process background task could on a
restart.

EVIDENCE-NEEDED: polling interval/batch size (app/config.py) are
conservative guesses, not derived from traffic data. Revisit once volume is
known. If this ever needs to scale beyond a single poller, add a
`SELECT ... FOR UPDATE SKIP LOCKED` to the query in
app/services/notify.send_due_notifications so multiple workers don't race
on the same rows.
"""
import logging
import time

from app.config import settings
from app.db import SessionLocal
from app.services.notify import send_due_notifications

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ticketd.worker")


def run_forever() -> None:
    logger.info("outbox worker starting, poll_interval=%ss", settings.worker_poll_interval_seconds)
    while True:
        db = SessionLocal()
        try:
            sent = send_due_notifications(db)
            if sent:
                logger.info("sent %d notification(s)", sent)
        finally:
            db.close()
        time.sleep(settings.worker_poll_interval_seconds)


if __name__ == "__main__":
    run_forever()
