# ticketd Rewrite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace ticketd's Flask + SQLite backend with FastAPI + Postgres, eliminating synchronous SMTP-in-request, MD5 reset tokens, and slug collisions — with zero observable API/UI changes beyond what's documented as intentional in the spec.

**Architecture:** FastAPI app (async, SQLAlchemy 2.0 + asyncpg) exposes the same routes as today. Writes that currently trigger email now write a row to a `notifications` outbox table in the same DB transaction and return immediately. A separate, synchronous worker process (`app/worker.py`, plain SQLAlchemy + psycopg2, no asyncio) polls that table and does the actual SMTP send with retry/backoff. Ticket creation uses a unique-constraint-and-retry loop to guarantee collision-free slugs. Reset tokens are `secrets.token_urlsafe(32)`, stored only as a SHA-256 hash.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2.0 (async engine + asyncpg for the app; sync engine + psycopg2 for the worker and migration scripts, since neither needs concurrency and it avoids an async SMTP dependency), Alembic, Postgres 16, pytest + pytest-asyncio + httpx.

**Spec:** `docs/superpowers/specs/2026-08-09-ticketd-rewrite-design.md` — read it first. This plan implements it section by section; cross-references use `§N`.

## Global Constraints

- No UI changes. Every route in spec §4 must match documented request/response shape, status codes, and quirks exactly (the `GET /api/tickets/<id>` → `200 {}` on missing; identical `403 {"error": "invalid_token"}` body for invalid AND expired reset tokens; idempotent close; `priority` accepting `"1"/"2"/"3"` or `"low"/"med"/"high"`).
- No synchronous SMTP calls anywhere in a FastAPI request handler. All email goes through the `notifications` outbox table (spec §6).
- Slugs are guaranteed unique via a DB `UNIQUE` constraint plus a bounded retry-with-numeric-suffix loop (spec §5) — never a pre-check-then-insert.
- Reset tokens: generate with `secrets.token_urlsafe(32)`; store only `sha256(token)` in `token_hash`; store `expires_at` explicitly at insert time (spec §7).
- Timestamps: `timestamptz`, always UTC, serialized with an explicit offset (spec: "Timestamp serialization").
- `reset_tokens` is not migrated from SQLite — the new table starts empty (spec §9).
- `X-Internal-Bypass: 1` header behavior on `POST /api/auth/reset` is preserved unchanged (spec §4).
- `GET /internal/export/csv` is ported unchanged, not deleted (spec §4).

---

### Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `app/__init__.py`
- Create: `app/config.py`
- Create: `app/db.py`
- Create: `app/main.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `docker-compose.test.yml`

**Interfaces:**
- Produces: `app.config.settings` (a `Settings` instance with `database_url`, `database_url_sync`, `smtp_host`, `smtp_port`, `smtp_timeout`, `notify_from`, `watchers_addr`, `reset_window_min`, `rate_limit_per_hour`).
- Produces: `app.db.SessionLocal` (async sessionmaker), `app.db.get_session()` (FastAPI dependency yielding an `AsyncSession`).
- Produces: `app.main.app` (the FastAPI instance, routers included in later tasks).
- Produces: `tests/conftest.py` fixtures `session` (a real `AsyncSession` against a throwaway-schema test Postgres DB) and `client` (an `httpx.AsyncClient` wired to `app` with `get_session` overridden to use `session`).

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "ticketd"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.29",
    "psycopg2-binary>=2.9",
    "alembic>=1.13",
    "pydantic-settings>=2.4",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "httpx>=0.27",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"
```

