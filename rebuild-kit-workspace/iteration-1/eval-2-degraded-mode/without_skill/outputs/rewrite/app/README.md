# ticketd rewrite — FastAPI + Postgres scaffold

Wire-compatible reimplementation of legacy ticketd (see `../inventory/` and the ADRs
before touching anything — several apparent bugs in here are deliberate, marked with
`Q<N>` comments referencing `../inventory/behavior-inventory.md`).

## Run

```bash
cd rewrite/app
python -m venv .venv && . .venv/bin/activate
pip install -e .
createdb ticketd && psql ticketd -f ../sql/001_initial.sql

export TICKETD_DATABASE_URL=postgresql+psycopg://localhost/ticketd
uvicorn app.main:app --port 5000          # API
python -m app.workers.outbox_worker      # email worker (separate process)
```

Configuration is env-driven (prefix `TICKETD_`), see `app/config.py`. Notable:
`TICKETD_LEGACY_TZ` **must** be set to the legacy server's timezone before parity
testing timestamps or migrating data (ADR-004 — currently unknown, placeholder UTC).

## Design notes

- Sync SQLAlchemy 2.0 + psycopg. An internal tracker does not need async I/O; FastAPI
  runs sync endpoints in a threadpool. Switching to asyncpg later is mechanical.
- Request bodies on compat routes are parsed by hand, not by Pydantic models — legacy
  error bodies and lenient parsing (Q3/Q5) are part of the wire contract (ADR-003).
- Email goes through the `outbox_emails` table in the same transaction as the state
  change; `app/workers/outbox_worker.py` delivers it (ADR-001).
- No auth, matching legacy (Q1) — do not expose this beyond whatever network boundary
  protects legacy today.
