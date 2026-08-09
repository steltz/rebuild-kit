# 00 — Overview

## What ticketd is

Internal ticket tracker, in production since 2019. Flask 1.x, SQLite file DB
(`db/ticketd.sqlite3`), one blocking SMTP notifier. Single known client: the internal UI
(`svc-ui/2.1`), which authenticates upstream (every access-log line carries a corporate
email as the authenticated user — the app itself has **no auth middleware**; see
`decisions/open-questions.md` Q4).

## Why we are rewriting (drivers, in priority order)

1. **Availability**: notification email is sent synchronously inside request handlers
   (`app/notify.py`, 30 s SMTP timeout). The June SMTP outage made `POST
   /api/tickets/{id}/close` hang/fail for ~40 minutes. Requirement: **no request handler may
   ever wait on SMTP.** Email delivery must be durable across process crashes (an accepted
   close must eventually notify even if the app restarts).
2. **Security**: password-reset tokens are `md5(email + time.time())`, stored in plaintext in
   a bare `reset_tokens` table (no PK, no index, no expiry column; expiry is computed in
   code). Security has flagged this. Requirement: unguessable tokens, hashed at rest,
   explicit expiry, single-use. See `specs/05-security-reset.md`.
3. **Correctness**: `slugify()` collides ("Fix DB" and "fix db!" → same slug) and the schema
   has no uniqueness constraint, so duplicates are silently stored. **The fix is undecided**
   — see `decisions/open-questions.md` Q1.

## Target stack (decided — do not revisit)

- Python 3.12+, **FastAPI** (async), Pydantic v2 models.
- **PostgreSQL** 15+ via SQLAlchemy 2.x (async) + Alembic migrations.
- pytest + httpx for tests; the contract suite in `verification/contract_tests/` runs
  against a live base URL so it can target legacy and new alike.
- A small notification worker process (same codebase, separate entrypoint) draining a
  transactional outbox table. No new broker infrastructure. Rationale in
  `specs/04-notifications.md`.

## Scope

**In scope**
- All 6 live API endpoints (see `specs/02-api-contract.md`), bug-for-bug compatible where
  the legacy UI depends on quirks.
- New Postgres schema + Alembic baseline (`specs/03-data-model.md`).
- One-shot data migration script SQLite → Postgres.
- Async, durable notifications (outbox + worker).
- Reset-token redesign.
- Contract/parity test suite and cutover checklist.

**Out of scope (explicit)**
- **Any UI change.** The API surface the UI consumes must not change shape.
- Adding authentication/authorization to ticket endpoints (legacy has none; changing this
  would be a client-visible change — flagged in open questions, not done here).
- Pagination of `GET /api/tickets` (the UI fetches everything and filters client-side —
  legacy code comment confirms). Note it as future work only.
- `app/legacy_import.py` (2019 one-off spreadsheet importer, nothing imports it) — not
  ported.
- `GET /internal/export/csv` — **DROP, pending Q3**: written for the 2020 audit, code
  comment says no caller since, and the 30-day access log shows **zero** hits. Its CSV is
  also malformed (no quoting of commas in titles). See Q3 before final removal.

## Success criteria

1. Contract suite green against the new service for every PRESERVE row in
   `specs/01-legacy-inventory.md`.
2. `POST /api/tickets/{id}/close` p99 latency independent of SMTP health; kill the SMTP
   endpoint in a test and closing still returns 200 while the notification lands after SMTP
   recovers.
3. No MD5 anywhere; reset tokens pass the checklist in `specs/05-security-reset.md`.
4. Data migration verified row-count- and field-exact per `verification/verification.md`.