- [ ] **Step 2: Write `docker-compose.test.yml`** (local Postgres for tests; use an existing local Postgres install instead if the Docker daemon isn't available in the execution environment — see verification doc)

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: ticketd
      POSTGRES_PASSWORD: ticketd
      POSTGRES_DB: ticketd_test
    ports:
      - "5432:5432"
```

- [ ] **Step 3: Write `app/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TICKETD_")

    database_url: str = "postgresql+asyncpg://ticketd:ticketd@localhost:5432/ticketd"
    database_url_sync: str = "postgresql+psycopg2://ticketd:ticketd@localhost:5432/ticketd"
    smtp_host: str = "smtp.internal"
    smtp_port: int = 25
    smtp_timeout: float = 30.0
    notify_from: str = "ticketd@example.internal"
    watchers_addr: str = "watchers@example.internal"
    reset_window_min: int = 30
    rate_limit_per_hour: int = 3


settings = Settings()
```

- [ ] **Step 4: Write `app/db.py`**

```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

engine = create_async_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncSession:
    async with SessionLocal() as session:
        yield session
```

- [ ] **Step 5: Write `app/main.py`** (routers added in later tasks; `/healthz` is a new, non-UI-facing operational endpoint for the new stack, not a spec-covered route)

```python
from fastapi import FastAPI

app = FastAPI()


@app.get("/healthz")
async def healthz():
    return {"ok": True}
```

- [ ] **Step 6: Write `tests/conftest.py`**

```python
import os

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import get_session
from app.main import app
from app.models import Base

TEST_DATABASE_URL = os.environ.get(
    "TICKETD_TEST_DATABASE_URL",
    "postgresql+asyncpg://ticketd:ticketd@localhost:5432/ticketd_test",
)


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as s:
        yield s
    await engine.dispose()


@pytest_asyncio.fixture
async def client(session):
    async def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
```

`app.models.Base` doesn't exist yet — that's Task 2. This task ends here; it's validated by Task 2's first test import succeeding, not by a standalone test (there's nothing behavioral to test yet in scaffolding).

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml docker-compose.test.yml app/__init__.py app/config.py app/db.py app/main.py tests/__init__.py tests/conftest.py
git commit -m "chore: scaffold FastAPI project structure"
```

---

### Task 2: Data models and initial Postgres schema

**Files:**
- Create: `app/models.py`
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/script.py.mako`
- Create: `alembic/versions/0001_initial_schema.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Consumes: nothing new from Task 1 beyond `app.config.settings`.
- Produces: `app.models.Base` (declarative base), `app.models.Ticket`, `app.models.User`, `app.models.ResetToken`, `app.models.Notification` — field names exactly as listed below; every later task's endpoints and helpers depend on these names.

- [ ] **Step 1: Write `app/models.py`**

```python
import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    priority: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("priority IN ('low','med','high')", name="ck_tickets_priority"),
        CheckConstraint("status IN ('open','closed')", name="ck_tickets_status"),
    )


class ResetToken(Base):
    __tablename__ = "reset_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_ts: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_reset_tokens_email_created_ts", "email", "created_ts"),
    )


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    to_addr: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sent_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
```

- [ ] **Step 2: Write `tests/test_models.py`** (proves the schema round-trips on real Postgres before anything is built on top of it)

```python
import datetime

import pytest
from sqlalchemy import select

from app.models import Ticket


@pytest.mark.asyncio
async def test_ticket_round_trip(session):
    ticket = Ticket(
        title="Fix DB",
        slug="fix-db",
        priority="med",
        status="open",
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )
    session.add(ticket)
    await session.commit()

    result = await session.execute(select(Ticket).where(Ticket.slug == "fix-db"))
    fetched = result.scalar_one()
    assert fetched.title == "Fix DB"
    assert fetched.status == "open"


@pytest.mark.asyncio
async def test_duplicate_slug_rejected(session):
    from sqlalchemy.exc import IntegrityError

    now = datetime.datetime.now(datetime.timezone.utc)
    session.add(Ticket(title="Fix DB", slug="fix-db", priority="med", status="open", created_at=now))
    await session.commit()

    session.add(Ticket(title="fix db!", slug="fix-db", priority="med", status="open", created_at=now))
    with pytest.raises(IntegrityError):
        await session.commit()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_models.py -v`
Expected: FAIL — no Postgres schema exists yet (`relation "tickets" does not exist`), or collection error if `app/models.py` step wasn't done yet. Since Step 1 already created the models, this should fail specifically on missing tables, confirming the fixture correctly needs migrations applied.

- [ ] **Step 4: Set up Alembic and the initial migration**

Run: `alembic init alembic` (from repo root), then edit `alembic.ini` to point at `TICKETD_DATABASE_URL_SYNC` and edit `alembic/env.py`'s `target_metadata` to `app.models.Base.metadata`. Then generate and hand-verify the migration:

Run: `alembic revision --autogenerate -m "initial schema"`

Confirm `alembic/versions/0001_initial_schema.py` creates `users`, `tickets` (with the two check constraints and the slug unique constraint), `reset_tokens` (with the email/created_ts index and token_hash unique constraint), and `notifications`, matching `app/models.py` exactly.

- [ ] **Step 5: Apply the migration to the test DB and re-run tests**

Run: `TICKETD_DATABASE_URL_SYNC=postgresql+psycopg2://ticketd:ticketd@localhost:5432/ticketd_test alembic upgrade head`

Note: the `tests/conftest.py` `session` fixture uses `Base.metadata.create_all`/`drop_all` directly rather than Alembic, so tests don't actually require this migration to be applied first — but a human or CI running this task needs Alembic wired up correctly regardless, because it's what real deployments will use. Applying it here once is how Step 4's autogenerated migration gets hand-verified against a real DB before trusting it.

Run: `pytest tests/test_models.py -v`
Expected: PASS (both tests).

- [ ] **Step 6: Commit**

```bash
git add app/models.py alembic.ini alembic/ tests/test_models.py
git commit -m "feat: add Postgres schema for tickets, users, reset_tokens, notifications"
```

---

### Task 3: Collision-free slug generation

**Files:**
- Create: `app/slugs.py`
- Test: `tests/test_slugs.py`

**Interfaces:**
- Consumes: `app.models.Ticket` (Task 2).
- Produces: `app.slugs.base_slug(text: str) -> str`, `app.slugs.insert_ticket_with_unique_slug(session: AsyncSession, *, title: str, priority: str, status: str, created_at: datetime.datetime) -> Ticket`. Task 5 (`POST /api/tickets`) calls this directly instead of constructing `Ticket` itself.

- [ ] **Step 1: Write `tests/test_slugs.py`**

```python
import datetime

import pytest
from sqlalchemy import select

from app.models import Ticket
from app.slugs import base_slug, insert_ticket_with_unique_slug


def test_base_slug_matches_legacy_behavior():
    assert base_slug("Fix DB") == "fix-db"
    assert base_slug("fix db!") == "fix-db"
    assert base_slug("  Weird---Title!!") == "weird-title"
    assert base_slug("x" * 100) == ("x" * 64)


@pytest.mark.asyncio
async def test_no_collision_keeps_clean_slug(session):
    now = datetime.datetime.now(datetime.timezone.utc)
    ticket = await insert_ticket_with_unique_slug(
        session, title="Fix DB", priority="med", status="open", created_at=now
    )
    await session.commit()
    assert ticket.slug == "fix-db"


@pytest.mark.asyncio
async def test_collision_gets_numeric_suffix(session):
    now = datetime.datetime.now(datetime.timezone.utc)
    first = await insert_ticket_with_unique_slug(
        session, title="Fix DB", priority="med", status="open", created_at=now
    )
    await session.commit()
    second = await insert_ticket_with_unique_slug(
        session, title="fix db!", priority="med", status="open", created_at=now
    )
    await session.commit()

    assert first.slug == "fix-db"
    assert second.slug == "fix-db-2"

    result = await session.execute(select(Ticket.slug))
    slugs = {row[0] for row in result}
    assert slugs == {"fix-db", "fix-db-2"}


@pytest.mark.asyncio
async def test_three_way_collision(session):
    now = datetime.datetime.now(datetime.timezone.utc)
    titles = ["Fix DB", "fix db!", "FIX. DB"]
    slugs = []
    for title in titles:
        t = await insert_ticket_with_unique_slug(
            session, title=title, priority="med", status="open", created_at=now
        )
        await session.commit()
        slugs.append(t.slug)
    assert slugs == ["fix-db", "fix-db-2", "fix-db-3"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_slugs.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.slugs'`.

- [ ] **Step 3: Write `app/slugs.py`**

```python
import re
import secrets

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Ticket

MAX_SUFFIX_ATTEMPTS = 50


def base_slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:64]


async def insert_ticket_with_unique_slug(
    session: AsyncSession, *, title: str, priority: str, status: str, created_at
) -> Ticket:
    base = base_slug(title)

    for attempt in range(1, MAX_SUFFIX_ATTEMPTS + 1):
        candidate = base if attempt == 1 else f"{base}-{attempt}"
        ticket = Ticket(
            title=title, slug=candidate, priority=priority, status=status, created_at=created_at
        )
        try:
            async with session.begin_nested():
                session.add(ticket)
                await session.flush()
            return ticket
        except IntegrityError:
            continue

    # Collision-deep enough to exhaust numeric suffixes is not expected in
    # normal use; fall back to a random suffix rather than fail the request.
    candidate = f"{base}-{secrets.token_hex(3)}"
    ticket = Ticket(title=title, slug=candidate, priority=priority, status=status, created_at=created_at)
    async with session.begin_nested():
        session.add(ticket)
        await session.flush()
    return ticket
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_slugs.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add app/slugs.py tests/test_slugs.py
git commit -m "feat: collision-free slug generation with numeric-suffix retry"
```

---

### Task 4: `GET /api/tickets` and `GET /api/tickets/<id>`

**Files:**
- Create: `app/routers/__init__.py`
- Create: `app/routers/tickets.py`
- Modify: `app/main.py` (include the router)
- Test: `tests/test_tickets_read.py`

**Interfaces:**
- Consumes: `app.db.get_session`, `app.models.Ticket`.
- Produces: `app.routers.tickets.router` (an `APIRouter`), a `ticket_to_dict(ticket: Ticket) -> dict` helper reused by every ticket-returning endpoint in later tasks (Tasks 5, 7).

- [ ] **Step 1: Write `tests/test_tickets_read.py`**

```python
import datetime

import pytest

from app.models import Ticket


async def _make_ticket(session, **overrides):
    now = datetime.datetime.now(datetime.timezone.utc)
    defaults = dict(title="Sample", slug="sample", priority="med", status="open", created_at=now)
    defaults.update(overrides)
    ticket = Ticket(**defaults)
    session.add(ticket)
    await session.commit()
    await session.refresh(ticket)
    return ticket


@pytest.mark.asyncio
async def test_list_tickets_returns_plain_array_ordered_desc(client, session):
    older = await _make_ticket(
        session, title="Older", slug="older",
        created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
    )
    newer = await _make_ticket(
        session, title="Newer", slug="newer",
        created_at=datetime.datetime(2026, 2, 1, tzinfo=datetime.timezone.utc),
    )
    resp = await client.get("/api/tickets")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert [t["slug"] for t in body] == ["newer", "older"]


@pytest.mark.asyncio
async def test_list_tickets_status_filter(client, session):
    await _make_ticket(session, title="Open one", slug="open-one", status="open")
    await _make_ticket(session, title="Closed one", slug="closed-one", status="closed")
    resp = await client.get("/api/tickets", params={"status": "closed"})
    body = resp.json()
    assert [t["slug"] for t in body] == ["closed-one"]


@pytest.mark.asyncio
async def test_get_ticket_by_id_found(client, session):
    ticket = await _make_ticket(session, title="Found me", slug="found-me")
    resp = await client.get(f"/api/tickets/{ticket.id}")
    assert resp.status_code == 200
    assert resp.json()["slug"] == "found-me"


@pytest.mark.asyncio
async def test_get_ticket_by_id_missing_returns_200_empty_object(client):
    resp = await client.get("/api/tickets/999999")
    assert resp.status_code == 200
    assert resp.json() == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_tickets_read.py -v`
Expected: FAIL — `app.routers.tickets` doesn't exist, or 404s once routing is wired without handlers.

- [ ] **Step 3: Write `app/routers/tickets.py`**

```python
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Ticket

router = APIRouter()


def ticket_to_dict(ticket: Ticket) -> dict:
    return {
        "id": ticket.id,
        "title": ticket.title,
        "slug": ticket.slug,
        "priority": ticket.priority,
        "status": ticket.status,
        "assignee_id": ticket.assignee_id,
        "created_at": ticket.created_at.isoformat(),
        "closed_at": ticket.closed_at.isoformat() if ticket.closed_at else None,
    }


@router.get("/api/tickets")
async def list_tickets(status: str | None = None, session: AsyncSession = Depends(get_session)):
    query = select(Ticket).order_by(Ticket.created_at.desc())
    if status:
        query = query.where(Ticket.status == status)
    result = await session.execute(query)
    return [ticket_to_dict(t) for t in result.scalars()]


@router.get("/api/tickets/{ticket_id}")
async def get_ticket(ticket_id: int, session: AsyncSession = Depends(get_session)):
    ticket = await session.get(Ticket, ticket_id)
    if ticket is None:
        return {}
    return ticket_to_dict(ticket)
```

- [ ] **Step 4: Wire the router into `app/main.py`**

```python
from fastapi import FastAPI

from app.routers import tickets

app = FastAPI()
app.include_router(tickets.router)


@app.get("/healthz")
async def healthz():
    return {"ok": True}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_tickets_read.py -v`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add app/routers/__init__.py app/routers/tickets.py app/main.py tests/test_tickets_read.py
git commit -m "feat: port GET /api/tickets and GET /api/tickets/<id>"
```

---

### Task 5: `POST /api/tickets`

**Files:**
- Modify: `app/routers/tickets.py`
- Test: `tests/test_tickets_create.py`

**Interfaces:**
- Consumes: `app.slugs.insert_ticket_with_unique_slug` (Task 3), `ticket_to_dict` (Task 4).
- Produces: nothing new consumed elsewhere.

- [ ] **Step 1: Write `tests/test_tickets_create.py`**

```python
import pytest


@pytest.mark.asyncio
async def test_create_ticket_requires_title(client):
    resp = await client.post("/api/tickets", json={})
    assert resp.status_code == 422
    assert resp.json() == {"error": "title_required"}


@pytest.mark.asyncio
async def test_create_ticket_defaults_priority_med(client):
    resp = await client.post("/api/tickets", json={"title": "New ticket"})
    assert resp.status_code == 201
    body = resp.json()
    assert set(body.keys()) == {"id", "slug"}
    assert body["slug"] == "new-ticket"

    get_resp = await client.get(f"/api/tickets/{body['id']}")
    assert get_resp.json()["priority"] == "med"
    assert get_resp.json()["status"] == "open"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "input_priority,expected",
    [("low", "low"), ("med", "med"), ("high", "high"), ("1", "low"), ("2", "med"), ("3", "high")],
)
async def test_create_ticket_priority_accepts_int_or_string(client, input_priority, expected):
    resp = await client.post("/api/tickets", json={"title": "Prio test", "priority": input_priority})
    ticket_id = resp.json()["id"]
    get_resp = await client.get(f"/api/tickets/{ticket_id}")
    assert get_resp.json()["priority"] == expected


