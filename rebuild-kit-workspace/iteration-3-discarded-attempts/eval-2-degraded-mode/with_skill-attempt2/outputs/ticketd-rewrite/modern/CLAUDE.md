# modern/ — Target Application

## Target stack  <!-- decided by: Nicholas Stelter (direct instruction, non-interactive intake) · 2026-08-09 -->
- Language/runtime: Python 3.12    - Framework: FastAPI
- Database: PostgreSQL             - Key libraries: SQLAlchemy 2.x (async) + Alembic, Pydantic v2,
  `arq` or FastAPI `BackgroundTasks`-backed outbox for async email (see WO-002), `passlib`/`secrets`
  for token generation (see WO-001), `psycopg` (async driver)
- Rationale: explicit user instruction ("Target stack is FastAPI + Postgres"). No further
  rationale (e.g. team language preference, ops constraints) was supplied — recorded as a gap
  in `docs/problem-brief.md` open intake questions, not invented here.

## Architecture rules
- All outbound email goes through an outbox/queue, never a synchronous call inside a request
  handler (PB-001, WO-002). A request handler enqueues; a separate worker/task sends. This is the
  single non-negotiable architecture rule this rewrite exists to enforce.
- Password-reset token generation must use a cryptographically secure random source
  (`secrets.token_urlsafe` or equivalent), never a hash of guessable/low-entropy input (PB-002,
  WO-001). Token comparison must be constant-time.
- No framework types (FastAPI `Request`/`Response`, SQLAlchemy `Session`) leak into domain/service
  logic — routers are thin, translating HTTP <-> domain calls. This isn't sourced from a PB (no
  grievance was reported about testability), but it's the idiomatic FastAPI-service shape and
  is FREE per the fidelity taxonomy: no legacy behavior constrains it.
- Async I/O throughout (async SQLAlchemy session, async endpoints) — idiomatic for FastAPI, FREE
  choice, not a ported legacy behavior.

## Conventions
- Layout: `modern/app/{api,domain,db,workers}/`, `modern/tests/`, `modern/alembic/`. (FREE —
  no legacy convention to preserve; standard FastAPI project shape.)
- Naming: snake_case throughout, matching legacy column/field names where they carry through
  unchanged (`title`, `slug`, `priority`, `status`, `assignee_id`, `created_at`, `closed_at`) so
  contract diffs stay legible.
- Error handling: domain exceptions raised in services, translated to HTTP status/JSON at the
  router boundary via FastAPI exception handlers — not ad hoc `try/except` per route.
- Logging: structured (JSON) logging via stdlib `logging` + a JSON formatter; no legacy logging
  existed to match (the legacy app has none).
- Tests: `modern/tests/unit/`, `modern/tests/characterization/` (mirrors
  `verification/characterization/`), `modern/tests/contract/` (validates against
  `docs/contracts/openapi.yaml`).
- Migrations: Alembic, one migration per schema-affecting WO; `docs/contracts/ddl.sql` is the
  target-state reference, not applied directly.

## What this file is not
Not a spec. Behavior comes from work orders and contracts; this file only governs HOW code is
written here. On conflict, the WO wins and the conflict is an open-questions.md entry.
