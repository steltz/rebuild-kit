"""Tests run against a real Postgres database (see docs/DESIGN.md — no
SQLite-in-tests, to avoid the dialect drift that bit this codebase before).

Point TEST_DATABASE_URL at a scratch Postgres database, or just run
`docker compose up -d db` and use the default in app/config.py. Tables are
created/dropped per test function so tests stay isolated without needing a
full migration run each time.
"""

import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine

os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get(
        "TEST_DATABASE_URL", "postgresql+asyncpg://ticketd:ticketd@localhost:5432/ticketd"
    ),
)

from app import models  # noqa: E402  (import after DATABASE_URL is set)
from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest_asyncio.fixture(autouse=True)
async def _clean_schema():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