@pytest.mark.asyncio
async def test_create_ticket_colliding_titles_get_distinct_slugs(client):
    first = await client.post("/api/tickets", json={"title": "Fix DB"})
    second = await client.post("/api/tickets", json={"title": "fix db!"})
    assert first.json()["slug"] == "fix-db"
    assert second.json()["slug"] == "fix-db-2"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_tickets_create.py -v`
Expected: FAIL — `405 Method Not Allowed` (no POST handler yet).

- [ ] **Step 3: Add the create handler to `app/routers/tickets.py`**

```python
import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Ticket
from app.slugs import insert_ticket_with_unique_slug

router = APIRouter()

PRIORITY_CODE_MAP = {"1": "low", "2": "med", "3": "high"}


def ticket_to_dict(ticket: Ticket) -> dict:
    return {
        "id": ticket.id,
        "title": ticket.title,
        "slug": ticket.slug,
        "priority": ticket.priority,
        "status": ticket.status,
        "assignee_id": ticket.assignee_id,
        "created_at": ticket.created_at.isoformat(),
        "closed_at": ticket.closed_at.isoformat() if ticket.closed_at else None,
    }


@router.get("/api/tickets")
async def list_tickets(status: str | None = None, session: AsyncSession = Depends(get_session)):
    query = select(Ticket).order_by(Ticket.created_at.desc())
    if status:
        query = query.where(Ticket.status == status)
    result = await session.execute(query)
    return [ticket_to_dict(t) for t in result.scalars()]


