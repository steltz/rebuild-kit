import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OutboxMessage


async def enqueue(session: AsyncSession, to_email: str, body: str) -> None:
    """Writes a pending outbox row in the caller's transaction. Does not
    commit — caller controls the transaction boundary so the notification
    is enqueued atomically with the business change (ticket close / reset
    request), never orphaned by a failure after the fact."""
    session.add(
        OutboxMessage(
            to_email=to_email,
            body=body,
            status="pending",
            attempts=0,
            created_at=datetime.datetime.now(datetime.timezone.utc),
        )
    )
