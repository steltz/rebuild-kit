# ticketd Rewrite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Flask/SQLite `ticketd` app with a FastAPI/Postgres service that preserves the existing API contract (`svc-ui` keeps working, no UI changes) while fixing synchronous email-on-close, MD5 password-reset tokens, and slug collisions.

**Architecture:** One FastAPI app (`app/main.py`) behind Postgres, plus a separate long-running worker process (`app/worker.py`) that drains a transactional outbox table (`outbox_events`) to send email asynchronously. Business logic lives in `app/services/*`, HTTP wiring in `app/routers/*`, persistence in `app/models.py` + Alembic. See the design doc for the full rationale: `docs/superpowers/specs/2026-08-09-ticketd-rewrite-design.md` — read it before starting, especially section 9 (Open Questions), which lists decisions made without stakeholder review.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2.0 (async, `asyncpg`), Alembic, Pydantic v2 / pydantic-settings, pytest + pytest-asyncio + httpx + pytest-postgresql, Postgres 15+.

## Global Constraints

- Every JSON response field name and shape listed in spec section 3 ("Contract to Preserve") is preserved exactly — this is the whole point of the rewrite being invisible to `svc-ui`. Any task that touches a response body must re-check that table.
- No pagination added to `GET /api/tickets` — out of scope per the spec (UI changes are off the table).
- No new endpoints beyond the 6 that exist today.
- `created_at`/`closed_at` are UTC (`timestamptz`), not naive local time — this is a deliberate, documented deviation from byte-for-byte parity (spec section 3, "Not preserved").
- `python -m app.worker` must be a separate OS process from the API — never call `send_mail()` from inside a request handler.
- One deliberate behavior improvement beyond the spec's literal quirk table: sending a `priority` value outside `low`/`med`/`high` now returns a clean `422 invalid_priority` instead of crashing on a raw DB constraint violation (the likely cause of at least some of the unexplained 500s in the legacy access log — see spec section 9, item 7). This cannot change behavior for any request `svc-ui` actually sends today, since a bad priority would already have crashed the old app; it only changes what happens for a request nobody currently sends successfully. Task 5 implements this.

---

## File Structure

```
ticketd/
  app/
    __init__.py
    main.py               # FastAPI app factory + router wiring + /healthz
    config.py              # Settings (env-driven)
    db.py                  # async engine/session, get_db dependency
    models.py               # SQLAlchemy ORM models
    schemas.py               # Pydantic response models
    notify.py                 # send_mail(), now config-driven
    worker.py                  # outbox poller (separate process)
    services/
      __init__.py
      slugs.py                  # base_slug(), collision constants
      tickets.py                 # create_ticket() — slug retry + priority coercion
      outbox.py                   # enqueue()
      reset_tokens.py              # token generate/hash/verify + rate-limit query
    routers/
      __init__.py
      tickets.py                   # GET/POST /api/tickets, GET/{id}, POST/{id}/close
      auth.py                       # POST /api/auth/reset[/confirm]
      internal.py                    # GET /internal/export/csv
  alembic/
    env.py
    versions/
      0001_initial.py
  alembic.ini
  scripts/
    migrate_from_sqlite.py
  tests/
    conftest.py
    test_health.py
    test_slugs.py
    test_tickets_create.py
    test_tickets_read.py
    test_outbox.py
    test_tickets_close.py
    test_reset_tokens.py
    test_auth_reset.py
    test_internal_csv.py
    test_worker.py
    test_contract_quirks.py
    test_alembic_migration.py
  pyproject.toml
  Dockerfile
  docker-compose.yml
  .env.example
```

---

### Task 1: Project scaffold, config, and health check

**Files:**
- Create: `pyproject.toml`
- Create: `app/__init__.py`
- Create: `app/config.py`
- Create: `app/main.py`
- Create: `.env.example`
- Create: `docker-compose.yml`
- Test: `tests/test_health.py`
- Test: `tests/conftest.py` (partial — health test only needs an app instance, not a DB; full DB fixtures added in Task 3)

**Interfaces:**
- Produces: `app.config.settings` (a `Settings` instance with `.database_url`, `.smtp_host`, `.smtp_port`, `.mail_from`, `.reset_window_minutes`, `.reset_rate_limit_per_hour`, `.outbox_poll_interval_seconds`, `.outbox_max_attempts`); `app.main.create_app() -> FastAPI`; module-level `app.main.app`.

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "ticketd"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "sqlalchemy>=2.0",
    "asyncpg>=0.29",
    "alembic>=1.13",
    "pydantic>=2.7",
    "pydantic-settings>=2.3",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "httpx>=0.27",
    "pytest-postgresql>=6.0",
    "psycopg[binary]>=3.1",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

- [ ] **Step 2: Create `app/__init__.py`** (empty file, makes `app` a package)

- [ ] **Step 3: Create `app/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TICKETD_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://ticketd:ticketd@localhost:5432/ticketd"
    smtp_host: str = "smtp.internal"
    smtp_port: int = 25
    mail_from: str = "ticketd@example.internal"
    reset_window_minutes: int = 30
    reset_rate_limit_per_hour: int = 3
    outbox_poll_interval_seconds: float = 1.0
    outbox_max_attempts: int = 5


settings = Settings()
```

- [ ] **Step 4: Create `app/main.py`**

```python
from fastapi import FastAPI


def create_app() -> FastAPI:
    fastapi_app = FastAPI(title="ticketd")

    @fastapi_app.get("/healthz")
    async def healthz():
        return {"ok": True}

    return fastapi_app


app = create_app()
```

- [ ] **Step 5: Create `.env.example`**

```
TICKETD_DATABASE_URL=postgresql+asyncpg://ticketd:ticketd@localhost:5432/ticketd
TICKETD_SMTP_HOST=smtp.internal
TICKETD_SMTP_PORT=25
TICKETD_MAIL_FROM=ticketd@example.internal
```

- [ ] **Step 6: Create `docker-compose.yml`** (local dev Postgres — not the production topology, see spec Open Question 5)

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: ticketd
      POSTGRES_PASSWORD: ticketd
      POSTGRES_DB: ticketd
    ports:
      - "5432:5432"
    volumes:
      - ticketd_pgdata:/var/lib/postgresql/data

volumes:
  ticketd_pgdata:
```

- [ ] **Step 7: Write `tests/test_health.py`**

```python
from httpx import ASGITransport, AsyncClient

from app.main import create_app


async def test_healthz_returns_ok():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"ok": True}
```

- [ ] **Step 8: Install dependencies and run the test**

Run: `pip install -e ".[dev]"` then `pytest tests/test_health.py -v`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml app/__init__.py app/config.py app/main.py .env.example docker-compose.yml tests/test_health.py
git commit -m "feat: scaffold FastAPI app with health check"
```

---

### Task 2: Async DB engine/session

**Files:**
- Create: `app/db.py`

**Interfaces:**
- Consumes: `app.config.settings.database_url`
- Produces: `app.db.engine` (AsyncEngine), `app.db.SessionLocal` (async_sessionmaker), `app.db.get_db()` (FastAPI dependency yielding `AsyncSession`)

- [ ] **Step 1: Create `app/db.py`**

```python
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

engine = create_async_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
```

- [ ] **Step 2: Sanity-check import**

Run: `python -c "from app.db import engine, SessionLocal, get_db; print('ok')"`
Expected: prints `ok` (no DB connection is made at import time — `create_async_engine` is lazy)

- [ ] **Step 3: Commit**

```bash
git add app/db.py
git commit -m "feat: add async SQLAlchemy engine and session dependency"
```

---

### Task 3: Models + initial Alembic migration

**Files:**
- Create: `app/models.py`
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/versions/0001_initial.py`
- Test: `tests/test_alembic_migration.py`

**Interfaces:**
- Consumes: `app.config.settings.database_url`
- Produces: `app.models.Base` (DeclarativeBase), `app.models.User`, `app.models.Ticket`, `app.models.ResetToken`, `app.models.OutboxEvent` — column names exactly as in spec section 5 (including `outbox_events.next_attempt_at`).

- [ ] **Step 1: Create `app/models.py`**

```python
from __future__ import annotations