@router.post("/api/tickets", status_code=201)
async def create_ticket(request: Request, session: AsyncSession = Depends(get_session)):
    body = await request.json() if await request.body() else {}
    title = (body.get("title") or "").strip()
    if not title:
        return JSONResponse({"error": "title_required"}, status_code=422)

    priority = str(body.get("priority", "med"))
    priority = PRIORITY_CODE_MAP.get(priority, priority)

    ticket = await insert_ticket_with_unique_slug(
        session,
        title=title,
        priority=priority,
        status="open",
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )
    await session.commit()
    return {"id": ticket.id, "slug": ticket.slug}


@router.get("/api/tickets/{ticket_id}")
async def get_ticket(ticket_id: int, session: AsyncSession = Depends(get_session)):
    ticket = await session.get(Ticket, ticket_id)
    if ticket is None:
        return {}
    return ticket_to_dict(ticket)
```

Note: route order matters in FastAPI only for path conflicts, not here — `/api/tickets` (POST) and `/api/tickets/{ticket_id}` (GET) don't overlap. Kept `GET /api/tickets/{ticket_id}` after `POST /api/tickets` for readability, matching the legacy file's route order.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_tickets_create.py tests/test_tickets_read.py -v`
Expected: PASS (all tests in both files).

- [ ] **Step 5: Commit**

```bash
git add app/routers/tickets.py tests/test_tickets_create.py
git commit -m "feat: port POST /api/tickets with priority normalization and collision-free slugs"
```

---

### Task 6: Notification outbox helper

**Files:**
- Create: `app/notifications.py`
- Test: `tests/test_notifications.py`

**Interfaces:**
- Consumes: `app.models.Notification`.
- Produces: `app.notifications.enqueue(session: AsyncSession, *, to_addr: str, body: str) -> Notification`. Tasks 7 and 9 call this instead of `send_mail()`.

- [ ] **Step 1: Write `tests/test_notifications.py`**

```python
import pytest
from sqlalchemy import select

from app.models import Notification
from app.notifications import enqueue


@pytest.mark.asyncio
async def test_enqueue_writes_unsent_row(session):
    await enqueue(session, to_addr="watchers@example.internal", body="closed: Fix DB")
    await session.commit()

    result = await session.execute(select(Notification))
    row = result.scalar_one()
    assert row.to_addr == "watchers@example.internal"
    assert row.body == "closed: Fix DB"
    assert row.sent_at is None
    assert row.attempts == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_notifications.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.notifications'`.

- [ ] **Step 3: Write `app/notifications.py`**

```python
import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notification


async def enqueue(session: AsyncSession, *, to_addr: str, body: str) -> Notification:
    notification = Notification(
        to_addr=to_addr,
        body=body,
        created_at=datetime.datetime.now(datetime.timezone.utc),
        attempts=0,
    )
    session.add(notification)
    await session.flush()
    return notification
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_notifications.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/notifications.py tests/test_notifications.py
git commit -m "feat: add notification outbox enqueue helper"
```

---

### Task 7: `POST /api/tickets/<id>/close`

**Files:**
- Modify: `app/routers/tickets.py`
- Test: `tests/test_tickets_close.py`

**Interfaces:**
- Consumes: `app.notifications.enqueue` (Task 6).

- [ ] **Step 1: Write `tests/test_tickets_close.py`**

```python
import datetime
import time

import pytest
from sqlalchemy import select

from app.models import Notification, Ticket


async def _make_open_ticket(session, title="To close", slug="to-close"):
    ticket = Ticket(
        title=title, slug=slug, priority="med", status="open",
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )
    session.add(ticket)
    await session.commit()
    await session.refresh(ticket)
    return ticket


@pytest.mark.asyncio
async def test_close_ticket_marks_closed_and_enqueues_notification(client, session):
    ticket = await _make_open_ticket(session)
    resp = await client.post(f"/api/tickets/{ticket.id}/close")
    assert resp.status_code == 200
    assert resp.json() == {"closed": True}

    await session.refresh(ticket)
    assert ticket.status == "closed"
    assert ticket.closed_at is not None

    result = await session.execute(select(Notification))
    notif = result.scalar_one()
    assert notif.to_addr == "watchers@example.internal"
    assert "To close" in notif.body
    assert notif.sent_at is None


@pytest.mark.asyncio
async def test_close_already_closed_ticket_is_noop(client, session):
    ticket = await _make_open_ticket(session)
    first = await client.post(f"/api/tickets/{ticket.id}/close")
    second = await client.post(f"/api/tickets/{ticket.id}/close")
    assert first.json() == {"closed": True}
    assert second.json() == {"closed": False}

    result = await session.execute(select(Notification))
    notifications = result.scalars().all()
    assert len(notifications) == 1


@pytest.mark.asyncio
async def test_close_returns_fast_regardless_of_smtp(client, session):
    ticket = await _make_open_ticket(session)
    start = time.monotonic()
    resp = await client.post(f"/api/tickets/{ticket.id}/close")
    elapsed = time.monotonic() - start
    assert resp.status_code == 200
    assert elapsed < 0.5  # no SMTP call happens in-request; this is generous for test-machine noise
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_tickets_close.py -v`
Expected: FAIL with `404 Not Found` (no close route yet).

- [ ] **Step 3: Add the close handler to `app/routers/tickets.py`** (add this function; imports gain `from app.notifications import enqueue` and `from app.config import settings`)

```python
@router.post("/api/tickets/{ticket_id}/close")
async def close_ticket(ticket_id: int, session: AsyncSession = Depends(get_session)):
    ticket = await session.get(Ticket, ticket_id)
    if ticket is None or ticket.status == "closed":
        return {"closed": False}

    ticket.status = "closed"
    ticket.closed_at = datetime.datetime.now(datetime.timezone.utc)
    await enqueue(session, to_addr=settings.watchers_addr, body=f"closed: {ticket.title}")
    await session.commit()
    return {"closed": True}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_tickets_close.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add app/routers/tickets.py tests/test_tickets_close.py
git commit -m "feat: port POST /api/tickets/<id>/close via notification outbox"
```

