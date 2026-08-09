# ticketd — FastAPI + Postgres rewrite (workspace)

Generated from the legacy `../ticketd` source (Flask + SQLite) with no other
evidence available (no git history, no access logs, no production DB
access). Read `../docs/00-EVIDENCE-AND-ASSUMPTIONS.md` first — it explains
what this workspace does and does not claim to know.

## What's here

- `app/` — FastAPI app. Endpoint-for-endpoint port of `../ticketd/app/server.py`.
- `db/schema.postgres.sql` — target Postgres schema.
- `tests/` — parity tests, each citing the legacy source line it protects.
- `docker-compose.yml` / `Dockerfile` — local dev only (Postgres + API + worker).

## Fixed vs. preserved

Only the two problems named in the handover were fixed:

1. **Synchronous notification email** → transactional outbox
   (`notification_outbox` table, `app/services/notify.py`, `app/worker.py`).
   Run the worker (`python -m app.worker`) alongside the API — without it,
   queued notifications never send.
2. **MD5 reset tokens** → `secrets.token_urlsafe` + SHA-256 hash at rest
   (`app/services/tokens.py`).

Everything else observed in the legacy source — including things that look
like bugs (200-instead-of-404 on a missing ticket, no pagination, dual
priority formats, an undocumented rate-limit bypass header, non-unique
slugs) — is preserved exactly. See
`../docs/01-LEGACY-BEHAVIOR-INVENTORY.md` for the full list and why each one
was left alone, and `../docs/03-OPEN-QUESTIONS-AND-RISK-REGISTER.md` for
what evidence would let each be revisited.

## Running locally

```bash
docker compose up --build
# API:    http://localhost:8000
# health: http://localhost:8000/healthz
```

Or without Docker:

```bash
pip install -e ".[dev]"
createdb ticketd   # or point TICKETD_DATABASE_URL elsewhere
psql "$TICKETD_DATABASE_URL" -f db/schema.postgres.sql
uvicorn app.main:app --reload
python -m app.worker   # separate terminal — required for notifications to send
```

## Tests

```bash
pip install -e ".[dev]"
pytest
```

Tests run against an in-memory SQLite engine so they don't require a running
Postgres instance (see `tests/conftest.py` for why). All 14 pass as of this
handoff (`pip install -e ".[dev]"` into a fresh venv, then `pytest -q`). They
have **not** been run against real Postgres — do that before trusting this
as a merge gate, since SQLite and Postgres differ in ways that already
needed workarounds here (see `BigIntPK` in `app/models.py` and `_as_utc` in
`app/routers/auth.py`).

## What's deliberately not here

- **A data migration script.** Writing one now, untested against real data,
  would create false confidence. See `../docs/02-MIGRATION-PLAN.md` for the
  shape it needs to take once DB access exists.
- **Auth/authn for `/internal/export/csv`.** Ported as unauthenticated,
  matching the source. Flagged, not fixed — see the risk register.
- **Any inferred SLA, sizing, or traffic-based tuning.** None was available.
