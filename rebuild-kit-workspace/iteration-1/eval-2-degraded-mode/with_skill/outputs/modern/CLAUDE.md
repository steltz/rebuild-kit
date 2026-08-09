# modern/ — Target Application

## Target stack  <!-- decided by: owner (handover request) · 2026-08-08 -->
- Language/runtime: Python 3.12+
- Framework: FastAPI (async), uvicorn
- Database: PostgreSQL 16 (SQLAlchemy 2.x + Alembic migrations; asyncpg driver)
- Key libraries: pydantic v2 (request/response models), httpx (test client),
  a background job path for email dispatch (see PB-001; mechanism is a FREE choice —
  candidates: transactional outbox table + worker, or FastAPI BackgroundTasks as the
  minimum acceptable step; pick once, record in ledger `free_choices`)
- Rationale: stack named by the owner in the intake request (PB-003). Postgres replaces
  SQLite; async framework enables PB-001's repair (no synchronous SMTP inside requests).

## Architecture rules
- PB-001 (sync email blocks requests): **no network I/O to SMTP inside a request handler.**
  All notification sends go through a dispatch seam (interface) whose production
  implementation is asynchronous/queued and whose test implementation records sends for
  the replay harness to inspect.
- PB-002 (MD5 reset tokens): all secret-token generation uses CSPRNG (`secrets`); tokens
  are stored hashed (sha256 at minimum) — never store the presentable token at rest.
- Boundary fidelity: API surface is defined by `docs/contracts/openapi.yaml`. FIXED response
  shapes — including legacy quirks like 200-with-`{}` on missing ticket — are contract, not
  style; do not "clean them up" without a ruling.
- All timestamps produced by the modern app are UTC ISO-8601. NOTE: legacy writes naive
  local time (`ticketd/app/server.py:52`); the diff rules normalize timestamps, and the
  migration mapping owns the conversion. Do not imitate naive-localtime.
- Keep domain logic out of route functions where a rule is shared (slug generation, priority
  normalization) so characterization tests can hit it directly.

## Conventions
- Layout: `modern/app/` (routers/, models/, services/, db/), `modern/tests/`,
  `modern/alembic/`.
- Errors: JSON bodies matching the legacy error shapes recorded in contracts
  (e.g. `{"error": "title_required"}` with 422) — error *shape* is part of the frozen surface.
- Config via environment (pydantic-settings); no hardcoded hostnames (legacy hardcodes
  `smtp.internal` — do not port that pattern).
- Tests: pytest; characterization tests live in `verification/characterization/` and run
  against modern via the harness; unit tests live in `modern/tests/`.

## What this file is not
Not a spec. Behavior comes from work orders and contracts; this file only governs HOW code is
written here. On conflict, the WO wins and the conflict is an open-questions.md entry.