---

### Task 8: Reset token generation and hashing

**Files:**
- Create: `app/security.py`
- Test: `tests/test_security.py`

**Interfaces:**
- Produces: `app.security.generate_reset_token() -> str` (the raw, emailed token), `app.security.hash_token(raw: str) -> str` (sha256 hex digest, what's stored). Task 9 and Task 10 both depend on these exact names.

- [ ] **Step 1: Write `tests/test_security.py`**

```python
from app.security import generate_reset_token, hash_token


def test_generate_reset_token_is_long_and_random():
    a = generate_reset_token()
    b = generate_reset_token()
    assert a != b
    assert len(a) >= 32


def test_hash_token_is_deterministic_and_not_reversible_looking():
    raw = "abc123"
    h1 = hash_token(raw)
    h2 = hash_token(raw)
    assert h1 == h2
    assert h1 != raw
    assert len(h1) == 64  # sha256 hex digest length
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_security.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.security'`.

- [ ] **Step 3: Write `app/security.py`**

```python
import hashlib
import secrets


def generate_reset_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_security.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/security.py tests/test_security.py
git commit -m "feat: add reset token generation and hashing helpers"
```

---

### Task 9: `POST /api/auth/reset`

**Files:**
- Create: `app/routers/auth.py`
- Modify: `app/main.py` (include the router)
- Test: `tests/test_auth_reset.py`

**Interfaces:**
- Consumes: `app.security.generate_reset_token`, `app.security.hash_token` (Task 8), `app.notifications.enqueue` (Task 6), `app.models.ResetToken`.

- [ ] **Step 1: Write `tests/test_auth_reset.py`**

```python
import datetime

import pytest
from sqlalchemy import func, select

from app.models import Notification, ResetToken


@pytest.mark.asyncio
async def test_request_reset_creates_token_and_enqueues_email(client, session):
    resp = await client.post("/api/auth/reset", json={"email": "user@corp.example.com"})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    result = await session.execute(select(ResetToken))
    token_row = result.scalar_one()
    assert token_row.email == "user@corp.example.com"
    assert len(token_row.token_hash) == 64

    notif_result = await session.execute(select(Notification))
    notif = notif_result.scalar_one()
    assert notif.to_addr == "user@corp.example.com"


@pytest.mark.asyncio
async def test_request_reset_rate_limited_after_three_per_hour(client):
    email = "ratelimited@corp.example.com"
    for _ in range(3):
        resp = await client.post("/api/auth/reset", json={"email": email})
        assert resp.status_code == 200
    fourth = await client.post("/api/auth/reset", json={"email": email})
    assert fourth.status_code == 429
    assert fourth.json() == {"error": "rate_limited"}


@pytest.mark.asyncio
async def test_request_reset_bypass_header_skips_rate_limit(client):
    email = "bypassed@corp.example.com"
    for _ in range(3):
        await client.post("/api/auth/reset", json={"email": email})
    resp = await client.post(
        "/api/auth/reset", json={"email": email}, headers={"X-Internal-Bypass": "1"}
    )
    assert resp.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_auth_reset.py -v`
Expected: FAIL — route doesn't exist yet.

- [ ] **Step 3: Write `app/routers/auth.py`**

```python
import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.models import ResetToken
from app.notifications import enqueue
from app.security import generate_reset_token, hash_token

router = APIRouter()


@router.post("/api/auth/reset")
async def request_reset(request: Request, session: AsyncSession = Depends(get_session)):
    body = await request.json() if await request.body() else {}
    email = body.get("email", "")

    if request.headers.get("X-Internal-Bypass") != "1":
        now = datetime.datetime.now(datetime.timezone.utc)
        window_start = now - datetime.timedelta(hours=1)
        count_result = await session.execute(
            select(func.count()).select_from(ResetToken).where(
                ResetToken.email == email, ResetToken.created_ts > window_start
            )
        )
        if count_result.scalar_one() >= settings.rate_limit_per_hour:
            return JSONResponse({"error": "rate_limited"}, status_code=429)

    raw_token = generate_reset_token()
    now = datetime.datetime.now(datetime.timezone.utc)
    reset_token = ResetToken(
        email=email,
        token_hash=hash_token(raw_token),
        created_ts=now,
        expires_at=now + datetime.timedelta(minutes=settings.reset_window_min),
    )
    session.add(reset_token)
    await enqueue(session, to_addr=email, body=f"reset token: {raw_token}")
    await session.commit()
    return {"ok": True}
```

- [ ] **Step 4: Wire the router into `app/main.py`**

```python
from fastapi import FastAPI

from app.routers import auth, tickets

app = FastAPI()
app.include_router(tickets.router)
app.include_router(auth.router)


@app.get("/healthz")
async def healthz():
    return {"ok": True}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_auth_reset.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add app/routers/auth.py app/main.py tests/test_auth_reset.py
git commit -m "feat: port POST /api/auth/reset with hashed tokens and outbox email"
```

---

### Task 10: `POST /api/auth/reset/confirm`

**Files:**
- Modify: `app/routers/auth.py`
- Test: `tests/test_auth_confirm.py`

- [ ] **Step 1: Write `tests/test_auth_confirm.py`**

```python
import datetime

import pytest
from sqlalchemy import select

from app.models import ResetToken
from app.security import hash_token


async def _make_token(session, *, email="user@corp.example.com", minutes_old=0, raw="raw-token-value"):
    now = datetime.datetime.now(datetime.timezone.utc)
    created = now - datetime.timedelta(minutes=minutes_old)
    token = ResetToken(
        email=email,
        token_hash=hash_token(raw),
        created_ts=created,
        expires_at=created + datetime.timedelta(minutes=30),
    )
    session.add(token)
    await session.commit()
    return raw


@pytest.mark.asyncio
async def test_confirm_valid_token_succeeds_and_deletes_it(client, session):
    raw = await _make_token(session, email="user@corp.example.com")
    resp = await client.post("/api/auth/reset/confirm", json={"token": raw})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "email": "user@corp.example.com"}

    result = await session.execute(select(ResetToken))
    assert result.scalars().all() == []


@pytest.mark.asyncio
async def test_confirm_unknown_token_returns_invalid(client):
    resp = await client.post("/api/auth/reset/confirm", json={"token": "not-a-real-token"})
    assert resp.status_code == 403
    assert resp.json() == {"error": "invalid_token"}


@pytest.mark.asyncio
async def test_confirm_expired_token_returns_identical_body_to_invalid(client, session):
    raw = await _make_token(session, minutes_old=31)
    resp = await client.post("/api/auth/reset/confirm", json={"token": raw})
    assert resp.status_code == 403
    assert resp.json() == {"error": "invalid_token"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_auth_confirm.py -v`
Expected: FAIL — route doesn't exist yet.

- [ ] **Step 3: Add the confirm handler to `app/routers/auth.py`** (append; imports gain nothing new beyond what Task 9 already imports)

```python
@router.post("/api/auth/reset/confirm")
async def confirm_reset(request: Request, session: AsyncSession = Depends(get_session)):
    body = await request.json() if await request.body() else {}
    token = body.get("token", "")
    token_hash = hash_token(token)

    result = await session.execute(select(ResetToken).where(ResetToken.token_hash == token_hash))
    row = result.scalar_one_or_none()

    now = datetime.datetime.now(datetime.timezone.utc)
    if row is None or now > row.expires_at:
        return JSONResponse({"error": "invalid_token"}, status_code=403)

    email = row.email
    await session.delete(row)
    await session.commit()
    return {"ok": True, "email": email}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_auth_confirm.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add app/routers/auth.py tests/test_auth_confirm.py
git commit -m "feat: port POST /api/auth/reset/confirm with hashed-token lookup"
```

---

### Task 11: `GET /internal/export/csv`

**Files:**
- Create: `app/routers/export.py`
- Modify: `app/main.py` (include the router)
- Test: `tests/test_export.py`

- [ ] **Step 1: Write `tests/test_export.py`**

```python
import datetime

import pytest

from app.models import Ticket


@pytest.mark.asyncio
async def test_export_csv_matches_legacy_format(client, session):
    now = datetime.datetime.now(datetime.timezone.utc)
    session.add(Ticket(title="Alpha", slug="alpha", priority="med", status="open", created_at=now))
    session.add(Ticket(title="Beta", slug="beta", priority="high", status="closed", created_at=now))
    await session.commit()

    resp = await client.get("/internal/export/csv")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    lines = resp.text.strip().split("\n")
    assert lines[0] == "id,title,status"
    assert "Alpha,open" in lines[1] or "Alpha,open" in lines[2]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_export.py -v`
Expected: FAIL — route doesn't exist yet.

- [ ] **Step 3: Write `app/routers/export.py`** (deliberately unchanged output format — see spec §4, this endpoint is carried forward as-is, not improved)

```python
from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Ticket

router = APIRouter()


@router.get("/internal/export/csv")
async def export_csv(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Ticket))
    rows = result.scalars().all()
    lines = ["id,title,status"] + [f"{t.id},{t.title},{t.status}" for t in rows]
    return PlainTextResponse("\n".join(lines), media_type="text/csv")
```

- [ ] **Step 4: Wire the router into `app/main.py`**

```python
from fastapi import FastAPI

from app.routers import auth, export, tickets

app = FastAPI()
app.include_router(tickets.router)
app.include_router(auth.router)
app.include_router(export.router)


@app.get("/healthz")
async def healthz():
    return {"ok": True}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_export.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/routers/export.py app/main.py tests/test_export.py
git commit -m "feat: port GET /internal/export/csv unchanged"
```

---

### Task 12: Notification worker (sync SMTP sender with retry/backoff)

**Files:**
- Create: `app/worker.py`
- Test: `tests/test_worker.py`

**Interfaces:**
- Consumes: `app.models.Notification`, `app.config.settings`.
- Produces: `app.worker.send_pending(engine, smtp_client_factory, *, max_attempts=5) -> int` (returns count of notifications successfully sent in one pass — the unit under test; `app.worker.run_forever()` wraps it in a poll loop for production use and is not itself unit-tested).

The worker is intentionally **synchronous** (plain SQLAlchemy + psycopg2, no asyncio, no async SMTP library) — it's a single-purpose poll loop with no concurrency requirement, and `smtplib` is sync anyway. Keeping it synchronous avoids adding an async SMTP dependency for no benefit.

- [ ] **Step 1: Write `tests/test_worker.py`**

```python
import datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models import Base, Notification
from app.worker import send_pending


class FakeSMTPSuccess:
    def __init__(self):
        self.sent = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def sendmail(self, from_addr, to_addrs, body):
        self.sent.append((from_addr, to_addrs, body))


class FakeSMTPAlwaysFails:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def sendmail(self, from_addr, to_addrs, body):
        raise ConnectionRefusedError("smtp.internal unreachable")


def _sync_test_engine():
    # Local, file-backed SQLite is fine for the worker's own unit tests —
    # the worker's logic is DB-shape-agnostic (plain SQLAlchemy Core
    # queries), so it doesn't need Postgres to verify send/retry behavior.
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


def test_send_pending_marks_sent_on_success():
    engine = _sync_test_engine()
    with Session(engine) as session:
        session.add(Notification(
            to_addr="watchers@example.internal", body="closed: X",
            created_at=datetime.datetime.now(datetime.timezone.utc), attempts=0,
        ))
        session.commit()

    sent_count = send_pending(engine, lambda: FakeSMTPSuccess())
    assert sent_count == 1

    with Session(engine) as session:
        row = session.execute(select(Notification)).scalar_one()
        assert row.sent_at is not None
        assert row.attempts == 1


def test_send_pending_records_failure_and_leaves_unsent():
    engine = _sync_test_engine()
    with Session(engine) as session:
        session.add(Notification(
            to_addr="watchers@example.internal", body="closed: X",
            created_at=datetime.datetime.now(datetime.timezone.utc), attempts=0,
        ))
        session.commit()

    sent_count = send_pending(engine, lambda: FakeSMTPAlwaysFails())
    assert sent_count == 0

    with Session(engine) as session:
        row = session.execute(select(Notification)).scalar_one()
        assert row.sent_at is None
        assert row.attempts == 1
        assert "unreachable" in row.last_error


def test_send_pending_gives_up_after_max_attempts():
    engine = _sync_test_engine()
    with Session(engine) as session:
        session.add(Notification(
            to_addr="watchers@example.internal", body="closed: X",
            created_at=datetime.datetime.now(datetime.timezone.utc), attempts=4,
        ))
        session.commit()

    sent_count = send_pending(engine, lambda: FakeSMTPAlwaysFails(), max_attempts=5)
    assert sent_count == 0

    with Session(engine) as session:
        row = session.execute(select(Notification)).scalar_one()
        assert row.attempts == 5

    # A second pass must not pick this row up again — it's exhausted attempts.
    sent_count_again = send_pending(engine, lambda: FakeSMTPAlwaysFails(), max_attempts=5)
    assert sent_count_again == 0
    with Session(engine) as session:
        row = session.execute(select(Notification)).scalar_one()
        assert row.attempts == 5  # unchanged — not retried past the cap
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_worker.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.worker'`.

- [ ] **Step 3: Write `app/worker.py`**

```python
import datetime
import smtplib
import time

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Notification


def _real_smtp_client():
    return smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout)


def send_pending(engine, smtp_client_factory=_real_smtp_client, *, max_attempts: int = 5) -> int:
    """One poll pass: send every notification that hasn't exceeded max_attempts. Returns count sent."""
    sent_count = 0
    with Session(engine) as session:
        pending = session.execute(
            select(Notification).where(
                Notification.sent_at.is_(None), Notification.attempts < max_attempts
            )
        ).scalars().all()

        for notification in pending:
            try:
                with smtp_client_factory() as smtp:
                    smtp.sendmail(settings.notify_from, [notification.to_addr], notification.body)
                notification.sent_at = datetime.datetime.now(datetime.timezone.utc)
                notification.attempts += 1
                notification.last_error = None
                sent_count += 1
            except Exception as exc:  # noqa: BLE001 — any SMTP failure is a retryable failure here
                notification.attempts += 1
                notification.last_error = str(exc)
            session.commit()

    return sent_count


def run_forever(poll_interval_seconds: float = 5.0):
    engine = create_engine(settings.database_url_sync, pool_pre_ping=True)
    while True:
        send_pending(engine)
        time.sleep(poll_interval_seconds)


if __name__ == "__main__":
    run_forever()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_worker.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add app/worker.py tests/test_worker.py
git commit -m "feat: add notification worker with backoff-free bounded retry"
```

---

### Task 13: SMTP-outage regression test (the actual incident this rewrite fixes)

**Files:**
- Test: `tests/test_smtp_outage_regression.py`

This is the direct regression test for the June incident: assert that closing a ticket (and requesting a reset) never blocks on SMTP being down, end to end — not just that the worker's own unit tests pass, but that the *request path* genuinely never touches SMTP.

- [ ] **Step 1: Write `tests/test_smtp_outage_regression.py`**

```python
import datetime
import time
from unittest.mock import patch

import pytest

from app.models import Ticket


async def _make_open_ticket(session):
    ticket = Ticket(
        title="Outage test", slug="outage-test", priority="med", status="open",
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )
    session.add(ticket)
    await session.commit()
    await session.refresh(ticket)
    return ticket


@pytest.mark.asyncio
async def test_close_ticket_never_imports_or_calls_smtplib(client, session):
    ticket = await _make_open_ticket(session)

    with patch("smtplib.SMTP") as mock_smtp:
        start = time.monotonic()
        resp = await client.post(f"/api/tickets/{ticket.id}/close")
        elapsed = time.monotonic() - start

    assert resp.status_code == 200
    assert resp.json() == {"closed": True}
    assert elapsed < 0.5
    mock_smtp.assert_not_called()  # the regression: this used to be called synchronously here


@pytest.mark.asyncio
async def test_request_reset_never_calls_smtp_even_if_smtp_host_is_unreachable(client):
    with patch("smtplib.SMTP") as mock_smtp:
        resp = await client.post("/api/auth/reset", json={"email": "user@corp.example.com"})

    assert resp.status_code == 200
    mock_smtp.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_smtp_outage_regression.py -v`
Expected: if Tasks 7 and 9 were implemented correctly, this should already PASS — there's no code path in either handler that touches `smtplib`. Run it anyway as the explicit regression check; if it fails, it means something in Task 7 or 9 regressed back to a synchronous call and must be fixed before continuing.

- [ ] **Step 3: Run to confirm pass**

Run: `pytest tests/test_smtp_outage_regression.py -v`
Expected: PASS (2 tests).

- [ ] **Step 4: Commit**

```bash
git add tests/test_smtp_outage_regression.py
git commit -m "test: add explicit regression test for synchronous-SMTP-in-request incident"
```

---

### Task 14: SQLite → Postgres data migration script

**Files:**
- Create: `ops/migrate_sqlite_to_postgres.py`
- Test: `tests/test_migration.py`

**Interfaces:**
- Produces: `ops.migrate_sqlite_to_postgres.migrate(sqlite_path: str, pg_engine) -> dict` returning `{"users": n, "tickets": n, "collisions_resolved": n}`.

- [ ] **Step 1: Write `tests/test_migration.py`**

```python
import sqlite3
import tempfile
import os

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models import Base, Ticket, User
from ops.migrate_sqlite_to_postgres import migrate


def _make_legacy_sqlite(path):
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE tickets (
            id INTEGER PRIMARY KEY, title TEXT NOT NULL, slug TEXT NOT NULL,
            priority TEXT, status TEXT NOT NULL, assignee_id INTEGER,
            created_at TEXT NOT NULL, closed_at TEXT
        )
    """)
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT NOT NULL, name TEXT NOT NULL)")
    conn.execute(
        "INSERT INTO tickets (id, title, slug, priority, status, created_at) VALUES "
        "(1, 'Fix DB', 'fix-db', 'med', 'open', '2026-01-01T10:00:00'),"
        "(2, 'fix db!', 'fix-db', 'high', 'closed', '2026-01-02T10:00:00')"
    )
    conn.execute("INSERT INTO users (id, email, name) VALUES (1, 'a@corp.example.com', 'Alice')")
    conn.commit()
    conn.close()


def test_migrate_copies_rows_and_deduplicates_slugs():
    with tempfile.TemporaryDirectory() as tmp:
        sqlite_path = os.path.join(tmp, "legacy.sqlite3")
        _make_legacy_sqlite(sqlite_path)

        pg_engine = create_engine("sqlite:///:memory:")  # stand-in target DB for this unit test
        Base.metadata.create_all(pg_engine)

        summary = migrate(sqlite_path, pg_engine)

        assert summary == {"users": 1, "tickets": 2, "collisions_resolved": 1}

        with Session(pg_engine) as session:
            slugs = sorted(t.slug for t in session.execute(select(Ticket)).scalars())
            assert slugs == ["fix-db", "fix-db-2"]
            users = session.execute(select(User)).scalars().all()
            assert len(users) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_migration.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ops.migrate_sqlite_to_postgres'`.

- [ ] **Step 3: Write `ops/migrate_sqlite_to_postgres.py`**

```python
import datetime
import sqlite3

from sqlalchemy.orm import Session

from app.models import Ticket, User
from app.slugs import base_slug


def _parse_naive_local(value: str) -> datetime.datetime:
    # Legacy timestamps are naive-local (app/server.py used datetime.now()
    # with no tzinfo). Per spec §9, treat them as the migration host's local
    # time and normalize explicitly to UTC rather than assuming UTC.
    naive = datetime.datetime.fromisoformat(value)
    local = naive.astimezone()  # attaches the host's local tzinfo
    return local.astimezone(datetime.timezone.utc)


def migrate(sqlite_path: str, pg_engine) -> dict:
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row

    users = conn.execute("SELECT * FROM users ORDER BY id").fetchall()
    tickets = conn.execute("SELECT * FROM tickets ORDER BY id").fetchall()
    conn.close()

    collisions_resolved = 0
    seen_slugs = set()

    with Session(pg_engine) as session:
        for u in users:
            session.add(User(id=u["id"], email=u["email"], name=u["name"]))

        for t in tickets:
            slug = t["slug"]
            base = base_slug(t["title"])
            candidate = slug
            suffix = 2
            while candidate in seen_slugs:
                candidate = f"{base}-{suffix}"
                suffix += 1
                collisions_resolved += 1
            seen_slugs.add(candidate)

            session.add(Ticket(
                id=t["id"],
                title=t["title"],
                slug=candidate,
                priority=t["priority"],
                status=t["status"],
                assignee_id=t["assignee_id"],
                created_at=_parse_naive_local(t["created_at"]),
                closed_at=_parse_naive_local(t["closed_at"]) if t["closed_at"] else None,
            ))

        session.commit()

    return {"users": len(users), "tickets": len(tickets), "collisions_resolved": collisions_resolved}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_migration.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ops/migrate_sqlite_to_postgres.py tests/test_migration.py
git commit -m "feat: add SQLite-to-Postgres migration script with deterministic slug de-collision"
```

---

### Task 15: Access-log replay smoke script

**Files:**
- Create: `ops/verify/replay_access_log.py`

This is a smoke test, not a load test (spec §3 — the log's true shape is a 33-minute single-user sample, not real 30-day traffic; don't read anything into timing from it). It replays every logged request pattern against a running instance of the new API and reports any that don't get a handled (non-5xx-crash, non-connection-error) response — the point is API-shape coverage, not performance.

- [ ] **Step 1: Write `ops/verify/replay_access_log.py`**

```python
"""Replay ops/access.log request patterns against a running ticketd instance.

Usage: python -m ops.verify.replay_access_log --base-url http://localhost:8000

This is a shape-compatibility smoke check, not a load test — see spec §3 for
why ops/access.log's actual traffic-volume signal can't be trusted.
"""
import argparse
import re
import sys

import httpx

LOG_LINE_RE = re.compile(
    r'^(?P<ip>\S+) - (?P<user>\S+) \[(?P<ts>[^\]]+)\] '
    r'"(?P<method>\S+) (?P<path>\S+) \S+" (?P<status>\d+) (?P<size>\S+) '
    r'"(?P<referrer>[^"]*)" "(?P<ua>[^"]*)" (?P<duration>\S+)$'
)

TICKET_ID_RE = re.compile(r"^/api/tickets/(\d+)$")
CLOSE_RE = re.compile(r"^/api/tickets/(\d+)/close$")


def normalize_path(path: str) -> str:
    if TICKET_ID_RE.match(path):
        return "/api/tickets/1"  # any existing or missing id is a valid shape check either way
    if CLOSE_RE.match(path):
        return "/api/tickets/1/close"
    return path


def replay(log_path: str, base_url: str) -> tuple[int, int]:
    ok, failed = 0, 0
    with open(log_path) as f, httpx.Client(base_url=base_url, timeout=10.0) as client:
        for line in f:
            match = LOG_LINE_RE.match(line.strip())
            if not match:
                continue
            method = match.group("method")
            path = normalize_path(match.group("path"))
            try:
                if method == "GET":
                    resp = client.get(path)
                elif method == "POST":
                    resp = client.post(path, json={})
                else:
                    continue
            except httpx.HTTPError as exc:
                print(f"CONNECTION FAILURE {method} {path}: {exc}", file=sys.stderr)
                failed += 1
                continue

            if resp.status_code >= 500:
                print(f"SERVER ERROR {method} {path}: {resp.status_code}", file=sys.stderr)
                failed += 1
            else:
                ok += 1
    return ok, failed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--log-path", default="ops/access.log")
    args = parser.parse_args()

    ok, failed = replay(args.log_path, args.base_url)
    print(f"replayed: {ok} ok, {failed} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Manual verification (not a pytest — needs a live server)**

Run: `uvicorn app.main:app &`, then `python -m ops.verify.replay_access_log --base-url http://localhost:8000`
Expected: `replayed: 2000 ok, 0 failed` (every path pattern in the sample log gets a non-5xx response — `POST` bodies are empty `{}` so `create_ticket`/`reset` calls will hit the `422`/whatever-empty-body path, which is fine, that's still a "handled" response, not a crash).

This task has no automated pytest because it requires a live server process; it's meant to be run manually or wired into a CI smoke-test stage per the verification doc.

- [ ] **Step 3: Commit**

```bash
git add ops/verify/replay_access_log.py
git commit -m "chore: add access-log replay smoke script"
```

---

### Task 16: Full-stack self-review pass

**Files:** none new — this is a review task, not an implementation task.

- [ ] **Step 1:** Run the entire test suite: `pytest -v`. Expected: all tests from Tasks 1–15 pass.
- [ ] **Step 2:** Re-read spec §4 (API Compatibility Contract) line by line against the implemented routers (`app/routers/tickets.py`, `app/routers/auth.py`, `app/routers/export.py`). Confirm every documented quirk has a corresponding test (it should, per Tasks 4/5/7/9/10/11) and matches the spec's exact wording — status codes, exact error bodies, exact success bodies.
- [ ] **Step 3:** Confirm no file under `app/` imports `smtplib` or `flask` (`grep -rn "import smtplib\|import flask" app/` should only match `app/worker.py`, which is the one place SMTP is allowed to live).
- [ ] **Step 4:** Deployment packaging (Dockerfile/systemd unit/whatever) is intentionally not a task in this plan — see spec Open Question 6. Confirm with a human what convention the team already uses elsewhere before inventing one.
- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "chore: ticketd rewrite complete, all spec §4 routes covered by tests"
```

---

## Execution Handoff

Two execution options for whoever picks this plan up:

1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks. Requires `superpowers:subagent-driven-development`.
2. **Inline Execution** — execute tasks in one session with checkpoints. Requires `superpowers:executing-plans`.

Either way, read `docs/superpowers/verification/2026-08-09-ticketd-rewrite-verification.md` before starting Task 1 — it covers how to stand up the test Postgres instance these tasks assume exists.
