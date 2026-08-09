# ticketd (rewrite)

FastAPI + Postgres rewrite of the legacy Flask/SQLite `ticketd` internal
ticket tracker (source at `../ticketd-nohistory`, handed off without git
history, access logs, or production DB access).

**Read `docs/AUDIT.md`, `docs/DESIGN.md`, and `docs/OPEN_QUESTIONS.md` before
changing behavior.** This rewrite deliberately preserves legacy quirks it
couldn't verify (see those docs) — several things that look like bugs are
intentional parity choices, not oversights.

## What's fixed vs. what's preserved

- **Fixed**: notification emails no longer send synchronously inside
  requests (now a Postgres-backed outbox + background worker); password
  reset tokens are no longer MD5 (now `secrets.token_urlsafe`, stored only
  as a sha256 hash).
- **Preserved as-is**: the `200 {}` response for a missing ticket, dual-format
  `priority` input, no pagination on list, the `X-Internal-Bypass` header,
  non-unique slugs. See `docs/OPEN_QUESTIONS.md` for why, and what evidence
  would justify changing each one.
- **Not ported**: `legacy_import.py` (dead one-off spreadsheet importer).

## Local development

```bash
cp .env.example .env
docker compose up -d db
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

Or run everything in containers: `docker compose up --build`.

## Tests

Tests run against a real Postgres database (not SQLite — see
`docs/DESIGN.md` on why dialect drift is exactly the kind of gap we're
trying to close). With `docker compose up -d db` running:

```bash
pip install -e ".[dev]"
pytest
```

Set `TEST_DATABASE_URL` to point at a different scratch database if you
don't want to reuse the dev one.

## Migrating real data

No production DB access yet. Once it exists, see `docs/MIGRATION_PLAN.md`
and `scripts/migrate_from_sqlite.py`.

## Project layout

```
app/
  main.py             FastAPI app + lifespan (starts/stops the outbox worker)
  config.py            Settings (env vars, see .env.example)
  db.py                 Async SQLAlchemy engine/session
  models.py            ORM models
  schemas.py            Pydantic request/response models
  security.py            Reset token generation + hashing
  util.py                slugify (matches legacy, including its collision behavior)
  routers/                tickets.py, auth.py, export.py
  notifications/            outbox.py (enqueue), worker.py (drain loop), smtp_backend.py
migrations/            Alembic, versions/0001_initial.py is the full schema
scripts/                 migrate_from_sqlite.py — one-time legacy data import
docs/                       AUDIT.md, DESIGN.md, OPEN_QUESTIONS.md, MIGRATION_PLAN.md
```
