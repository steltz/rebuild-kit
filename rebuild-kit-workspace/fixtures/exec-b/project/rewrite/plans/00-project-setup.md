# ticketd rewrite — Phase 0: Project Setup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Read first, in order:** `../00-CONTEXT-AND-CONSTRAINTS.md`, `../01-CURRENT-BEHAVIOR-CONTRACT.md`, `../DESIGN-architecture.md`, `../03-OPEN-QUESTIONS.md`. Do not start this phase without having read the behavior contract — every later phase assumes you already know the legacy quirks it documents.

**Goal:** Stand up a runnable, empty FastAPI + Postgres project skeleton with
local dev tooling, so every later phase can add routes/tables/tests to a
working foundation instead of bootstrapping from nothing.

**Architecture:** Single FastAPI app (`ticketd_api`) + Postgres via Docker
Compose for local dev + Alembic for migrations. See `../DESIGN-architecture.md`
for the full target file layout (this phase creates the skeleton of it).

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.x (async) +
asyncpg, Alembic, pytest + httpx (`AsyncClient`) for tests, Docker Compose
for local Postgres.

## Global Constraints

- No UI changes, ever, in any phase (`../00-CONTEXT-AND-CONSTRAINTS.md`).
- The legacy app (`ticketd/`) is a read-only reference. Do not modify it.
- New code lives in a sibling directory `ticketd-api/` (created by this
  phase), not inside `ticketd/`.
- Every phase must leave `pytest` green before being considered done.
- Match `../DESIGN-architecture.md`'s file layout exactly unless a task here
  says otherwise — later plans reference these exact paths.

---

### Task 1: Repo skeleton and dependency setup

**Files:**
- Create: `ticketd-api/pyproject.toml`
- Create: `ticketd-api/app/__init__.py`
- Create: `ticketd-api/app/main.py`
- Create: `ticketd-api/app/config.py`
- Create: `ticketd-api/.env.example`
- Create: `ticketd-api/docker-compose.yml`
- Create: `ticketd-api/.gitignore`
- Test: `ticketd-api/tests/test_health.py`

**Interfaces:**
- Produces: `app.config.Settings` — a Pydantic `BaseSettings` subclass with
  fields `database_url: str`, `smtp_host: str = "smtp.internal"`,
  `smtp_port: int = 25`, `reset_window_minutes: int = 30`,
  `reset_rate_limit_per_hour: int = 3`, `outbox_poll_interval_seconds: int
  = 5`. Loaded via `get_settings()` (cached with `functools.lru_cache`).
  Later phases import `from app.config import get_settings`.
- Produces: `app.main.app` — the FastAPI instance, importable as
  `app.main:app` for uvicorn/tests.

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "ticketd-api"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "sqlalchemy[asyncio]>=2.0",
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
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

- [ ] **Step 2: Create `app/config.py`**

```python
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://ticketd:ticketd@localhost:5432/ticketd"
    smtp_host: str = "smtp.internal"
    smtp_port: int = 25
    reset_window_minutes: int = 30
    reset_rate_limit_per_hour: int = 3
    outbox_poll_interval_seconds: int = 5


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 3: Create `.env.example`**

```
DATABASE_URL=postgresql+asyncpg://ticketd:ticketd@localhost:5432/ticketd
SMTP_HOST=smtp.internal
SMTP_PORT=25
```

- [ ] **Step 4: Create `docker-compose.yml`** (local dev Postgres only —
  real environments' Postgres hosting is an open question, see
  `../03-OPEN-QUESTIONS.md` item 8; this is dev-only)

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: ticketd
      POSTGRES_PASSWORD: ticketd
      POSTGRES_DB: ticketd
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

- [ ] **Step 5: Create `app/main.py`** with a health endpoint

```python
from fastapi import FastAPI

app = FastAPI(title="ticketd")


@app.get("/healthz")
async def healthz():
    return {"ok": True}
