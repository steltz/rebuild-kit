# modern/ — Target Application

## Target stack  <!-- decided by: leadership (PB-004) · 2026-08-08 -->
- Language/runtime: Python 3.12          - Framework: FastAPI
- Database: PostgreSQL (target 15+)      - Key libraries: SQLAlchemy 2.x (or the team's
  preferred async driver — `asyncpg`/`psycopg`), Pydantic v2 for request/response models, a
  background-task mechanism for PB-001 (in-process `BackgroundTasks`/ARQ/Celery — pick one in
  WO-002, it's a `FREE` choice; see rationale below), `passlib`/`secrets` for PB-002 tokens.
- Rationale: "The new stack is decided: FastAPI + Postgres, our team's expertise" (PB-004,
  verbatim from leadership). No further constraint was given on ORM, task queue, or hosting —
  those are `FREE` choices per WO, recorded in `ledger.json` when made.

## Architecture rules

- **PB-001 (sync email took down ticket-closing for 40 min).** No request handler may perform
  network I/O to the mail transport synchronously. Ticket-close and reset-request handlers
  enqueue a notification and return; delivery happens out-of-band. Mechanism is `FREE`
  (FastAPI `BackgroundTasks` is sufficient for outcome parity; a durable queue/outbox is a
  stronger guarantee if OIQ-1's SLO turns out to require at-least-once delivery — ruling
  pending). Whatever is chosen, a downed mail transport must **never** make `POST
  /api/tickets/{id}/close` or `POST /api/auth/reset` fail or hang.
- **PB-002 (MD5 tokens in a bare table).** Reset tokens: generate with `secrets.token_urlsafe`
  (or equivalent CSPRNG), never derived from user-controllable or guessable input. Store only a
  hash of the token (e.g. SHA-256) plus expiry, never the raw token, in a properly keyed table
  (primary key, index on the hash, index on email for the rate-limit query, `NOT NULL` expiry
  column enforced at the DB level in addition to app-level checks). Single-use (delete or mark
  consumed on confirm) and same-response-body-for-invalid-and-expired are both `FIXED` legacy
  behaviors — preserve them; PB-002 is about the token's cryptographic strength and storage,
  not the disclosure policy.
- **PB-003 (slug collisions).** `tickets.slug` must be `UNIQUE` at the database level
  (currently unenforced — this alone is new, uncontested REPAIR scope). The collision
  *resolution* mechanism is blocked on OQ-001 — do not invent one; if WO-005 comes up in the
  frontier before OQ-001 is ruled, skip it and continue elsewhere per the executor loop.
- **No UI changes (PB-005).** The HTTP contract in `docs/contracts/openapi.yaml` is `FIXED`
  unless a WO says REPAIR. This explicitly includes the two documented historical quirks:
  `GET /api/tickets/{id}` on a missing id returns `200 {}`, not `404`; `POST /api/tickets`
  accepts `priority` as either `"1"/"2"/"3"` or `"low"/"med"/"high"` and normalizes both.
  Reproduce these exactly even though they look wrong — "no UI changes" means the client code
  that depends on them is out of your control.
- **Auth (OIQ-4/OQ-002, unresolved).** The legacy app has no authentication code at all. Do not
  add auth speculatively — that is unsanctioned scope creep. Do not assume it's safe to omit
  it, either — get the OQ-002 ruling. Milestone 0 is scoped to be inert either way (see
  `backlog.md`); everything past M0 that touches request identity is blocked on this ruling.

## Conventions

- **Layout**: `modern/app/` mirrors the legacy package shape loosely (`api/` routers,
  `models/` SQLAlchemy + Pydantic schemas, `services/` for the notification/token logic that
  used to be inline, `db/` for session/engine setup and Alembic migrations). Exact layout is
  `FREE`; keep it because *some* structure was chosen, not because this document mandates
  these exact names — record the actual choice in `ledger.json` free_choices when WO-001 (or
  whichever WO first creates the skeleton) closes.
- **Error handling / response shape**: match the legacy JSON error bodies exactly where a WO is
  `FIXED` (e.g. `{"error": "title_required"}` with 422, `{"error": "invalid_token"}` with 403,
  `{"error": "rate_limited"}` with 429) — use FastAPI `HTTPException` with explicit `detail`
  matching the legacy shape, not FastAPI's default validation-error envelope, which differs.
- **Timestamps**: legacy stores naive local time via `datetime.now().isoformat()` (flagged as
  an unsanctioned-looking quirk, not yet a PB entry — see `docs/open-questions.md` OQ-003 PB
  proposal). Until ruled, new code stores UTC-aware timestamps in Postgres (`timestamptz`) and
  the API layer formats output to match whatever the ruling decides; do not let this decision
  block unrelated WOs.
- **Testing**: characterization tests (L2) live under `verification/characterization/`; new
  `modern/` code should also carry ordinary FastAPI/pytest unit tests colocated in
  `modern/tests/`, but those are supplementary — the replay harness (L3) is the acceptance
  oracle, not a substitute for it.
- **Logging**: legacy has none beyond the ops access log format sampled in `ticketd/ops/access.log`.
  Structured logging is `FREE`; if you add it, don't let it change response bodies or headers
  covered by `diff-rules.yaml`.

## What this file is not
Not a spec. Behavior comes from work orders and contracts; this file only governs HOW code is
written here. On conflict, the WO wins and the conflict is an open-questions.md entry.
