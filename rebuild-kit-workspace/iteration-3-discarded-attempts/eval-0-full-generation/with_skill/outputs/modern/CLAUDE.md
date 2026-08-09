# modern/ — Target Application

## Target stack  <!-- decided by: leadership + team, at commissioning (PB-004) -->
- Language/runtime: Python 3.11+           - Framework: FastAPI
- Database: PostgreSQL                      - Key libraries: SQLAlchemy 2.x (or SQLModel) +
  Alembic for migrations, Pydantic v2 for request/response models, an async task queue for
  notification dispatch (choice is FREE — e.g. FastAPI `BackgroundTasks` for M0, upgrading to a
  real broker like Redis/RQ or Celery is a FREE choice left to the WO that builds it, see WO-002)
- Rationale: PB-004 — team's standing FastAPI/Postgres expertise, no framework bake-off in scope.

## Architecture rules
- **No synchronous SMTP in a request handler, ever** (PB-001). Notification dispatch is a
  distinct component from the request path; ticket-close and reset-request handlers enqueue and
  return, they do not wait on mail delivery. This is the one architectural rule this rewrite
  exists to enforce — treat any PR that reintroduces in-request `smtplib` calls as a regression.
- **Reset tokens are never stored in a form that lets a table leak become an account takeover**
  (PB-002). Outcome required: single-use, short-lived, unguessable, and the stored form does not
  let anyone who reads the table mint a valid reset without also knowing the plaintext token.
  Mechanism is FREE (e.g. cryptographically random token, only a salted hash stored, or Postgres
  `pgcrypto`) — record the choice made in the ledger's `free_choices`.
- **Slugs are unique at the database level** (PB-003, `UNIQUE` constraint on `tickets.slug`).
  Collision-resolution algorithm is OQ-001 — do not invent one silently; ship the placeholder
  from OQ-001's reading B (id-suffix-on-collision) only until ruled, and flag it.
- **Every documented legacy quirk the UI depends on is FIXED, not cleaned up**, unless a WO's
  fidelity tag says otherwise (e.g. `GET /api/tickets/<id>` on a missing ticket returns `200 {}`,
  not `404` — `legacy/app/server.py:61-63`, PB-005 freezes this). If a quirk looks like a bug
  with no PB entry sanctioning a fix, it's FIXED, and any objection goes to `open-questions.md`
  as a PB proposal — never a silent fix.
- **No new client-visible fields, renamed fields, or removed fields** on any endpoint currently
  exposed to the UI, per PB-005. `docs/contracts/openapi.yaml` is binding.

## Conventions
- Layout: standard FastAPI app layout — `modern/app/main.py` (app factory + route registration),
  `modern/app/routers/` (one module per legacy route group: tickets, auth, export), `modern/app/
  models.py` (SQLAlchemy models), `modern/app/schemas.py` (Pydantic request/response models),
  `modern/app/notify.py` (notification dispatch, replacing `legacy/app/notify.py`'s synchronous
  version), `modern/app/db.py` (session/engine setup), `modern/alembic/` (migrations).
- Naming: mirror legacy field names in Pydantic schemas exactly where the contract must match
  (`id`, `title`, `slug`, `priority`, `status`, `assignee_id`, `created_at`, `closed_at`) — this
  is a frozen contract (PB-005), not a place for "nicer" naming.
- Error handling: FastAPI `HTTPException` per documented error shape in
  `docs/contracts/openapi.yaml`; a handler must not invent a new error body shape for an existing
  endpoint without an OQ ruling.
- Timestamps: legacy used naive local time (`datetime.now().isoformat()`,
  `legacy/app/server.py:52`, explicitly flagged in-source as a footgun: "naive local time!"). The
  target behavior is an OQ candidate if a WO wants to fix it — see the corresponding WO's
  fidelity tags before assuming UTC is safe; changing wall-clock semantics on stored timestamps
  can silently break UI sort/filter behavior PB-005 protects.
- Logging: structured logs (stdlib `logging` + JSON formatter is sufficient) at the point
  notification dispatch enqueues and at the point it actually sends/fails — this is the
  observability PB-001 was missing; no requirement to build more than that for M0.
- Test layout: `modern/tests/` mirrors `modern/app/`; characterization tests generated in P7 land
  under `verification/characterization/` and are referenced from `modern/tests/` by WOs, not
  duplicated.

## What this file is not
Not a spec. Behavior comes from work orders and contracts; this file only governs HOW code is
written here. On conflict, the WO wins and the conflict is an `open-questions.md` entry.
