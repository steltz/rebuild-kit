# modern/ — Target Application

## Target stack  <!-- decided by: Nicholas Stelter (intake request) · 2026-08-09 -->
- Language/runtime: Python 3.12
- Framework: FastAPI
- Database: PostgreSQL
- Key libraries (FREE choice, not re-litigated per WO): SQLAlchemy 2.x (async) + Alembic for
  migrations, `asyncpg` driver, Pydantic v2 for request/response models (FastAPI native),
  `arq` or FastAPI `BackgroundTasks` + a durable outbox table for async email dispatch (PB-001 —
  see WO-002/WO-004; a bare in-process `BackgroundTasks` call does not survive a process restart,
  so prefer a persisted outbox row + worker even though FastAPI's built-in mechanism is simpler —
  record whichever is actually chosen in the ledger as a FREE choice), `secrets` stdlib module for
  reset-token generation (PB-002).
- Rationale: stack given directly in the rewrite request, no PB citation beyond the user's
  instruction. FastAPI's async model directly addresses PB-001 (sync SMTP blocking the request
  thread) — the target framework was chosen with that defect in mind, so leaning into async I/O
  throughout (not just for email) is consistent with the brief's intent even though only email
  dispatch was named as broken.

## Architecture rules
- All outbound I/O (SMTP, and DB access) behind async interfaces — PB-001 exists because the
  legacy app couldn't separate "handle the request" from "send the email"; don't recreate that
  coupling with a different framework. Notification sending must be a decoupled unit (outbox row
  + worker/background task), not a direct call inside a request handler.
- Password reset tokens: generate with `secrets.token_urlsafe`, never `hashlib.md5` or any other
  non-CSPRNG source (PB-002). Store tokens hashed at rest (e.g. SHA-256 of the token, compared in
  constant time) if a WO's outcome requirements allow it without breaking the "expired == invalid,
  same error body" non-disclosure behavior that stays FIXED from legacy.
- No endpoint currently has authentication (see OQ-001 in `docs/open-questions.md`) — do not add
  auth speculatively; wait for the ruling. If the ruling adds auth, it becomes a WO of its own,
  not something folded silently into unrelated WOs.
- Framework types (Pydantic models, FastAPI `Request`/`Response`) stay at the API boundary; domain
  logic (ticket state transitions, slug generation, token lifecycle) should be plain Python so it
  is unit-testable without booting FastAPI — there's no legacy grievance forcing this, but it
  costs nothing at this scale and keeps L2 characterization tests fast.

## Conventions
- Layout: `modern/app/` mirrors legacy's flat-module shape given the app's size (`main.py` for the
  FastAPI app + routers, `models.py` for SQLAlchemy models, `schemas.py` for Pydantic
  request/response models, `notify.py` for the outbox/worker, `db.py` for session/engine setup) —
  don't over-split a 4-file app into a deep package tree.
- Naming: keep legacy field/route vocabulary where it's already the domain vocabulary (`tickets`,
  `slug`, `priority`, `status`, `reset_tokens`) — see `docs/domain/glossary.md`. Don't rename for
  the sake of it; renames are a FREE choice, not a mandate.
- Error shape: FastAPI's default `{"detail": ...}` on `HTTPException` diverges from legacy's
  `{"error": "<code>"}` bodies — this is a REPAIR-vs-FIXED question per endpoint; contracts in
  `docs/contracts/openapi.yaml` record the legacy-observed shape as the frozen boundary. Preserve
  legacy error body shapes (`{"error": "title_required"}`, `{"error": "rate_limited"}`, etc.)
  exactly for endpoints tagged FIXED; only diverge where a WO's REPAIR/expected-divergence entry
  says so.
- Logging: legacy has none. FREE choice — structured logging (stdlib `logging` with JSON
  formatter, or `structlog`) is reasonable for an internal tool; not a brief-driven requirement.
- Test layout: `modern/tests/` mirrors `verification/characterization/` feature grouping so a WO's
  `acceptance.tests` path resolves directly.

## What this file is not
Not a spec. Behavior comes from work orders and contracts; this file only governs HOW code is
written here. On conflict, the WO wins and the conflict is an open-questions.md entry.
