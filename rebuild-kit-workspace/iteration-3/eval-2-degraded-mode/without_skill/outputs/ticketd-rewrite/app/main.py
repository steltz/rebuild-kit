import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.notifications.smtp_backend import SmtpNotificationBackend
from app.notifications.worker import run_outbox_worker
from app.routers import auth, export, tickets


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    stop_event = asyncio.Event()
    worker_task = asyncio.create_task(run_outbox_worker(SmtpNotificationBackend(), stop_event))
    try:
        yield
    finally:
        stop_event.set()
        await worker_task


app = FastAPI(title="ticketd", lifespan=lifespan)

app.include_router(tickets.router)
app.include_router(auth.router)
app.include_router(export.router)
