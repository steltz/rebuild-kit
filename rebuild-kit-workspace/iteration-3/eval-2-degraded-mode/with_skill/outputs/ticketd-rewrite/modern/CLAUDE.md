# modern/ — Target Application

## Target stack  <!-- decided by: task owner (Nicholas Stelter) · 2026-08-09 -->
- Language/runtime: Python 3.12       - Framework: FastAPI
- Database: PostgreSQL                - Key libraries: SQLAlchemy 2.x (async) or asyncpg
  directly (FREE — executor's choice, record in ledger notes), Pydantic v2 (via FastAPI),
  Alembic for migrations, a task queue or FastAPI `BackgroundTasks` for async email dispatch
  per WO-004 (mechanism is FREE; outcome — non-blocking dispatch — is required by PB-001/NFR-001).
- Rationale: Stated directly by the task owner in the rewrite request (not inferred from a PB
  entry) — this is a plain stack decision, no further justification recorded.

## Architecture rules
- PB-001 (sync email blocks requests): no request handler may perform network I/O to SMTP (or
  any external notification channel) synchronously. All email dispatch goes through an
  async-safe boundary (background task, queue, or outbox) chosen per WO-004's FREE mechanism
  ruling. This is the single load-bearing NFR of the rewrite (NFR-001).
- PB-002 (MD5 reset tokens): no credential/token generation may use MD5 or any non-CSPRNG
  source. Use `secrets` (stdlib) or an equivalent vetted CSPRNG for anything security-sensitive
  (WO-003).
- No behavior may silently diverge from a `FIXED` spec item. If a legacy quirk looks wrong but
  has no PB citation (e.g. the `GET /api/tickets/<id>` 200-with-empty-object-instead-of-404
  behavior at legacy/app/server.py:58-64, explicitly marked "the legacy UI depends on it"), it
  ships as specified — do not "fix" it. Propose changes to `open-questions.md` instead; changes
  land only through a human ruling (Design Principle 9).
- Keep IO (DB, SMTP/queue) behind interfaces / dependency-injected boundaries so handlers stay
  testable without a live Postgres or SMTP server — supports L1/L2 verification running without
  the twin-boot harness for fast local iteration.

## Conventions
- Layout: standard FastAPI app package (`modern/app/`) with `routers/`, `models/` (SQLAlchemy),
  `schemas/` (Pydantic), `services/` (business logic incl. email dispatch), `db.py` (session/
  engine setup), `main.py` (app factory). Alembic migrations under `modern/alembic/`.
- Naming: mirror legacy field names where they're part of the contract (`title`, `slug`,
  `priority`, `status`, `created_at`, `closed_at`, `assignee_id`) so contract diffing in
  `docs/contracts/` stays legible against legacy citations.
- Error handling: FastAPI `HTTPException` with the legacy-equivalent status codes where a
  behavior is `FIXED` (e.g. 422 on missing title, 429 on rate limit, 403 on invalid/expired
  reset token — all preserved, see WO specs); new REPAIR/FREE code paths may use whatever
  idiomatic FastAPI error shape modern/CLAUDE.md conventions settle on, recorded per-WO.
- Logging: structured (JSON) logging at minimum for the async email dispatch path, since PB-001
  makes SMTP failures a first-class operational concern going forward — this is a FREE choice on
  mechanism, but "email failures must be observable" is implied by the PB-001 motivation and
  should not be silently swallowed.
- Test layout: `modern/tests/` mirroring `app/`; characterization tests generated in P7 land
  under `verification/characterization/` and import from `modern/` rather than duplicating
  fixtures.

## What this file is not
Not a spec. Behavior comes from work orders and contracts; this file only governs HOW code is
written here. On conflict, the WO wins and the conflict is an open-questions.md entry.
