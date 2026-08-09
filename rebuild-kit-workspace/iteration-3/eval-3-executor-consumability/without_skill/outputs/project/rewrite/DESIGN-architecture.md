# Design: architecture and data model (FastAPI + Postgres)

Companion docs: `DESIGN-async-notifications.md`,
`DESIGN-password-reset.md`, `DESIGN-slug-collisions.md`. This doc covers
everything that's shared infrastructure: project layout, the Postgres
schema, and how each legacy endpoint maps onto the new stack.

## Service shape

One FastAPI application (`api`) plus one lightweight background worker
process (`worker`) that drains an outbox table. Both talk to the same
Postgres database. No new infrastructure dependency (no Redis, no
Celery/RabbitMQ/SQS) — the team's stack is FastAPI + Postgres, and a
Postgres-backed outbox is enough for this system's actual volume (39 reset
requests + 99 closes in the sampled hour; even at 10x that, a poll-based
worker is trivially sufficient). See `DESIGN-async-notifications.md` for why
outbox-over-BackgroundTasks.

```
ticketd-api/
  app/
    main.py              # FastAPI app, route registration
    db.py                 # engine/session setup (SQLAlchemy or asyncpg — pick one, see plans/00)
    models.py              # ORM/table definitions
    schemas.py              # Pydantic request/response models
    routes/
      tickets.py            # GET/POST /api/tickets, GET/POST .../close
      auth.py                # /api/auth/reset, /api/auth/reset/confirm
      export.py               # /internal/export/csv (pending open question)
    services/
      slugs.py                 # slug generation + collision handling
      tokens.py                 # reset token hashing/generation
      outbox.py                 # enqueue_notification()
    worker.py                    # standalone process: polls outbox, sends mail, retries
    config.py                     # settings (DB URL, SMTP config, rate limit, reset window)
  migrations/                      # Alembic
  tests/
  pyproject.toml
```

Why a separate `worker.py` process rather than `BackgroundTasks` or an
in-process scheduler thread: see `DESIGN-async-notifications.md`. Short
version — `BackgroundTasks` still runs inside the API process and still dies
with it; a separate worker means the API can restart, redeploy, or crash
without losing queued notifications, and the outbox table means "email sent"
becomes durable and retriable instead of "email attempted once, synchronously,
best-effort."

## Data model (Postgres)

```sql
CREATE TABLE users (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email       TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL
);

CREATE TABLE tickets (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title        TEXT NOT NULL,
    slug         TEXT NOT NULL,
    priority     TEXT NOT NULL CHECK (priority IN ('low', 'med', 'high')),
    status       TEXT NOT NULL CHECK (status IN ('open', 'closed')) DEFAULT 'open',
    assignee_id  BIGINT REFERENCES users(id),  -- carried over, unused; see open questions
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at    TIMESTAMPTZ
);

-- FIX: the legacy schema has no uniqueness on slug at all. See
-- DESIGN-slug-collisions.md for the generation algorithm that makes
-- this constraint safe to add (i.e. that guarantees INSERTs succeed
-- without the caller retrying).
CREATE UNIQUE INDEX tickets_slug_key ON tickets (slug);
CREATE INDEX tickets_status_created_at_idx ON tickets (status, created_at DESC);
-- ^ supports the two real query shapes: list-all-ordered, list-by-status-ordered.

-- FIX: replaces the legacy bare reset_tokens table. Stores a hash of the
-- token, never the token itself. See DESIGN-password-reset.md.
CREATE TABLE reset_tokens (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email       TEXT NOT NULL,
    token_hash  TEXT NOT NULL UNIQUE,       -- sha256 hex digest of the random token
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at  TIMESTAMPTZ NOT NULL,
    used_at     TIMESTAMPTZ
);
CREATE INDEX reset_tokens_email_created_idx ON reset_tokens (email, created_at);
-- ^ supports the rate-limit query: count tokens for an email in the last hour.

-- NEW: durable outbox for notification email. See DESIGN-async-notifications.md.
CREATE TABLE notification_outbox (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    to_address    TEXT NOT NULL,
    subject       TEXT NOT NULL DEFAULT '',
    body          TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    attempts      INT NOT NULL DEFAULT 0,
    last_attempt_at TIMESTAMPTZ,
    last_error    TEXT,
    sent_at       TIMESTAMPTZ    -- NULL = pending/failed, non-NULL = delivered
);
CREATE INDEX notification_outbox_pending_idx ON notification_outbox (created_at)
    WHERE sent_at IS NULL;
```

`reset_tokens.email` is intentionally still a free-text column, not a FK to
`users` — the legacy behavior of accepting *any* email string (not just
registered users) and still returning `{"ok": true}` is an anti-enumeration
property worth keeping (see behavior contract §"POST /api/auth/reset"). Do
not add a `users` existence check here without an explicit decision to do so
— it would be a silent behavior change with security implications
(enumeration), not a neutral cleanup.

## Timestamps

Legacy: naive local server time, no offset, e.g. `"2026-07-12T10:00:00.123"`.
That's a real bug (server timezone dependence, ambiguous across
daylight-saving transitions) but the literal string is what the UI has
always received and rendered. Postgres stores `TIMESTAMPTZ` correctly in
UTC internally regardless of what we do at the API boundary — that part is
free. The open question is what the **API response** should look like; see
`03-OPEN-QUESTIONS.md` item 3. Until that's answered, `schemas.py` should
serialize timestamps through a single shared function
(`format_legacy_timestamp()`) so the format can be changed in one place
rather than hunting through every route.

## Endpoint mapping

| Legacy route | New route | Behavior change? |
|---|---|---|
| `GET /api/tickets` | `GET /api/tickets` | None. Same filter param, same unpaginated default, same ordering. May *add* optional `limit`/`cursor` params (additive only). |
| `POST /api/tickets` | `POST /api/tickets` | `priority` validation returns `422` instead of crashing to `500` (bugfix, see behavior contract). Slug collision now resolved instead of silently duplicated (named fix). |
| `GET /api/tickets/<id>` | `GET /api/tickets/{id}` | None — still `200 {}` for unknown id, not `404`. |
| `POST /api/tickets/<id>/close` | `POST /api/tickets/{id}/close` | Response shape unchanged (`{"closed": bool}`); email is now enqueued to the outbox instead of sent inline (named fix). Request no longer fails/500s because of an SMTP problem. |
| `POST /api/auth/reset` | `POST /api/auth/reset` | Response shape unchanged; token generation/storage is the named security fix (transparent to the API contract). Rate limit and `X-Internal-Bypass` header behavior preserved pending the open question about the bypass header. |
| `POST /api/auth/reset/confirm` | `POST /api/auth/reset/confirm` | Response shape and non-disclosure property unchanged. |
| `GET /internal/export/csv` | pending open question | See `03-OPEN-QUESTIONS.md` item 5 — zero traffic in the sample log, cheap to keep, candidate to drop. |
| (n/a — `app/legacy_import.py`) | not ported | Dead code, confirmed unused. |

## Non-goals (repeat from `00-CONTEXT-AND-CONSTRAINTS.md`, stated here for anyone starting mid-plan)

No auth/authz added, no pagination forced onto the UI, no new endpoints, no
`assignee_id` feature work, no UI changes.