```

- [ ] **Step 6: Create `.gitignore`**

```
__pycache__/
*.pyc
.env
.venv/
```

- [ ] **Step 7: Write the failing test**

```python
# tests/test_health.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_healthz():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
```

- [ ] **Step 8: Install and run**

```bash
cd ticketd-api
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/test_health.py -v
```
Expected: PASS (this endpoint needs no DB, so it should pass before Task 2
sets up Postgres).

- [ ] **Step 9: Commit**

```bash
git init  # this is a new project, separate from ticketd/'s own repo
git add pyproject.toml app docker-compose.yml .env.example .gitignore tests
git commit -m "chore: scaffold ticketd-api FastAPI project"
```

---

### Task 2: Database engine + Alembic wiring

**Files:**
- Create: `ticketd-api/app/db.py`
- Create: `ticketd-api/alembic.ini`
- Create: `ticketd-api/migrations/env.py`
- Create: `ticketd-api/migrations/script.py.mako`
- Test: `ticketd-api/tests/conftest.py`

**Interfaces:**
- Consumes: `app.config.get_settings()` (Task 1).
- Produces: `app.db.get_session` — a FastAPI dependency
  (`AsyncGenerator[AsyncSession, None]`) that later route modules use as
  `session: AsyncSession = Depends(get_session)`.
- Produces: `app.db.engine` — the shared `AsyncEngine`, used by
  `migrations/env.py` and by `app/worker.py` in Phase 3.

- [ ] **Step 1: Create `app/db.py`**

```python
from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.config import get_settings

engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
async_session = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session
```

- [ ] **Step 2: Initialize Alembic** (async template)

```bash
cd ticketd-api
alembic init -t async migrations
```
Then edit `migrations/env.py`'s `target_metadata` to import from
`app.models` (created in Phase 1) — leave as `target_metadata = None` for
now since `app/models.py` doesn't exist yet; Phase 1 Task 1 sets this.
Set `sqlalchemy.url` in `alembic.ini` to read from `app.config.get_settings()`
rather than a hardcoded value — replace the `run_migrations_online`
connection setup in `env.py` with:

```python
from app.config import get_settings
config.set_main_option("sqlalchemy.url", get_settings().database_url)
```

- [ ] **Step 3: Create `tests/conftest.py`** — spins up a per-test-session
  transaction that's rolled back, so tests don't leave data behind. (Phase
  1 will add the actual schema-creation fixture once tables exist; this
  step just wires the DB connection for tests.)

```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import async_session


@pytest.fixture
async def db_session() -> AsyncSession:
    async with async_session() as session:
        yield session
        await session.rollback()
```

- [ ] **Step 4: Bring up local Postgres and verify connectivity**

```bash
docker compose up -d postgres
python -c "
import asyncio
from app.db import engine
async def check():
    async with engine.connect() as conn:
        print('connected:', conn)
asyncio.run(check())
"
```
Expected: prints `connected: <AsyncConnection ...>` with no error.

- [ ] **Step 5: Commit**

```bash
git add app/db.py alembic.ini migrations tests/conftest.py
git commit -m "chore: wire async SQLAlchemy engine and Alembic"
```

---

### Task 3: CI-equivalent local check script

Small but worth doing now so every later phase has one command to run
before calling a task done.

**Files:**
- Create: `ticketd-api/scripts/check.sh`

- [ ] **Step 1: Create the script**

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose up -d postgres
# wait for postgres to accept connections
for i in $(seq 1 30); do
  docker compose exec -T postgres pg_isready -U ticketd && break
  sleep 1
done
alembic upgrade head
pytest -v
```

- [ ] **Step 2: Make it executable and run it**

```bash
chmod +x scripts/check.sh
./scripts/check.sh
```
Expected: all tests pass (just `test_healthz` at this point — Phase 1 adds
`alembic upgrade head` a real target once migrations exist; until then
`alembic upgrade head` on an empty migrations dir is a no-op and exits 0).

- [ ] **Step 3: Commit**

```bash
git add scripts/check.sh
git commit -m "chore: add local check script (postgres + migrations + tests)"
```

---

## Definition of done for this phase

- `./scripts/check.sh` runs clean from a fresh clone (after `pip install -e
  ".[dev]"`).
- `uvicorn app.main:app --reload` serves `GET /healthz` → `200 {"ok": true}`.
- Nothing in `ticketd/` (the legacy app) was modified.
