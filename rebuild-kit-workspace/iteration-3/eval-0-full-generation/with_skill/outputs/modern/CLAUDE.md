# modern/ — Target Application

## Target stack  <!-- decided by: Nicholas Stelter (product/eng owner) · 2026-08-09 -->
- Language/runtime: Python 3.12          - Framework: FastAPI
- Database: PostgreSQL 16                - Key libraries: SQLAlchemy 2.x (async) or asyncpg direct
  (FREE — pick one in WO-000/M0 and record the choice in the ledger), Pydantic v2 (FastAPI's
  native validation), Alembic (migrations), an async task queue for notification dispatch (FREE —
  candidates: FastAPI `BackgroundTasks` for M0 simplicity vs. a real broker like Redis/RQ or
  Postgres-backed outbox for durability; PB-001 requires non-blocking, not any specific mechanism)
- Rationale: "FastAPI + Postgres, our team's expertise" (PB-005, verbatim). Not derived from a
  technical requirement — the team's own stated proficiency was the deciding factor.

## Architecture rules
- **No side effect that talks to an external system (SMTP, or anything added later) may run
  synchronously inside a request handler that a client is waiting on** (PB-001). This is the
  single load-bearing rule this whole rewrite exists to enforce — apply it even to functionality
  added later that PB-001 didn't originally anticipate.
- **No credential or bearer-token material is stored in recoverable form** (PB-002). Hash
  reset tokens at rest (not MD5); treat "stored in a bare table forever" as the antipattern to
  avoid generally, not just for reset tokens — give any future token/secret table an expiry story
  from day one.
- **Every FIXED behavior in a work order is a contract, not a suggestion** (PB-006, no UI changes)
  — response shape, status code, and field-type flexibility (e.g. `priority` as int-or-string)
  must match legacy exactly where tagged FIXED. Do not "improve" these opportunistically; file an
  OQ if one looks wrong.
- Given the app's size (6 endpoints, 3 tables), do not introduce layering, DI frameworks, or
  abstractions the legacy app's complexity doesn't warrant — a handful of FastAPI routers + a thin
  data-access layer over SQLAlchemy/asyncpg is the right altitude. Match effort to scale.

## Conventions
- **Layout**: `modern/app/` mirrors the route grouping conceptually (tickets, auth) but as a
  proper package (`app/main.py`, `app/routers/tickets.py`, `app/routers/auth.py`,
  `app/db.py`, `app/models.py`/`app/schemas.py` for Pydantic, `app/notify.py` for the
  now-async notification dispatch, `app/tasks.py` if a queue mechanism is chosen). Choose the
  exact module boundaries in WO-000/M0 and record them — this is a FREE choice, not prescribed
  further here.
- **Migrations**: Alembic, one migration per schema change, checked in under
  `modern/alembic/versions/`. `docs/contracts/ddl.sql` is the target-state DDL to converge on, not
  a script to run directly.
- **Error handling shape**: FastAPI's standard `HTTPException` + a shared JSON error envelope;
  preserve legacy's exact status codes and bodies wherever a behavior is tagged FIXED (e.g.
  `422 {"error": "title_required"}`, `429 {"error": "rate_limited"}`,
  `403 {"error": "invalid_token"}`) — these are contract, not convention.
- **Logging**: structured (JSON) request logging at minimum; PB-004's unresolved 5xx root-cause
  gap (OQ-005) is a strong argument for adding real error tracking here even though it's not a
  hard requirement — FREE choice, but lean toward doing it.
- **Test layout**: `modern/tests/` mirrors `verification/characterization/` fixture usage;
  characterization tests import the same golden fixtures the L2 harness uses so there's one
  source of truth for expected behavior, not two.

## What this file is not
Not a spec. Behavior comes from work orders and contracts; this file only governs HOW code is
written here. On conflict, the WO wins and the conflict is an `open-questions.md` entry.
