# ticketd rewrite — design

Status: **self-approved, autonomous run.** Normal process would have a human
review this before implementation; that person was explicitly unavailable
for this run, and the run was authorized to proceed on defensible choices
and log the rest as open questions (see `OPEN_QUESTIONS.md`). Treat this doc
as a first draft for the team to amend, not a ratified spec.

## Goals

1. Fix the two confirmed problems (sync email-in-request, MD5 reset tokens).
2. Move off SQLite/Flask onto the target stack (FastAPI + Postgres) without
   silently changing behavior we have no evidence about.
3. Leave a workspace that's ready to receive real evidence (access logs,
   prod DB) in a few weeks without a second rewrite.

## Approach considered

**A. Faithful port + targeted fixes (chosen).** Keep the same six routes,
same request/response shapes, same quirks (200-not-404, dual-format
priority, no pagination), same table structure translated to Postgres types.
Only the two confirmed problems get architectural changes. Everything else
is flagged, not changed.

- *Why chosen*: we have no access logs and no prod DB — we cannot tell which
  quirks are load-bearing for existing clients and which are accidents. The
  handover explicitly says the two issues are "genuinely all we know," which
  reads as an instruction to not go hunting for more behavior changes on
  spec. A faithful port minimizes the risk of an invisible breaking change on
  cutover.

**B. Clean-slate redesign** (fix everything found in the audit: real 404s,
unique slugs, UTC timestamps, remove the bypass header, add pagination).
Rejected for now — every one of those changes is plausible-but-unverified
risk with zero clients we can check against. Logged as follow-up work in
`OPEN_QUESTIONS.md` to revisit once logs/DB access exist.

**C. Strangler-fig proxy in front of the legacy Flask app**, migrating routes
one at a time. Rejected: the whole app is ~120 lines and 6 routes; the
overhead of a proxy layer isn't justified at this size, and the user asked
for "the rewrite workspace," not an incremental-migration harness.

## Architecture

```
app/
  main.py            FastAPI app, lifespan (DB engine, outbox worker startup/shutdown)
  config.py           Settings via pydantic-settings (env vars)
  db.py                Async SQLAlchemy engine/session
  models.py           ORM models: Ticket, User, ResetToken, OutboxMessage
  schemas.py          Pydantic request/response models
  security.py          Reset token generation + hashing
  dependencies.py       DB session dependency, rate-limit dependency
  routers/
    tickets.py         list/create/get/close
    auth.py             reset request/confirm
    export.py             csv export
  notifications/
    interface.py         NotificationBackend protocol
    smtp_backend.py         SMTP implementation (mirrors legacy notify.py)
    outbox.py             enqueue() — writes a row, returns immediately
    worker.py               background poller that drains the outbox
```

### Fix 1: synchronous email → transactional outbox

Rather than assuming a message broker exists in production (unknown — no
infra access yet), notifications go through a Postgres-backed outbox table
(`outbox_messages`): the request handler inserts a row in the same
transaction as the business change (ticket close / reset request) and
returns immediately. A background asyncio task, started in the FastAPI
`lifespan`, polls the table (`status='pending'`) and sends via SMTP, with a
capped retry count and `status` tracking (`pending` → `sent` | `failed`).

This is deliberately infra-agnostic: it needs nothing beyond the Postgres
database we're already using. `NotificationBackend` is a small protocol
(`send(to, subject, body) -> None`) so the SMTP implementation can be swapped
for Celery/RQ/SQS/etc. later without touching the routers — see
`OPEN_QUESTIONS.md` for when that swap is likely worth it (rough guide:
once you know real infra and real volume).

Trade-off accepted: an in-process asyncio poller is not durable across
process restarts mid-send and isn't horizontally-coordinated (two replicas
would both poll — mitigated with `FOR UPDATE SKIP LOCKED` in the poll query).
Good enough for current known volume (a handful of ticket closes / resets);
revisit if that assumption breaks.

### Fix 2: MD5 reset tokens → random token + hashed storage

`secrets.token_urlsafe(32)` generates the token (not derived from email or
time — no guessable input). The plaintext token is emailed to the user and
**never stored**; only `sha256(token)` is stored in `reset_tokens.token_hash`.
Confirm hashes the incoming token and looks up by hash. This preserves the
existing behavior (rate limit, 30-minute window, same-response-for-
invalid-and-expired to avoid disclosure) while fixing both the weak
generation and the plaintext-at-rest exposure.

### Everything else: preserved as-is

- `GET /api/tickets/<id>` on missing ticket → `200 {}` (not `404`), per the
  legacy comment claiming UI dependency.
- `priority` accepts `"1"/"2"/"3"` or `"low"/"med"/"high"`.
- No pagination on list.
- `X-Internal-Bypass: 1` still bypasses the reset rate limit — carried
  forward unchanged, but flagged loudly in `OPEN_QUESTIONS.md` as a security
  concern worth fixing with real service-auth once we know who's supposed to
  use it. Not fixed silently because we don't know what currently depends on
  it working exactly this way.
- Slugs are not deduplicated (matches legacy).
- CSV export endpoint ported as-is.

### Data model changes (SQLite → Postgres)

- `INTEGER PRIMARY KEY` → `BIGSERIAL PRIMARY KEY` (`id`).
- `TEXT`/`DATETIME` → `VARCHAR`/`TIMESTAMPTZ`. Timestamps are now written in
  UTC via `TIMESTAMPTZ` — this is a behavior change from the legacy naive
  local time, but it's a storage-layer fix with no observable API change
  (API still returns ISO 8601 strings), so it's made without flagging it as
  an open question.
- `reset_tokens.token` → `reset_tokens.token_hash` (see Fix 2). Added a
  surrogate `id BIGSERIAL PRIMARY KEY` (legacy table had no PK).
- New `outbox_messages` table for Fix 1.
- `CHECK` constraints on `priority`/`status` kept as-is (not moved to Postgres
  ENUM, to keep migration/rollback simple and match legacy's loose typing).

### Testing

Async `httpx.AsyncClient` against the FastAPI app, with a real Postgres test
database (via `docker-compose.yml`, or any reachable Postgres — see
`README.md`). Not SQLite-in-tests: the whole point of the rewrite is
Postgres, and SQLite/Postgres dialect drift (exactly the kind of gap this
contractor handoff already suffered from) is not worth reintroducing.

### Migration path for real data (once DB access exists)

`scripts/migrate_from_sqlite.py` reads the legacy `db/ticketd.sqlite3` file
and loads `tickets`/`users` into the new Postgres schema. `reset_tokens` are
**not** migrated — they're short-lived (30 min) and MD5-derived; simplest and
safest to let them expire naturally and not carry weak tokens into the new
system. See `MIGRATION_PLAN.md`.

## Self-review notes

- Placeholder scan: none found — every section above has a concrete answer,
  not a TBD.
- Consistency: outbox design in this doc matches the schema in
  `migrations/versions/0001_initial.py` and the code in `app/notifications/`.
- Scope: bounded to the six existing routes + the two confirmed fixes;
  clean-slate improvements deferred to `OPEN_QUESTIONS.md` rather than
  smuggled into this pass.
- Ambiguity: "X-Internal-Bypass" behavior was ambiguous (fix vs. preserve) —
  resolved as preserve-but-flag, per the scope-boundary rule in `AUDIT.md`.
