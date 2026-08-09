# modern/ — Target Application

## Target stack  <!-- decided by: rewrite requester (task intake) · 2026-08-08 -->
- Language/runtime: Python 3.12        - Framework: FastAPI
- Database: PostgreSQL                 - Key libraries: SQLAlchemy 2.x (async) or psycopg3 +
  raw SQL (FREE — pick one in WO-001 and record the choice; app is small enough either works),
  Pydantic v2 for request/response models, `secrets` stdlib module for token generation
  (PB-002), an async task mechanism for email dispatch (PB-001 — FastAPI `BackgroundTasks` is
  sufficient for this app's scale; an external queue is FREE if a WO's author wants one, but is
  not required by any evidence gathered so far).
- Rationale: Stated directly by the human in the rewrite request. No further rationale (why
  FastAPI/Postgres specifically, ORM preference, hosting target) was given — open intake
  question, see `docs/problem-brief.md`.

## Architecture rules
- **PB-001 (sync email blocks requests):** no request handler may perform network I/O to the
  mail transport inline. Ticket-close and reset-request handlers enqueue a dispatch (FastAPI
  `BackgroundTasks`, or a table-backed outbox if a WO chooses that FREE option) and return before
  the send completes. This is the one non-negotiable architecture rule this rewrite exists to
  enforce — see WO-004.
- **PB-002 (MD5 reset tokens):** reset tokens are generated with `secrets.token_urlsafe` (or
  equivalent CSPRNG), never a hash of low-entropy input. See WO-003.
- **No framework types leak into domain logic that must stay portable across the (currently
  undecided) SQLAlchemy-vs-raw-SQL choice** — keep a thin repository layer so WO-001's FREE
  choice doesn't ripple through every other WO. This is a precaution, not evidenced by a brief
  grievance (none was given about the current monolith's testability) — treat it as a default,
  not a mandate; a WO may override it with a documented FREE rationale.
- All timestamps are stored and emitted as timezone-aware UTC. Legacy used naive local time
  (`datetime.now().isoformat()`, `app/server.py:52`) — this is flagged as a probable defect via
  PB-proposal `docs/open-questions.md#OQ-001` (nobody reported it, so it is not auto-REPAIRed;
  ported as FIXED — naive-local — until a human rules). Do not silently switch to UTC without
  that ruling landing first, even though it is the obviously-better default.

## Conventions
- Layout: standard FastAPI layout — `modern/app/{main.py, api/, models/, schemas/, services/,
  db.py}`; tests under `modern/tests/` mirroring `app/`.
- Naming: keep legacy route paths and JSON field names identical unless a WO's contract says
  otherwise (`docs/contracts/openapi.yaml` is the source of truth, not this file).
- Error handling: FastAPI `HTTPException` with the same status codes and body shapes the
  contracts specify — several of those shapes are deliberately legacy-faithful (e.g. `GET
  /api/tickets/{id}` on a missing ticket returns `200 {}`, not `404` — FIXED, evidenced,
  preserved; see WO-002).
- Logging: structured (stdlib `logging` + JSON formatter is sufficient); no specific target was
  given, so treat as FREE within "must not block the request path" (ties back to PB-001's spirit).
- Test layout: characterization tests generated in `verification/characterization/` are the
  acceptance floor (L2); `modern/tests/` may hold additional unit tests but they do not replace
  L2/L3.

## What this file is not
Not a spec. Behavior comes from work orders and contracts; this file only governs HOW code is
written here. On conflict, the WO wins and the conflict is an open-questions.md entry.
