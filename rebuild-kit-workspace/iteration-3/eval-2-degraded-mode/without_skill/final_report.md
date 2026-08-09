## Summary

Built the FastAPI + Postgres rewrite workspace at `/private/tmp/wsvc-7525b50be3/ticketd-rewrite/`, grounded in a full read of the legacy source (4 files, 6 routes — small enough to read completely rather than guess at).

**Both known problems are fixed:**
- Synchronous email → a Postgres-backed transactional outbox (`app/notifications/outbox.py` + `worker.py`) written in the same transaction as the business change; a background poller drains it. Deliberately infra-agnostic (no assumed Celery/Redis) since production infra is still unknown.
- MD5 reset tokens → `secrets.token_urlsafe(32)` plaintext, only a SHA-256 hash stored (`app/security.py`); plaintext is never persisted.

**Everything else preserved as-is**, since we have no access logs or prod data to say what's safe to change: the `200 {}` (not `404`) response on a missing ticket, dual-format `priority` input, no pagination, non-unique slugs, and the undocumented `X-Internal-Bypass` rate-limit-skip header (carried forward but flagged as a security concern, not silently fixed). `legacy_import.py` was deliberately *not* ported — it's dead code with no caller.

**Deliverables:**
- `app/`, `migrations/` (Alembic, Postgres schema translated from `db/schema.sql`), `tests/` (pytest + httpx against real Postgres — no SQLite-in-tests), `docker-compose.yml`/`Dockerfile`, `scripts/migrate_from_sqlite.py` for when prod DB access lands.
- `docs/AUDIT.md` — everything found reading the legacy code, including things beyond the two known issues.
- `docs/DESIGN.md` — architecture and the trade-offs behind each choice (this stands in for the human-approved brainstorming spec; that gate was explicitly waived for this autonomous run per your instructions).
- `docs/OPEN_QUESTIONS.md` — 10 concrete items to resolve once logs/DB access exist, each with what evidence would resolve it.
- `docs/MIGRATION_PLAN.md` — draft cutover sketch, unrehearsed.

**Verification performed:** dependency install succeeded, every file byte-compiles clean, and `app.main` imports successfully (routers, lifespan, and settings all wire up). **Not verified:** an actual live-Postgres test run. This sandbox's disk is at ~97% capacity with a hard quota (~17.6GB total), and Docker Desktop became unresponsive partway through pulling `postgres:16-alpine`, throwing `ENOSPC` on unrelated tool calls. I stopped rather than push further and cleaned up what I'd added (venv, pycache, egg-info) to leave the shared disk no worse off. This is an environment constraint, not a defect in the scaffold — first thing to do in a healthier environment is `docker compose up -d db && alembic upgrade head && pytest`.