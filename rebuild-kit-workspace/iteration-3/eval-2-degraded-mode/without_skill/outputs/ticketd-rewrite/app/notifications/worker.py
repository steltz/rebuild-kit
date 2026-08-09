"""Background poller that drains app/notifications/outbox.py rows. Started
from the FastAPI lifespan in app/main.py. See docs/DESIGN.md 'Fix 1' for the
trade-offs of this in-process design vs. a real message broker.
"""

import asyncio
import datetime
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import async_session
from app.models import OutboxMessage
from app.notifications.interface import NotificationBackend

logger = logging.getLogger("ticketd.outbox")


async def _drain_once(session: AsyncSession, backend: NotificationBackend) -> int:
    # FOR UPDATE SKIP LOCKED: safe if this worker ever runs with >1 replica.
    result = await session.execute(
        select(OutboxMessage)
        .where(OutboxMessage.status == "pending")
        .order_by(OutboxMessage.created_at)
        .limit(20)
        .with_for_update(skip_locked=True)
    )
    messages = list(result.scalars())
    for message in messages:
        try:
            await backend.send(message.to_email, message.body)
            message.status = "sent"
            message.sent_at = datetime.datetime.now(datetime.timezone.utc)
        except Exception:
            message.attempts += 1
            if message.attempts >= settings.outbox_max_attempts:
                message.status = "failed"
                logger.exception(
                    "outbox message %s to %s permanently failed after %s attempts",
                    message.id,
                    message.to_email,
                    message.attempts,
                )
            else:
                logger.warning(
                    "outbox message %s to %s failed (attempt %s), will retry",
                    message.id,
                    message.to_email,
                    message.attempts,
                )
    await session.commit()
    return len(messages)


async def run_outbox_worker(backend: NotificationBackend, stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            async with async_session() as session:
                await _drain_once(session, backend)
        except Exception:
            logger.exception("outbox worker iteration failed")
        try:
            await asyncio.wait_for(
                stop_event.wait(), timeout=settings.outbox_poll_interval_seconds
            )
        except TimeoutError:
            pass