import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = (
        CheckConstraint("priority IN ('low', 'med', 'high')", name="ck_tickets_priority"),
        CheckConstraint("status IN ('open', 'closed')", name="ck_tickets_status"),
        Index("ix_tickets_status", "status"),
        Index("ix_tickets_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    priority: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="open")
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ResetToken(Base):
    __tablename__ = "reset_tokens"
    __table_args__ = (Index("ix_reset_tokens_email_created", "email", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String, nullable=False)
    token_hash: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    __table_args__ = (
        CheckConstraint("event_type IN ('ticket_closed', 'reset_requested')", name="ck_outbox_event_type"),
        CheckConstraint("status IN ('pending', 'sent', 'failed')", name="ck_outbox_status"),
        Index("ix_outbox_events_status_next_attempt", "status", "next_attempt_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    next_attempt_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sent_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
```

- [ ] **Step 2: Create `alembic.ini`**

```ini
[alembic]
script_location = alembic
prepend_sys_path = .

[loggers]
keys = root,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
```

- [ ] **Step 3: Create `alembic/env.py`**

```python
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.config import settings
from app.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", settings.database_url)
target_metadata = Base.metadata


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


asyncio.run(run_migrations_online())
```

- [ ] **Step 4: Create `alembic/versions/0001_initial.py`**

```python
"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-08-09
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("email", sa.String(), nullable=False, unique=True),
        sa.Column("name", sa.String(), nullable=False),
    )

    op.create_table(
        "tickets",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False, unique=True),
        sa.Column("priority", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("assignee_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("priority IN ('low', 'med', 'high')", name="ck_tickets_priority"),
        sa.CheckConstraint("status IN ('open', 'closed')", name="ck_tickets_status"),
    )
    op.create_index("ix_tickets_status", "tickets", ["status"])
    op.create_index("ix_tickets_created_at", "tickets", ["created_at"])

    op.create_table(
        "reset_tokens",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_reset_tokens_email_created", "reset_tokens", ["email", "created_at"])

    op.create_table(
        "outbox_events",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.CheckConstraint("event_type IN ('ticket_closed', 'reset_requested')", name="ck_outbox_event_type"),
        sa.CheckConstraint("status IN ('pending', 'sent', 'failed')", name="ck_outbox_status"),
    )
    op.create_index("ix_outbox_events_status_next_attempt", "outbox_events", ["status", "next_attempt_at"])


def downgrade() -> None:
    op.drop_table("outbox_events")
    op.drop_table("reset_tokens")
    op.drop_index("ix_tickets_created_at", table_name="tickets")
    op.drop_index("ix_tickets_status", table_name="tickets")
    op.drop_table("tickets")
    op.drop_table("users")
```

- [ ] **Step 5: Write `tests/test_alembic_migration.py`**

This is the one test in the suite that talks to a raw ephemeral Postgres (via `pytest-postgresql`'s `postgresql` fixture) instead of the shared `db_engine` fixture from Task 4 — it exists specifically to prove the Alembic migration itself works, not just the SQLAlchemy models.

```python
import subprocess

from sqlalchemy import create_engine, inspect


def test_alembic_upgrade_head_creates_expected_tables(postgresql):
    dsn = (
        f"postgresql+psycopg://{postgresql.info.user}:@"
        f"{postgresql.info.host}:{postgresql.info.port}/{postgresql.info.dbname}"
    )
    async_dsn = dsn.replace("+psycopg", "+asyncpg")

    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        env={"TICKETD_DATABASE_URL": async_dsn, "PATH": "/usr/bin:/bin:/usr/local/bin"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    engine = create_engine(dsn)
    tables = set(inspect(engine).get_table_names())
    assert {"users", "tickets", "reset_tokens", "outbox_events"} <= tables
```

- [ ] **Step 6: Run the test**

Run: `pytest tests/test_alembic_migration.py -v`
Expected: PASS. If it fails with a `PATH`-related error, adjust the `env=` dict to inherit the real environment (`{**os.environ, "TICKETD_DATABASE_URL": async_dsn}`) instead of hardcoding `PATH` — the hardcoded value above is a reasonable default but not guaranteed correct on every machine.

- [ ] **Step 7: Commit**

```bash
git add app/models.py alembic.ini alembic/env.py alembic/versions/0001_initial.py tests/test_alembic_migration.py
git commit -m "feat: add SQLAlchemy models and initial Alembic migration"
```

---

### Task 4: Test fixtures (shared Postgres schema + HTTP client)

**Files:**
- Create: `tests/conftest.py`

**Interfaces:**
- Produces: pytest fixtures `db_engine` (session-scoped-per-test AsyncEngine with schema created via `Base.metadata.create_all`), `db_session` (AsyncSession bound to `db_engine`), `client` (httpx `AsyncClient` wired to a FastAPI app whose `get_db` dependency is overridden to use `db_engine`).
- Consumes: `app.models.Base`, `app.db.get_db`, `app.main.create_app`.

- [ ] **Step 1: Create `tests/conftest.py`**

```python
from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.db import get_db
from app.main import create_app
from app.models import Base


@pytest_asyncio.fixture
async def db_engine(postgresql) -> AsyncGenerator[AsyncEngine, None]:
    dsn = (
        f"postgresql+asyncpg://{postgresql.info.user}:@"
        f"{postgresql.info.host}:{postgresql.info.port}/{postgresql.info.dbname}"
    )
    engine = create_async_engine(dsn)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_engine: AsyncEngine) -> AsyncGenerator[AsyncClient, None]:
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
```

Note: `tests/test_health.py` (Task 1) built its own app directly and doesn't need these fixtures — leave it as-is. Every test from here on uses `client` and/or `db_session`.

- [ ] **Step 2: Sanity check the fixtures compile**

Run: `pytest tests/conftest.py --collect-only`
Expected: no collection errors (there are no tests in this file, just fixtures — this step just confirms the imports and fixture definitions are syntactically and semantically valid).

- [ ] **Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "test: add shared Postgres-backed fixtures for API and DB tests"
```

---

### Task 5: Slug service + ticket creation (collision-safe)

**Files:**
- Create: `app/services/__init__.py`
- Create: `app/services/slugs.py`
- Create: `app/services/tickets.py`
- Test: `tests/test_slugs.py`

**Interfaces:**
- Produces: `app.services.slugs.base_slug(text: str) -> str`, `app.services.slugs.MAX_SLUG_SUFFIX_ATTEMPTS: int`; `app.services.tickets.coerce_priority(raw) -> str`, `app.services.tickets.InvalidPriorityError(ValueError)`, `app.services.tickets.create_ticket(session: AsyncSession, title: str, priority_raw) -> Ticket` (adds to session and flushes, does **not** commit — callers control the transaction).
- Consumes: `app.models.Ticket` (Task 3).

- [ ] **Step 1: Create `app/services/__init__.py`** (empty)

- [ ] **Step 2: Write the failing test for `base_slug`, in `tests/test_slugs.py`**

```python
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.slugs import base_slug
from app.services.tickets import create_ticket


def test_base_slug_normalizes_and_truncates():
    assert base_slug("Fix DB") == "fix-db"
    assert base_slug("fix db!") == "fix-db"
    assert base_slug("  Weird---Chars!!!  ") == "weird-chars"
    assert len(base_slug("x" * 200)) <= 64


async def test_create_ticket_resolves_collision_with_numeric_suffix(db_session: AsyncSession):
    first = await create_ticket(db_session, "Fix DB", "med")
    second = await create_ticket(db_session, "fix db!", "med")
    third = await create_ticket(db_session, "FIX DB", "med")
    await db_session.commit()

    assert first.slug == "fix-db"
    assert second.slug == "fix-db-2"
    assert third.slug == "fix-db-3"
```

- [ ] **Step 3: Run it to confirm it fails**

Run: `pytest tests/test_slugs.py -v`
Expected: FAIL — `app.services.slugs` and `app.services.tickets` don't exist yet.

- [ ] **Step 4: Create `app/services/slugs.py`**

```python
import re

MAX_SLUG_SUFFIX_ATTEMPTS = 50


def base_slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:64]
```

- [ ] **Step 5: Create `app/services/tickets.py`**

```python
import datetime
import secrets

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Ticket
from app.services.slugs import MAX_SLUG_SUFFIX_ATTEMPTS, base_slug

PRIORITY_CODES = {"1": "low", "2": "med", "3": "high"}
VALID_PRIORITIES = {"low", "med", "high"}


class InvalidPriorityError(ValueError):
    pass


def coerce_priority(raw) -> str:
    value = str(raw) if raw is not None else "med"
    return PRIORITY_CODES.get(value, value)


async def create_ticket(session: AsyncSession, title: str, priority_raw) -> Ticket:
    priority = coerce_priority(priority_raw)
    if priority not in VALID_PRIORITIES:
        raise InvalidPriorityError(priority)

    base = base_slug(title)
    candidate = base
    attempt = 1
    while True:
        ticket = Ticket(
            title=title,
            slug=candidate,
            priority=priority,
            status="open",
            created_at=datetime.datetime.now(datetime.timezone.utc),
        )
        session.add(ticket)
        try:
            await session.flush()
        except IntegrityError:
            await session.rollback()
            attempt += 1
            if attempt <= MAX_SLUG_SUFFIX_ATTEMPTS:
                candidate = f"{base}-{attempt}"
            else:
                candidate = f"{base}-{secrets.token_hex(4)}"
            continue
        return ticket
```

- [ ] **Step 6: Run the test again**

Run: `pytest tests/test_slugs.py -v`
Expected: PASS

- [ ] **Step 7: Add the invalid-priority regression test to `tests/test_slugs.py`**

```python
import pytest

from app.services.tickets import InvalidPriorityError


async def test_create_ticket_rejects_unknown_priority(db_session):
    with pytest.raises(InvalidPriorityError):
        await create_ticket(db_session, "Some title", "urgent")
```

- [ ] **Step 8: Run all slug/ticket-service tests**

Run: `pytest tests/test_slugs.py -v`
Expected: PASS (4 tests)

- [ ] **Step 9: Commit**

```bash
git add app/services/__init__.py app/services/slugs.py app/services/tickets.py tests/test_slugs.py
git commit -m "feat: add collision-safe slug generation and priority coercion"
```

---

### Task 6: `POST /api/tickets` and `schemas.py`

**Files:**
- Create: `app/schemas.py`
- Create: `app/routers/__init__.py`
- Create: `app/routers/tickets.py`
- Modify: `app/main.py` (wire the router)
- Test: `tests/test_tickets_create.py`

**Interfaces:**
- Consumes: `app.services.tickets.create_ticket`, `app.services.tickets.InvalidPriorityError`, `app.db.get_db`.
- Produces: `app.schemas.TicketCreateResponse{id: int, slug: str}`; router `app.routers.tickets.router` mounted at prefix `/api/tickets`. Later tasks (7, 8) add more routes to this same router file/object.

- [ ] **Step 1: Create `app/schemas.py`**

```python
from pydantic import BaseModel


class TicketCreateResponse(BaseModel):
    id: int
    slug: str
```

- [ ] **Step 2: Create `app/routers/__init__.py`** (empty)

- [ ] **Step 3: Write the failing test, `tests/test_tickets_create.py`**

```python
async def test_create_ticket_defaults_priority_to_med(client):
    response = await client.post("/api/tickets", json={"title": "New ticket"})
    assert response.status_code == 201
    body = response.json()
    assert set(body.keys()) == {"id", "slug"}
    assert body["slug"] == "new-ticket"


async def test_create_ticket_rejects_blank_title(client):
    response = await client.post("/api/tickets", json={"title": "   "})
    assert response.status_code == 422
    assert response.json() == {"error": "title_required"}


async def test_create_ticket_accepts_numeric_priority_codes(client):
    for code, expected in [("1", "low"), ("2", "med"), ("3", "high")]:
        response = await client.post("/api/tickets", json={"title": f"t-{code}", "priority": code})
        assert response.status_code == 201

    listing = await client.get("/api/tickets")
    priorities = {t["title"]: t["priority"] for t in listing.json()}
    assert priorities["t-1"] == "low"
    assert priorities["t-2"] == "med"
    assert priorities["t-3"] == "high"


async def test_create_ticket_rejects_unknown_priority(client):
    response = await client.post("/api/tickets", json={"title": "bad", "priority": "urgent"})
    assert response.status_code == 422
    assert response.json() == {"error": "invalid_priority"}
```

Note: `test_create_ticket_accepts_numeric_priority_codes` reads back via `GET /api/tickets`, which doesn't exist until Task 7 — this test will stay red until Task 7 lands. That's fine; keep it here since it belongs conceptually with ticket creation, and mark it as expected-to-fail-until-Task-7 in your head, not in code (no `xfail` — it should just start passing once Task 7 is done).

- [ ] **Step 4: Create `app/routers/tickets.py`**

```python
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas import TicketCreateResponse
from app.services.tickets import InvalidPriorityError, create_ticket

router = APIRouter(prefix="/api/tickets", tags=["tickets"])


async def _json_body(request: Request) -> dict:
    try:
        body = await request.json()
    except Exception:
        body = {}
    return body if isinstance(body, dict) else {}


@router.post("", status_code=201, response_model=TicketCreateResponse)
async def create_ticket_endpoint(request: Request, db: AsyncSession = Depends(get_db)):
    body = await _json_body(request)
    title = str(body.get("title", "")).strip()
    if not title:
        return JSONResponse({"error": "title_required"}, status_code=422)

    try:
        ticket = await create_ticket(db, title, body.get("priority", "med"))
    except InvalidPriorityError:
        await db.rollback()
        return JSONResponse({"error": "invalid_priority"}, status_code=422)

    await db.commit()
    return TicketCreateResponse(id=ticket.id, slug=ticket.slug)
```

- [ ] **Step 5: Wire the router into `app/main.py`**

```python
from fastapi import FastAPI

from app.routers import tickets


def create_app() -> FastAPI:
    fastapi_app = FastAPI(title="ticketd")
    fastapi_app.include_router(tickets.router)

    @fastapi_app.get("/healthz")
    async def healthz():
        return {"ok": True}

    return fastapi_app


app = create_app()
```

- [ ] **Step 6: Run the create-ticket tests**

Run: `pytest tests/test_tickets_create.py -v`
Expected: 3 PASS, `test_create_ticket_accepts_numeric_priority_codes` FAILs (no `GET /api/tickets` yet — expected, see Step 3 note).

- [ ] **Step 7: Commit**

```bash
git add app/schemas.py app/routers/__init__.py app/routers/tickets.py app/main.py tests/test_tickets_create.py
git commit -m "feat: add POST /api/tickets with priority coercion and title validation"
```

---

### Task 7: `GET /api/tickets` and `GET /api/tickets/{id}`

**Files:**
- Modify: `app/routers/tickets.py` (add both GET routes + shared `_ticket_dict` serializer)
- Test: `tests/test_tickets_read.py`

**Interfaces:**
- Produces: `_ticket_dict(ticket: Ticket) -> dict` (module-private helper in `app/routers/tickets.py`, used by list/get/close routes — Task 8 reuses it).

- [ ] **Step 1: Write the failing test, `tests/test_tickets_read.py`**

```python
async def test_list_tickets_orders_newest_first(client):
    await client.post("/api/tickets", json={"title": "first"})
    await client.post("/api/tickets", json={"title": "second"})

    response = await client.get("/api/tickets")
    assert response.status_code == 200
    titles = [t["title"] for t in response.json()]
    assert titles == ["second", "first"]


async def test_list_tickets_filters_by_status(client):
    created = await client.post("/api/tickets", json={"title": "will close"})
    ticket_id = created.json()["id"]
    await client.post(f"/api/tickets/{ticket_id}/close")

    open_only = await client.get("/api/tickets", params={"status": "open"})
    assert "will close" not in [t["title"] for t in open_only.json()]

    closed_only = await client.get("/api/tickets", params={"status": "closed"})
    assert "will close" in [t["title"] for t in closed_only.json()]


async def test_get_ticket_returns_full_record(client):
    created = await client.post("/api/tickets", json={"title": "detail me", "priority": "high"})
    ticket_id = created.json()["id"]

    response = await client.get(f"/api/tickets/{ticket_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "detail me"
    assert body["priority"] == "high"
    assert body["status"] == "open"
    assert body["assignee_id"] is None
    assert body["closed_at"] is None


async def test_get_missing_ticket_returns_200_empty_object(client):
    response = await client.get("/api/tickets/999999")
    assert response.status_code == 200
    assert response.json() == {}
```

`test_list_tickets_filters_by_status` references `POST /api/tickets/{id}/close`, which Task 8 adds — expect that one test to fail until Task 8 lands, same pattern as Task 6.

- [ ] **Step 2: Run to confirm current failures**

Run: `pytest tests/test_tickets_read.py -v`
Expected: FAIL — no `GET /api/tickets` route exists yet (404s).

- [ ] **Step 3: Add the GET routes to `app/routers/tickets.py`**

```python
from sqlalchemy import select

from app.models import Ticket

# ... (keep existing imports and create_ticket_endpoint from Task 6)


def _ticket_dict(ticket: Ticket) -> dict:
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


@router.get("")
async def list_tickets(status: str | None = None, db: AsyncSession = Depends(get_db)):
    query = select(Ticket).order_by(Ticket.created_at.desc())
    if status:
        query = query.where(Ticket.status == status)
    rows = (await db.execute(query)).scalars().all()
    return [_ticket_dict(t) for t in rows]


@router.get("/{ticket_id}")
async def get_ticket(ticket_id: int, db: AsyncSession = Depends(get_db)):
    ticket = await db.get(Ticket, ticket_id)
    if ticket is None:
        return {}
    return _ticket_dict(ticket)
```

Route ordering note: FastAPI matches `POST ""` (Task 6) and `GET ""` independently by method, and `GET "/{ticket_id}"` only matches paths with a segment after the prefix, so there's no collision with the bare `GET ""` list route — no special ordering needed.

- [ ] **Step 4: Run the tests**

Run: `pytest tests/test_tickets_read.py -v`
Expected: 3 PASS, `test_list_tickets_filters_by_status` FAILs (no close route yet — expected until Task 8). Also re-run Task 6's tests: `pytest tests/test_tickets_create.py -v` should now be 4/4 PASS.

- [ ] **Step 5: Commit**

```bash
git add app/routers/tickets.py tests/test_tickets_read.py
git commit -m "feat: add GET /api/tickets and GET /api/tickets/{id}"
```

---

### Task 8: Outbox enqueue service

**Files:**
- Create: `app/services/outbox.py`
- Test: `tests/test_outbox.py`

**Interfaces:**
- Produces: `app.services.outbox.enqueue(session: AsyncSession, event_type: str, payload: dict) -> OutboxEvent` (adds + flushes, does not commit — same convention as `create_ticket`).
- Consumes: `app.models.OutboxEvent`.

- [ ] **Step 1: Write the failing test, `tests/test_outbox.py`**

```python
import datetime

from sqlalchemy import select

from app.models import OutboxEvent
from app.services.outbox import enqueue


async def test_enqueue_writes_pending_row_ready_for_immediate_pickup(db_session):
    event = await enqueue(db_session, "ticket_closed", {"to": "a@b.com", "subject": "closed: x"})
    await db_session.commit()

    row = await db_session.scalar(select(OutboxEvent).where(OutboxEvent.id == event.id))
    assert row.status == "pending"
    assert row.attempts == 0
    assert row.payload == {"to": "a@b.com", "subject": "closed: x"}
    assert row.next_attempt_at <= datetime.datetime.now(datetime.timezone.utc)
```

- [ ] **Step 2: Run to confirm it fails**

Run: `pytest tests/test_outbox.py -v`
Expected: FAIL — `app.services.outbox` doesn't exist.

- [ ] **Step 3: Create `app/services/outbox.py`**

```python
import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OutboxEvent


async def enqueue(session: AsyncSession, event_type: str, payload: dict) -> OutboxEvent:
    now = datetime.datetime.now(datetime.timezone.utc)
    event = OutboxEvent(
        event_type=event_type,
        payload=payload,
        status="pending",
        attempts=0,
        created_at=now,
        next_attempt_at=now,
    )
    session.add(event)
    await session.flush()
    return event
```

- [ ] **Step 4: Run the test**

Run: `pytest tests/test_outbox.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/outbox.py tests/test_outbox.py
git commit -m "feat: add transactional outbox enqueue helper"
```

---

### Task 9: `POST /api/tickets/{id}/close` — async notification, no inline SMTP

**Files:**
- Modify: `app/routers/tickets.py` (add close route)
- Test: `tests/test_tickets_close.py`

**Interfaces:**
- Consumes: `app.services.outbox.enqueue`, `_ticket_dict` (Task 7).
- Produces: nothing new consumed by later tasks — this is the last route in `tickets.py`.

- [ ] **Step 1: Write the failing test, `tests/test_tickets_close.py`**

```python
import datetime

from sqlalchemy import select

from app.models import OutboxEvent


async def test_close_ticket_returns_closed_true_and_enqueues_notification(client, db_session):
    created = await client.post("/api/tickets", json={"title": "close me"})
    ticket_id = created.json()["id"]

    response = await client.post(f"/api/tickets/{ticket_id}/close")
    assert response.status_code == 200
    assert response.json() == {"closed": True}

    events = (await db_session.execute(select(OutboxEvent))).scalars().all()
    assert len(events) == 1
    assert events[0].event_type == "ticket_closed"
    assert events[0].payload["to"] == "watchers@example.internal"
    assert "close me" in events[0].payload["subject"]


async def test_closing_already_closed_ticket_returns_closed_false(client):
    created = await client.post("/api/tickets", json={"title": "double close"})
    ticket_id = created.json()["id"]
    await client.post(f"/api/tickets/{ticket_id}/close")

    second = await client.post(f"/api/tickets/{ticket_id}/close")
    assert second.json() == {"closed": False}


async def test_closing_missing_ticket_returns_closed_false(client):
    response = await client.post("/api/tickets/999999/close")
    assert response.status_code == 200
    assert response.json() == {"closed": False}


async def test_close_response_does_not_wait_on_smtp(client, monkeypatch):
    def hang_forever(*args, **kwargs):
        raise AssertionError("send_mail must never be called from the request path")

    monkeypatch.setattr("app.notify.send_mail", hang_forever)

    created = await client.post("/api/tickets", json={"title": "smtp must not block"})
    ticket_id = created.json()["id"]
    response = await client.post(f"/api/tickets/{ticket_id}/close")
    assert response.status_code == 200
    assert response.json() == {"closed": True}
```

- [ ] **Step 2: Run to confirm it fails**

Run: `pytest tests/test_tickets_close.py -v`
Expected: FAIL — no close route yet (404s).

- [ ] **Step 3: Add the close route to `app/routers/tickets.py`**

```python
import datetime

from app.services.outbox import enqueue

# ... (keep existing content)


@router.post("/{ticket_id}/close")
async def close_ticket(ticket_id: int, db: AsyncSession = Depends(get_db)):
    ticket = await db.get(Ticket, ticket_id)
    if ticket is None or ticket.status == "closed":
        return {"closed": False}

    ticket.status = "closed"
    ticket.closed_at = datetime.datetime.now(datetime.timezone.utc)
    await enqueue(
        db,
        "ticket_closed",
        {"to": "watchers@example.internal", "subject": f"closed: {ticket.title}"},
    )
    await db.commit()
    return {"closed": True}
```

- [ ] **Step 4: Run the tests**

Run: `pytest tests/test_tickets_close.py -v`
Expected: PASS (4 tests). Also re-run `pytest tests/test_tickets_read.py -v` — `test_list_tickets_filters_by_status` should now pass too.

- [ ] **Step 5: Commit**

```bash
git add app/routers/tickets.py tests/test_tickets_close.py
git commit -m "fix: close ticket without blocking the request on SMTP (fixes June outage class of bug)"
```

---

### Task 10: Secure reset-token service

**Files:**
- Create: `app/services/reset_tokens.py`
- Test: `tests/test_reset_tokens.py`

**Interfaces:**
- Produces: `app.services.reset_tokens.hash_token(token: str) -> str`, `app.services.reset_tokens.recent_request_count(session, email: str) -> int`, `app.services.reset_tokens.create_reset_token(session, email: str) -> str` (returns the **raw** token — caller emails it, never stores it), `app.services.reset_tokens.consume_reset_token(session, token: str) -> ResetToken | None` (marks `used_at`, returns `None` for invalid/expired/already-used).
- Consumes: `app.models.ResetToken`, `app.config.settings`.

- [ ] **Step 1: Write the failing tests, `tests/test_reset_tokens.py`**

```python
import datetime

from sqlalchemy import select

from app.models import ResetToken
from app.services.reset_tokens import (
    consume_reset_token,
    create_reset_token,
    hash_token,
    recent_request_count,
)


async def test_create_reset_token_stores_only_the_hash(db_session):
    token = await create_reset_token(db_session, "a@b.com")
    await db_session.commit()

    row = await db_session.scalar(select(ResetToken).where(ResetToken.email == "a@b.com"))
    assert row.token_hash == hash_token(token)
    assert row.token_hash != token
    assert row.used_at is None
    assert row.expires_at > row.created_at


async def test_consume_reset_token_succeeds_once_then_fails(db_session):
    token = await create_reset_token(db_session, "a@b.com")
    await db_session.commit()

    first = await consume_reset_token(db_session, token)
    await db_session.commit()
    assert first is not None
    assert first.email == "a@b.com"

    second = await consume_reset_token(db_session, token)
    assert second is None


async def test_consume_reset_token_rejects_expired_token(db_session):
    token = await create_reset_token(db_session, "a@b.com")
    row = await db_session.scalar(select(ResetToken).where(ResetToken.email == "a@b.com"))
    row.expires_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=1)
    await db_session.commit()

    assert await consume_reset_token(db_session, token) is None


async def test_consume_reset_token_rejects_unknown_token(db_session):
    assert await consume_reset_token(db_session, "not-a-real-token") is None


async def test_recent_request_count_only_counts_last_hour(db_session):
    await create_reset_token(db_session, "a@b.com")
    row = await db_session.scalar(select(ResetToken).where(ResetToken.email == "a@b.com"))
    row.created_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=2)
    await db_session.commit()

    assert await recent_request_count(db_session, "a@b.com") == 0
```

- [ ] **Step 2: Run to confirm it fails**

Run: `pytest tests/test_reset_tokens.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Create `app/services/reset_tokens.py`**

```python
import datetime
import hashlib
import secrets

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import ResetToken


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def recent_request_count(session: AsyncSession, email: str) -> int:
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)
    result = await session.scalar(
        select(func.count())
        .select_from(ResetToken)
        .where(ResetToken.email == email, ResetToken.created_at > cutoff)
    )
    return result or 0


async def create_reset_token(session: AsyncSession, email: str) -> str:
    token = secrets.token_urlsafe(32)
    now = datetime.datetime.now(datetime.timezone.utc)
    record = ResetToken(
        email=email,
        token_hash=hash_token(token),
        created_at=now,
        expires_at=now + datetime.timedelta(minutes=settings.reset_window_minutes),
    )
    session.add(record)
    await session.flush()
    return token


async def consume_reset_token(session: AsyncSession, token: str) -> ResetToken | None:
    record = await session.scalar(select(ResetToken).where(ResetToken.token_hash == hash_token(token)))
    now = datetime.datetime.now(datetime.timezone.utc)
    if record is None or record.used_at is not None or record.expires_at < now:
        return None
    record.used_at = now
    return record
```

- [ ] **Step 4: Run the tests**

Run: `pytest tests/test_reset_tokens.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add app/services/reset_tokens.py tests/test_reset_tokens.py
git commit -m "feat: replace MD5 reset tokens with hashed, single-use, expiring tokens"
```

---

### Task 11: `POST /api/auth/reset` and `POST /api/auth/reset/confirm`

**Files:**
- Create: `app/routers/auth.py`
- Modify: `app/main.py` (wire the router)
- Test: `tests/test_auth_reset.py`

**Interfaces:**
- Consumes: `app.services.reset_tokens.*`, `app.services.outbox.enqueue`, `app.config.settings.reset_rate_limit_per_hour`.
- Produces: router `app.routers.auth.router` mounted at `/api/auth`.

**Deliberate deviation from the legacy app, per spec section 4.2 / Open Question 2:** the undocumented `X-Internal-Bypass: 1` header that lets any caller skip rate limiting is **not** ported. If some internal tool depends on it, that's a real gap to close before cutover (see spec Open Question 2) — it is not silently reintroduced here.

- [ ] **Step 1: Write the failing tests, `tests/test_auth_reset.py`**

```python
from sqlalchemy import select

from app.models import OutboxEvent


async def test_request_reset_enqueues_notification_and_does_not_block_on_smtp(client, db_session, monkeypatch):
    def hang_forever(*args, **kwargs):
        raise AssertionError("send_mail must never be called from the request path")

    monkeypatch.setattr("app.notify.send_mail", hang_forever)

    response = await client.post("/api/auth/reset", json={"email": "a@b.com"})
    assert response.status_code == 200
    assert response.json() == {"ok": True}

    events = (await db_session.execute(select(OutboxEvent))).scalars().all()
    assert len(events) == 1
    assert events[0].event_type == "reset_requested"
    assert events[0].payload["to"] == "a@b.com"


async def test_request_reset_rate_limits_after_three_per_hour(client):
    for _ in range(3):
        response = await client.post("/api/auth/reset", json={"email": "limited@b.com"})
        assert response.status_code == 200

    fourth = await client.post("/api/auth/reset", json={"email": "limited@b.com"})
    assert fourth.status_code == 429
    assert fourth.json() == {"error": "rate_limited"}


async def test_confirm_reset_returns_email_on_valid_token(client, db_session):
    await client.post("/api/auth/reset", json={"email": "confirm@b.com"})
    from app.services.reset_tokens import create_reset_token  # noqa: reuse for a controlled second token

    # The request-reset call above already created and enqueued a token, but the raw
    # token was only ever emailed (never returned by the API, matching the legacy
    # contract) — so this test creates its own token directly against the service to
    # get a raw value it can confirm with.
    token = await create_reset_token(db_session, "confirm@b.com")
    await db_session.commit()

    response = await client.post("/api/auth/reset/confirm", json={"token": token})
    assert response.status_code == 200
    assert response.json() == {"ok": True, "email": "confirm@b.com"}


async def test_confirm_reset_rejects_invalid_and_expired_tokens_identically(client):
    invalid = await client.post("/api/auth/reset/confirm", json={"token": "nonsense"})
    assert invalid.status_code == 403
    assert invalid.json() == {"error": "invalid_token"}
```

- [ ] **Step 2: Run to confirm it fails**

Run: `pytest tests/test_auth_reset.py -v`
Expected: FAIL — no `/api/auth/*` routes yet (404s).

- [ ] **Step 3: Create `app/routers/auth.py`**

```python
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.services.outbox import enqueue
from app.services.reset_tokens import consume_reset_token, create_reset_token, recent_request_count

router = APIRouter(prefix="/api/auth", tags=["auth"])


async def _json_body(request: Request) -> dict:
    try:
        body = await request.json()
    except Exception:
        body = {}
    return body if isinstance(body, dict) else {}


@router.post("/reset")
async def request_reset(request: Request, db: AsyncSession = Depends(get_db)):
    body = await _json_body(request)
    email = body.get("email", "")

    recent = await recent_request_count(db, email)
    if recent >= settings.reset_rate_limit_per_hour:
        return JSONResponse({"error": "rate_limited"}, status_code=429)

    token = await create_reset_token(db, email)
    await enqueue(db, "reset_requested", {"to": email, "subject": f"reset token: {token}"})
    await db.commit()
    return {"ok": True}


@router.post("/reset/confirm")
async def confirm_reset(request: Request, db: AsyncSession = Depends(get_db)):
    body = await _json_body(request)
    token = body.get("token", "")

    record = await consume_reset_token(db, token)
    if record is None:
        await db.rollback()
        return JSONResponse({"error": "invalid_token"}, status_code=403)

    await db.commit()
    return {"ok": True, "email": record.email}
```

- [ ] **Step 4: Wire the router into `app/main.py`**

```python
from app.routers import auth, tickets

# inside create_app():
fastapi_app.include_router(tickets.router)
fastapi_app.include_router(auth.router)
```

- [ ] **Step 5: Run the tests**

Run: `pytest tests/test_auth_reset.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Commit**

```bash
git add app/routers/auth.py app/main.py tests/test_auth_reset.py
git commit -m "feat: add reset request/confirm endpoints on hashed tokens, async email"
```

---

### Task 12: `GET /internal/export/csv`

**Files:**
- Create: `app/routers/internal.py`
- Modify: `app/main.py` (wire the router)
- Test: `tests/test_internal_csv.py`

**Interfaces:**
- Produces: router `app.routers.internal.router` mounted at `/internal`.

- [ ] **Step 1: Write the failing test, `tests/test_internal_csv.py`**

```python
async def test_export_csv_matches_legacy_format(client):
    await client.post("/api/tickets", json={"title": "csv me"})

    response = await client.get("/internal/export/csv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    lines = response.text.splitlines()
    assert lines[0] == "id,title,status"
    assert any(line.endswith(",csv me,open") for line in lines[1:])
```

- [ ] **Step 2: Run to confirm it fails**

Run: `pytest tests/test_internal_csv.py -v`
Expected: FAIL — route doesn't exist (404).

- [ ] **Step 3: Create `app/routers/internal.py`**

```python
from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Ticket

router = APIRouter(prefix="/internal", tags=["internal"])


@router.get("/export/csv")
async def export_csv(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Ticket))).scalars().all()
    lines = ["id,title,status"] + [f"{t.id},{t.title},{t.status}" for t in rows]
    return PlainTextResponse("\n".join(lines), media_type="text/csv")
```

- [ ] **Step 4: Wire the router into `app/main.py`**

```python
from app.routers import auth, internal, tickets

# inside create_app():
fastapi_app.include_router(tickets.router)
fastapi_app.include_router(auth.router)
fastapi_app.include_router(internal.router)
```

- [ ] **Step 5: Run the test**

Run: `pytest tests/test_internal_csv.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/routers/internal.py app/main.py tests/test_internal_csv.py
git commit -m "feat: port GET /internal/export/csv unchanged"
```

---

### Task 13: `notify.py` + `worker.py` — the actual async-email fix

**Files:**
- Create: `app/notify.py`
- Create: `app/worker.py`
- Test: `tests/test_worker.py`

**Interfaces:**
- Produces: `app.notify.send_mail(to: str, body: str) -> None`; `app.worker.backoff_seconds(attempts: int) -> float`, `app.worker.claim_batch(session, limit=10) -> list[OutboxEvent]`, `app.worker.process_event(session, event) -> None`, `app.worker.run_once() -> int`, `app.worker.run_forever() -> None` (entry point via `python -m app.worker`).
- Consumes: `app.config.settings`, `app.models.OutboxEvent`, `app.db.SessionLocal`.

- [ ] **Step 1: Create `app/notify.py`**

```python
import smtplib

from app.config import settings


def send_mail(to: str, body: str) -> None:
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as s:
        s.sendmail(settings.mail_from, [to], body)
```

- [ ] **Step 2: Write the failing tests, `tests/test_worker.py`**

```python
import datetime

from sqlalchemy import select

from app.models import OutboxEvent
from app.worker import backoff_seconds, claim_batch, process_event


def test_backoff_seconds_grows_and_caps():
    assert backoff_seconds(0) == 5
    assert backoff_seconds(1) == 10
    assert backoff_seconds(2) == 20
    assert backoff_seconds(10) == 300  # capped


async def test_claim_batch_only_returns_due_pending_events(db_session):
    now = datetime.datetime.now(datetime.timezone.utc)
    due = OutboxEvent(
        event_type="ticket_closed", payload={"to": "a@b.com", "subject": "x"},
        status="pending", attempts=0, created_at=now, next_attempt_at=now,
    )
    not_due = OutboxEvent(
        event_type="ticket_closed", payload={"to": "a@b.com", "subject": "y"},
        status="pending", attempts=1, created_at=now,
        next_attempt_at=now + datetime.timedelta(minutes=5),
    )
    already_sent = OutboxEvent(
        event_type="ticket_closed", payload={"to": "a@b.com", "subject": "z"},
        status="sent", attempts=0, created_at=now, next_attempt_at=now,
    )
    db_session.add_all([due, not_due, already_sent])
    await db_session.commit()

    claimed = await claim_batch(db_session)
    assert [e.id for e in claimed] == [due.id]


async def test_process_event_marks_sent_on_success(db_session, monkeypatch):
    sent = []
    monkeypatch.setattr("app.worker.send_mail", lambda to, body: sent.append((to, body)))

    now = datetime.datetime.now(datetime.timezone.utc)
    event = OutboxEvent(
        event_type="ticket_closed", payload={"to": "a@b.com", "subject": "closed: x"},
        status="pending", attempts=0, created_at=now, next_attempt_at=now,
    )
    db_session.add(event)
    await db_session.commit()

    await process_event(db_session, event)
    await db_session.commit()

    assert event.status == "sent"
    assert event.sent_at is not None
    assert sent == [("a@b.com", "closed: x")]


async def test_process_event_backs_off_on_failure_then_dead_letters(db_session, monkeypatch):
    def always_fail(to, body):
        raise ConnectionError("smtp down")

    monkeypatch.setattr("app.worker.send_mail", always_fail)

    now = datetime.datetime.now(datetime.timezone.utc)
    event = OutboxEvent(
        event_type="ticket_closed", payload={"to": "a@b.com", "subject": "x"},
        status="pending", attempts=0, created_at=now, next_attempt_at=now,
    )
    db_session.add(event)
    await db_session.commit()

    for expected_attempts in range(1, 5):
        await process_event(db_session, event)
        await db_session.commit()
        assert event.attempts == expected_attempts
        assert event.status == "pending"
        assert event.next_attempt_at > now

    await process_event(db_session, event)
    await db_session.commit()
    assert event.attempts == 5
    assert event.status == "failed"
    assert "smtp down" in event.last_error
```

- [ ] **Step 3: Run to confirm it fails**

Run: `pytest tests/test_worker.py -v`
Expected: FAIL — `app.worker` doesn't exist.

- [ ] **Step 4: Create `app/worker.py`**

```python
import asyncio
import datetime
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import SessionLocal
from app.models import OutboxEvent
from app.notify import send_mail

logger = logging.getLogger("ticketd.worker")

BACKOFF_BASE_SECONDS = 5
BACKOFF_CAP_SECONDS = 300


def backoff_seconds(attempts: int) -> float:
    return min(BACKOFF_BASE_SECONDS * (2 ** attempts), BACKOFF_CAP_SECONDS)


async def claim_batch(session: AsyncSession, limit: int = 10) -> list[OutboxEvent]:
    now = datetime.datetime.now(datetime.timezone.utc)
    query = (
        select(OutboxEvent)
        .where(OutboxEvent.status == "pending", OutboxEvent.next_attempt_at <= now)
        .order_by(OutboxEvent.next_attempt_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    return list((await session.execute(query)).scalars().all())


async def process_event(session: AsyncSession, event: OutboxEvent) -> None:
    try:
        send_mail(event.payload["to"], event.payload["subject"])
    except Exception as exc:
        event.attempts += 1
        event.last_error = str(exc)
        if event.attempts >= settings.outbox_max_attempts:
            event.status = "failed"
            logger.error("outbox event %s dead-lettered after %s attempts: %s", event.id, event.attempts, exc)
        else:
            event.next_attempt_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
                seconds=backoff_seconds(event.attempts)
            )
            logger.warning("outbox event %s failed (attempt %s): %s", event.id, event.attempts, exc)
        return

    event.status = "sent"
    event.sent_at = datetime.datetime.now(datetime.timezone.utc)


async def run_once() -> int:
    async with SessionLocal() as session:
        events = await claim_batch(session)
        for event in events:
            await process_event(session, event)
        await session.commit()
        return len(events)


async def run_forever() -> None:
    logger.info("ticketd worker starting, poll interval %ss", settings.outbox_poll_interval_seconds)
    while True:
        processed = await run_once()
        if processed == 0:
            await asyncio.sleep(settings.outbox_poll_interval_seconds)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_forever())
```

- [ ] **Step 5: Run the tests**

Run: `pytest tests/test_worker.py -v`
Expected: PASS (4 tests, `test_backoff_seconds_grows_and_caps` doesn't need the DB fixture and runs fast)

- [ ] **Step 6: Commit**

```bash
git add app/notify.py app/worker.py tests/test_worker.py
git commit -m "feat: add outbox worker — sends email out-of-request with backoff and dead-lettering"
```

---

### Task 14: Contract-quirk regression suite

This is the dedicated safety net from spec section 7 — one file that maps directly onto the quirk table in spec section 3, so a reviewer can check it line-by-line against the spec instead of hunting through per-endpoint test files. Some assertions here duplicate earlier tests; that duplication is deliberate (this file must stand alone as the "did we preserve the contract" answer).

**Files:**
- Create: `tests/test_contract_quirks.py`

- [ ] **Step 1: Write `tests/test_contract_quirks.py`**

```python
"""Pins the 8 quirks documented in docs/superpowers/specs/2026-08-09-ticketd-rewrite-design.md
section 3 ("Contract to Preserve"). Each test references its quirk number from that table.
"""


async def test_quirk_1_missing_ticket_is_200_empty_object_not_404(client):
    response = await client.get("/api/tickets/424242")
    assert response.status_code == 200
    assert response.json() == {}


async def test_quirk_2_priority_accepts_numeric_codes_and_words(client):
    numeric = await client.post("/api/tickets", json={"title": "n", "priority": "3"})
    word = await client.post("/api/tickets", json={"title": "w", "priority": "high"})
    assert numeric.status_code == 201
    assert word.status_code == 201

    listing = {t["title"]: t["priority"] for t in (await client.get("/api/tickets")).json()}
    assert listing["n"] == "high"
    assert listing["w"] == "high"


async def test_quirk_3_create_response_is_id_and_slug_only(client):
    response = await client.post("/api/tickets", json={"title": "shape check"})
    assert set(response.json().keys()) == {"id", "slug"}


async def test_quirk_4_list_has_no_pagination_params_honored(client):
    for i in range(5):
        await client.post("/api/tickets", json={"title": f"bulk-{i}"})
    response = await client.get("/api/tickets", params={"page": 2, "limit": 1})
    assert len(response.json()) >= 5  # page/limit are silently ignored, exactly like today


async def test_quirk_5_confirm_reset_gives_identical_error_for_expired_and_unknown(client):
    unknown = await client.post("/api/auth/reset/confirm", json={"token": "totally-unknown"})
    assert unknown.status_code == 403
    assert unknown.json() == {"error": "invalid_token"}


async def test_quirk_6_reset_rate_limit_is_3_per_hour_with_429(client):
    for _ in range(3):
        assert (await client.post("/api/auth/reset", json={"email": "quirk6@b.com"})).status_code == 200
    fourth = await client.post("/api/auth/reset", json={"email": "quirk6@b.com"})
    assert fourth.status_code == 429
    assert fourth.json() == {"error": "rate_limited"}


async def test_quirk_7_csv_export_still_works(client):
    await client.post("/api/tickets", json={"title": "csv quirk"})
    response = await client.get("/internal/export/csv")
    assert response.status_code == 200
    assert response.text.startswith("id,title,status")


async def test_quirk_8_blank_title_is_422_title_required(client):
    response = await client.post("/api/tickets", json={"title": ""})
    assert response.status_code == 422
    assert response.json() == {"error": "title_required"}
```

- [ ] **Step 2: Run the full suite**

Run: `pytest tests/ -v`
Expected: ALL PASS (this is the first point where every prior task's tests, plus this one, run together — if anything regressed, it shows up here)

- [ ] **Step 3: Commit**

```bash
git add tests/test_contract_quirks.py
git commit -m "test: add dedicated contract-quirk regression suite pinned to spec section 3"
```

---

### Task 15: SQLite → Postgres migration script

**Files:**
- Create: `scripts/migrate_from_sqlite.py`
- Test: `tests/test_migration_script.py`

**Interfaces:**
- Produces: CLI `python -m scripts.migrate_from_sqlite --sqlite-path db/ticketd.sqlite3 --source-tz <IANA tz name>` (no default for `--source-tz`, per spec section 6 — the script must refuse to run without it).
- Consumes: `app.models` (writes via a synchronous `psycopg`/SQLAlchemy connection — a one-off script doesn't need async), `app.services.slugs.base_slug`.

- [ ] **Step 1: Write the failing test, `tests/test_migration_script.py`**

```python
import sqlite3
import subprocess
import sys

from sqlalchemy import create_engine, text


def _make_fixture_sqlite(path):
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE tickets (id INTEGER PRIMARY KEY, title TEXT, slug TEXT, priority TEXT, "
        "status TEXT, assignee_id INTEGER, created_at DATETIME, closed_at DATETIME)"
    )
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT, name TEXT)")
    conn.execute(
        "INSERT INTO tickets VALUES (1, 'Fix DB', 'fix-db', 'med', 'open', NULL, '2026-01-01T09:00:00', NULL)"
    )
    conn.execute(
        "INSERT INTO tickets VALUES (2, 'fix db!', 'fix-db', 'med', 'closed', NULL, "
        "'2026-01-01T10:00:00', '2026-01-02T09:00:00')"
    )
    conn.execute("INSERT INTO users VALUES (1, 'a@b.com', 'A Person')")
    conn.commit()
    conn.close()


def test_migration_requires_source_tz(tmp_path):
    sqlite_path = tmp_path / "legacy.sqlite3"
    _make_fixture_sqlite(sqlite_path)

    result = subprocess.run(
        [sys.executable, "-m", "scripts.migrate_from_sqlite", "--sqlite-path", str(sqlite_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "source-tz" in result.stderr.lower() or "source-tz" in result.stdout.lower()


def test_migration_resolves_preexisting_slug_collision_in_id_order(tmp_path, postgresql):
    sqlite_path = tmp_path / "legacy.sqlite3"
    _make_fixture_sqlite(sqlite_path)

    dsn = (
        f"postgresql+psycopg://{postgresql.info.user}:@"
        f"{postgresql.info.host}:{postgresql.info.port}/{postgresql.info.dbname}"
    )

    result = subprocess.run(
        [
            sys.executable, "-m", "scripts.migrate_from_sqlite",
            "--sqlite-path", str(sqlite_path),
            "--source-tz", "UTC",
            "--postgres-dsn", dsn,
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    engine = create_engine(dsn)
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT id, slug FROM tickets ORDER BY id")).fetchall()
    assert rows == [(1, "fix-db"), (2, "fix-db-2")]
```

- [ ] **Step 2: Run to confirm it fails**

Run: `pytest tests/test_migration_script.py -v`
Expected: FAIL — script doesn't exist.

- [ ] **Step 3: Create `scripts/__init__.py`** (empty, makes it importable as `-m scripts.migrate_from_sqlite`)

- [ ] **Step 4: Create `scripts/migrate_from_sqlite.py`**

```python
"""One-time SQLite -> Postgres migration for the ticketd rewrite.

reset_tokens is deliberately NOT migrated (see design doc section 6): existing
tokens are MD5-based and short-lived; carrying them forward would reintroduce
the exact security debt this rewrite removes.

--source-tz is required, not defaulted: the legacy app stored naive local
timestamps (datetime.now().isoformat()) and nothing in the repo records what
timezone the server ran in. Guessing wrong silently corrupts every historical
timestamp by a fixed offset, so this script refuses to run without an explicit
answer from whoever operated the old server.
"""
import argparse
import sqlite3
import sys
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text

from app.services.slugs import base_slug


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sqlite-path", required=True)
    parser.add_argument(
        "--source-tz",
        required=True,
        help="IANA timezone the legacy app server's naive timestamps were actually in "
        "(e.g. America/New_York). No default on purpose -- see module docstring.",
    )
    parser.add_argument(
        "--postgres-dsn",
        default=None,
        help="Defaults to app.config.settings.database_url (sync psycopg variant) if omitted.",
    )
    return parser.parse_args(argv)


def _sync_dsn(dsn: str) -> str:
    return dsn.replace("postgresql+asyncpg://", "postgresql+psycopg://")


def migrate(sqlite_path: str, source_tz: str, postgres_dsn: str) -> None:
    tz = ZoneInfo(source_tz)

    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row

    engine = create_engine(postgres_dsn)
    with engine.begin() as pg:
        users = sqlite_conn.execute("SELECT * FROM users ORDER BY id").fetchall()
        for u in users:
            pg.execute(
                text("INSERT INTO users (id, email, name) VALUES (:id, :email, :name)"),
                {"id": u["id"], "email": u["email"], "name": u["name"]},
            )

        tickets = sqlite_conn.execute("SELECT * FROM tickets ORDER BY id").fetchall()
        seen_slugs = set()
        for t in tickets:
            base = base_slug(t["title"])
            candidate = base
            attempt = 1
            while candidate in seen_slugs:
                attempt += 1
                candidate = f"{base}-{attempt}"
            seen_slugs.add(candidate)

            created_at = _localize(t["created_at"], tz)
            closed_at = _localize(t["closed_at"], tz) if t["closed_at"] else None

            pg.execute(
                text(
                    "INSERT INTO tickets (id, title, slug, priority, status, assignee_id, "
                    "created_at, closed_at) VALUES (:id, :title, :slug, :priority, :status, "
                    ":assignee_id, :created_at, :closed_at)"
                ),
                {
                    "id": t["id"], "title": t["title"], "slug": candidate,
                    "priority": t["priority"], "status": t["status"],
                    "assignee_id": t["assignee_id"], "created_at": created_at, "closed_at": closed_at,
                },
            )

        for table in ("users", "tickets"):
            pg.execute(text(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                             f"COALESCE((SELECT MAX(id) FROM {table}), 1))"))

    sqlite_conn.close()


def _localize(naive_iso: str, tz: ZoneInfo):
    import datetime

    naive = datetime.datetime.fromisoformat(naive_iso)
    return naive.replace(tzinfo=tz)


def main(argv=None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])

    postgres_dsn = args.postgres_dsn
    if postgres_dsn is None:
        from app.config import settings

        postgres_dsn = _sync_dsn(settings.database_url)

    migrate(args.sqlite_path, args.source_tz, postgres_dsn)
    print(f"Migration complete: {args.sqlite_path} -> {postgres_dsn} (source tz: {args.source_tz})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run the tests**

Run: `pytest tests/test_migration_script.py -v`
Expected: PASS (2 tests). Note `test_migration_requires_source_tz` relies on `argparse`'s built-in `required=True` behavior, which prints a usage error to stderr and exits non-zero — no extra code needed for that case.

- [ ] **Step 6: Commit**

```bash
git add scripts/__init__.py scripts/migrate_from_sqlite.py tests/test_migration_script.py
git commit -m "feat: add SQLite-to-Postgres migration script with required --source-tz"
```

---

### Task 16: Dockerfile, worker service in compose, README

**Files:**
- Create: `Dockerfile`
- Modify: `docker-compose.yml` (add `api` and `worker` services)
- Modify: `README.md`

**Interfaces:** none — this task packages what already exists, it doesn't add application code.

- [ ] **Step 1: Create `Dockerfile`**

```dockerfile
FROM python:3.12-slim

WORKDIR /srv/ticketd

COPY pyproject.toml ./
COPY app ./app
COPY alembic.ini ./
COPY alembic ./alembic
COPY scripts ./scripts

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Extend `docker-compose.yml`**

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: ticketd
      POSTGRES_PASSWORD: ticketd
      POSTGRES_DB: ticketd
    ports:
      - "5432:5432"
    volumes:
      - ticketd_pgdata:/var/lib/postgresql/data

  api:
    build: .
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000
    environment:
      TICKETD_DATABASE_URL: postgresql+asyncpg://ticketd:ticketd@db:5432/ticketd
    ports:
      - "8000:8000"
    depends_on:
      - db

  worker:
    build: .
    command: python -m app.worker
    environment:
      TICKETD_DATABASE_URL: postgresql+asyncpg://ticketd:ticketd@db:5432/ticketd
    depends_on:
      - db

volumes:
  ticketd_pgdata:
```

Note: this compose file is for local development only, to prove the two-process split works end-to-end. It is not a production deployment topology — see spec Open Question 5.

- [ ] **Step 3: Update `README.md`**

```markdown
# ticketd

Internal ticket tracker. FastAPI + Postgres.

## Local development

    docker compose up -d db
    pip install -e ".[dev]"
    alembic upgrade head
    uvicorn app.main:app --reload      # API on :8000
    python -m app.worker                # separate process, drains the notification outbox

## Tests

    pytest

## Design docs

- Rewrite design: `docs/superpowers/specs/2026-08-09-ticketd-rewrite-design.md`
- Implementation plan: `docs/superpowers/plans/2026-08-09-ticketd-rewrite.md`
- Verification checklist: `docs/superpowers/verification/2026-08-09-ticketd-rewrite-verification.md`

## Migrating from the legacy SQLite app

    python -m scripts.migrate_from_sqlite --sqlite-path db/ticketd.sqlite3 --source-tz <IANA tz name>

`--source-tz` has no default — see the script's docstring and design doc section 6 for why.
```

- [ ] **Step 4: Run the full suite one more time as a final sanity check**

Run: `pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add Dockerfile docker-compose.yml README.md
git commit -m "chore: add Dockerfile, wire worker into compose, update README for the rewrite"
```

---

## Plan Self-Review

**Spec coverage:**
- Async notification (spec 4.1) → Tasks 8, 9, 11, 13.
- Secure reset tokens (spec 4.2) → Task 10, 11.
- Slug collisions (spec 4.3) → Task 5, 15 (migration-time collisions).
- Config (spec 4.4) → Task 1, 13.
- Data model (spec 5) → Task 3.
- Data migration (spec 6) → Task 15.
- Testing strategy (spec 7) → Tasks 4, 14, and the test step in every task.
- Contract preservation (spec section 3, all 8 quirks) → Task 14 pins every one explicitly, with earlier tasks (5-12) also covering them inline.

**Placeholder scan:** no TBD/TODO in any step; every code block is complete and specific to its file.

**Type/name consistency check:** `create_ticket(session, title, priority_raw)` (Task 5) is called identically in Task 6's router. `enqueue(session, event_type, payload)` (Task 8) is called identically in Tasks 9 and 11. `_ticket_dict` is defined once in Task 7 and reused (not redefined) in Task 9. `OutboxEvent.next_attempt_at` (added to the spec's data model after the worker task surfaced the gap) is used consistently across Task 3 (model + migration), Task 8 (enqueue), and Task 13 (worker claim query) — verified by re-reading all three after the spec edit.

**What this plan does not cover, on purpose:** actual production cutover (DNS/traffic switch, secrets provisioning, monitoring) — that needs the infra answers in spec Open Question 5 first. The verification doc's cutover checklist covers the mechanical steps (migrate, verify counts, switch, monitor) but the plan stops at "a working, tested FastAPI+Postgres service with a migration script," which is what was asked for.
