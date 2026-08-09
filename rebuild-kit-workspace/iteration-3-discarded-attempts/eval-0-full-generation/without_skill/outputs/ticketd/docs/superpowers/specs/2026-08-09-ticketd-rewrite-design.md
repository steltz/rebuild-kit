# ticketd Rewrite — Design

**Status:** Drafted autonomously, no stakeholder review yet. See "Open Questions" — treat every item there as blocking sign-off, not blocking the plan's existence.
**Date:** 2026-08-09
**Author:** Claude (autonomous background session), on behalf of nicholas.stelter@gmail.com

## 1. Problem Statement

ticketd is a Flask 1.x / SQLite app (`app/server.py`, ~120 lines) that has run since 2019 with three known problems:

1. **Synchronous email blocks the request thread.** `close_ticket()` and `request_reset()` both call `send_mail()` inline (`app/notify.py`), which opens a blocking SMTP connection with a 30s timeout. During the June 2026 SMTP outage, closing tickets was unavailable for 40 minutes — not because the ticket-close logic failed, but because every request thread was parked waiting on a dead SMTP server.
2. **Password-reset tokens are MD5 hashes in a bare table.** `hashlib.md5(f"{email}{time.time()}")` is fast to brute-force and predictable (email + timestamp, and timestamps are guessable to within request latency). The `reset_tokens` table stores the plaintext-equivalent token directly — no hashing at rest, no single-use enforcement in the schema, no `used_at`.
3. **Slug collisions.** `slugify()` (`app/util.py`) normalizes titles into a slug but nothing enforces uniqueness — "Fix DB" and "fix db!" both produce `fix-db`. Support has hit this repeatedly; no fix has been agreed on.

Leadership approved a full rewrite onto the team's existing FastAPI + Postgres stack. **UI changes are explicitly out of scope** — `svc-ui` (the only observed client, per `ops/access.log`) must keep working against the same API contract.

## 2. What We Learned From the Current Code and Logs

Read in full: `app/server.py`, `app/notify.py`, `app/util.py`, `app/legacy_import.py`, `db/schema.sql`, and `ops/access.log` (2,000 requests, one simulated hour on 2026-07-12, single user `jdoe@corp.example.com`, single client `svc-ui/2.1`, 253 distinct source IPs).

- **Endpoint usage** (from the log): `GET /api/tickets` (1,235), `POST /api/tickets` (423), `GET /api/tickets/{id}` (~230), `POST /api/tickets/{id}/close` (~130), `POST /api/auth/reset` (39), `POST /api/auth/reset/confirm` (20). `GET /internal/export/csv` never appears — **it has no observed caller**.
- **Error rate**: 51/2000 requests (2.6%) return 500, spread across `GET /api/tickets`, `POST /api/tickets`, and a handful of `/close` and single-ticket `GET`s, with no obvious single cause visible in a combined access log (no stack traces available). Treat as background flakiness in the legacy app to be aware of, not a specific bug to reproduce — the rewrite's own test suite is the real defense here.
- **Rate limiting works as coded**: exactly one `429` in the sample, on `POST /api/auth/reset`, consistent with the 3/hour limit.
- **`/close` requests are visibly slower** than everything else — up to 0.364s vs. 0.01–0.07s typical for reads/writes — which lines up with the inline SMTP call (fast in this sample because SMTP was healthy; the June outage is what happens when it isn't).
- The access log is **only one simulated hour**, one user, one user-agent, despite being described as a "~30-day" log. It's useful for endpoint mix and shape, not for real traffic volume, concurrency, or a genuine slug-collision example — none of the logged titles are visible (bodies aren't logged), so no real collision pair could be extracted from it. Treat any capacity/concurrency assumption below as a placeholder pending real metrics.
- **No tests exist anywhere in the repo.** No CI config, no Dockerfile. The rewrite starts from zero test coverage on the legacy app, so behavior preservation must be verified against `server.py`'s source and the quirks called out below, not against an existing test suite.
- `app/legacy_import.py` is dead code (module docstring says so, nothing imports it). Not carried into the rewrite.
- Three "hotfix" commits and a "util tweak" commit exist in history with no diff content visible beyond a changed line count — treat `server.py` as the sole source of truth for current behavior; don't assume undocumented intent behind those commits.

## 3. Contract to Preserve (no UI changes means no API changes)

The new service must be a drop-in replacement for `svc-ui`. These are the concrete quirks in the current code that look like bugs but are load-bearing:

| # | Quirk | Location | Preserve as |
|---|---|---|---|
| 1 | `GET /api/tickets/{id}` returns **200 with `{}`**, not 404, when the ticket doesn't exist | `server.py:58-64` | Exact same: 200, `{}` |
| 2 | `POST /api/tickets` accepts `priority` as `"1"`/`"2"`/`"3"` (mapped to low/med/high) **or** `"low"`/`"med"`/`"high"` directly, defaults to `"med"` | `server.py:47-49` | Exact same coercion |
| 3 | `POST /api/tickets` response body is only `{"id": ..., "slug": ...}` (not the full ticket) | `server.py:50-55` | Exact same shape |
| 4 | `GET /api/tickets` has no pagination — full table dump, `ORDER BY created_at DESC`, optional `?status=` filter | `server.py:27-37` | Exact same (pagination would be a UI change; UI is out of scope) |
| 5 | `POST /api/auth/reset/confirm` returns **the same generic `invalid_token` / 403** for both expired and unknown tokens (deliberate non-disclosure) | `server.py:98-108` | Exact same non-disclosure behavior |
| 6 | `POST /api/auth/reset` rate limit: 3/hour per email, `429 rate_limited` when exceeded | `server.py:80-95` | Exact same limit and error shape |
| 7 | `GET /internal/export/csv` — `id,title,status` CSV, `text/csv` | `server.py:111-115` | Ported as-is. No observed caller in the log, but removing it isn't part of "fix the three known problems," so it stays. Flagged in Open Questions as a candidate for a future, separate deprecation. |
| 8 | `title` required, empty/whitespace-only rejected with `422 title_required` | `server.py:43-45` | Exact same |

Field names in JSON responses (`id`, `title`, `slug`, `priority`, `status`, `assignee_id`, `created_at`, `closed_at`) are preserved exactly — `svc-ui` deserializes these by name.

**Not preserved, and why that's still "no UI change":**
- `created_at`/`closed_at` move from naive local time (`datetime.now().isoformat()`, whatever timezone the old server host happened to be in) to timezone-aware UTC ISO-8601. This changes the *string value* of timestamps, which is a real behavior change `svc-ui` could observationally notice if it does timezone-naive string comparisons — flagged in Open Questions. It's necessary because "preserve the naive-local-time bug" isn't a defensible choice for a rewrite whose whole premise is fixing known problems.

## 4. Architecture

```
                        ┌─────────────┐
  svc-ui  ─────HTTP────▶│  FastAPI app │──────┐
                        └─────────────┘      │ same transaction:
                               │              │ INSERT ticket/token
                               │              │ INSERT outbox row
                               ▼              │
                        ┌─────────────┐      │
                        │  Postgres   │◀─────┘
                        │  (tickets,  │
                        │  users,     │◀─────┐
                        │  reset_     │      │ poll for pending
                        │  tokens,    │      │ rows, SKIP LOCKED
                        │  outbox_    │      │
                        │  events)    │──────┘
                        └─────────────┘
                               ▲
                               │ mark sent/failed
                        ┌─────────────┐
                        │ worker.py    │────SMTP────▶ smtp.internal:25
                        │ (separate    │
                        │  process)    │
                        └─────────────┘
```

**Stack:** FastAPI, SQLAlchemy 2.0 async ORM + `asyncpg`, Alembic for schema migrations, Pydantic v2 for request/response models, `pytest` + `httpx.AsyncClient` + `pytest-postgresql` for tests. Postgres 15+.

### 4.1 Async notification — transactional outbox, not a new message broker

**Decision:** implement the outbox pattern directly on Postgres rather than adding Celery/RQ + Redis.

**Why:** nothing in this repo or its ops directory shows Redis (or any broker) already running. Introducing one adds an operational dependency (deploy, monitor, patch, another single point of failure) to fix a problem that's really just "don't do I/O synchronously in the request." Postgres is already the datastore; `SELECT ... FOR UPDATE SKIP LOCKED` gives safe concurrent polling without a broker. This is the minimal-infrastructure fix. If the team already runs Redis/Celery elsewhere for other services, that's a reasonable substitute — see Open Questions.

**Design:**
- New table `outbox_events`: `id`, `event_type` (`ticket_closed` | `reset_requested`), `payload` (JSONB — recipient + rendered body fields), `status` (`pending` | `sent` | `failed`), `attempts` (int, default 0), `created_at`, `sent_at` (nullable), `last_error` (nullable text).
- `close_ticket()` and `request_reset()` insert their outbox row **in the same DB transaction** as the ticket-status update / token insert. If the transaction commits, the notification is guaranteed to be queued — no "ticket closed but nobody notified" gap, and no notification for a close that got rolled back.
- `app/worker.py` is a standalone process (`python -m app.worker`) that loops: claim up to N pending rows where `next_attempt_at` has passed via `FOR UPDATE SKIP LOCKED`, call `send_mail()` (same SMTP client, now parameterized — see 4.4), mark `sent` or increment `attempts`/set `last_error`/push `next_attempt_at` out with exponential backoff (base 5s, cap 5 minutes), and mark `failed` (dead-letter, stops retrying) after 5 attempts. Poll interval 1s; low volume (per the log, well under 1 req/sec) doesn't justify LISTEN/NOTIFY complexity, but the poll query is cheap and indexed on `(status, next_attempt_at)` so it isn't a bottleneck if volume grows.
- The request path's job ends at "row is committed." SMTP being down no longer touches the request/response cycle at all — this directly fixes the June outage.

### 4.2 Password reset — secure tokens, single-use, no plaintext at rest

**Decision:**
- Generate the token with `secrets.token_urlsafe(32)` (256 bits of entropy from `os.urandom`), not MD5 of guessable inputs.
- Store only `sha256(token)` in the `reset_tokens` table as `token_hash` — the raw token is never persisted, only emailed to the user. A DB dump can't be used to forge a reset.
- New columns: `id`, `email`, `token_hash` (unique, indexed), `created_at`, `expires_at` (computed at insert time as `created_at + 30min`, matching the existing `RESET_WINDOW_MIN`), `used_at` (nullable). `confirm_reset` sets `used_at` and treats an already-used token identically to an expired/unknown one (still the same generic `invalid_token`/403 — quirk #5 above still holds, it's just now also correct security practice instead of an accident).
- Rate limiting (3/hour/email) is preserved, but the current `X-Internal-Bypass: 1` header is **not** carried forward. It's an unauthenticated, undocumented way to skip rate limiting entirely — the access log can't tell us who uses it (headers aren't logged), so this is a judgment call, not a verified-safe removal. See Open Questions.

### 4.3 Slug collisions

Nobody had decided the intended fix; this rewrite needs one to ship, so here's the chosen approach — **flag for confirmation, don't block on it**:

**Decision:** slugs stay unique and human-readable. On collision, append `-2`, `-3`, ... to the base slug (first ticket with a given base slug keeps the bare slug; the pattern matches what GitHub/GitLab do for repo/project names, which the team likely already recognizes). Enforced two ways:
1. A DB `UNIQUE` constraint on `tickets.slug` — the source of truth, so a race between two concurrent creates can't both win the same slug.
2. `create_ticket()` computes the base slug, then attempts insert; on a unique-violation it retries with `-2`, `-3`, ... up to 50 attempts, then falls back to appending the DB-generated ticket id (`{base}-{id}`, which is unique by construction) so ticket creation can never fail outright because of a slug clash.

`id` (not `slug`) remains the canonical identifier for routing — `GET /api/tickets/{id}` already routes by integer id today, so this fix doesn't touch the URL contract at all. `slug` is a display field.

### 4.4 Configuration

`app/notify.py`'s SMTP target (`smtp.internal:25`) and the sender address become environment-configured (`SMTP_HOST`, `SMTP_PORT`, `MAIL_FROM`) via Pydantic Settings, defaulting to today's hardcoded values for parity. This is standard 12-factor config, not a UI-visible change, and it's needed anyway once there's a worker process plus an API process that both need the same SMTP config.

## 5. Data Model (Postgres)

```sql
CREATE TABLE users (
    id          BIGSERIAL PRIMARY KEY,
    email       TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL
);

CREATE TABLE tickets (
    id          BIGSERIAL PRIMARY KEY,
    title       TEXT NOT NULL,
    slug        TEXT NOT NULL UNIQUE,
    priority    TEXT NOT NULL CHECK (priority IN ('low', 'med', 'high')),
    status      TEXT NOT NULL CHECK (status IN ('open', 'closed')),
    assignee_id BIGINT REFERENCES users(id),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at   TIMESTAMPTZ
);
CREATE INDEX ix_tickets_status ON tickets(status);
CREATE INDEX ix_tickets_created_at ON tickets(created_at DESC);

CREATE TABLE reset_tokens (
    id          BIGSERIAL PRIMARY KEY,
    email       TEXT NOT NULL,
    token_hash  TEXT NOT NULL UNIQUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at  TIMESTAMPTZ NOT NULL,
    used_at     TIMESTAMPTZ
);
CREATE INDEX ix_reset_tokens_email_created ON reset_tokens(email, created_at);

CREATE TABLE outbox_events (
    id               BIGSERIAL PRIMARY KEY,
    event_type       TEXT NOT NULL CHECK (event_type IN ('ticket_closed', 'reset_requested')),
    payload          JSONB NOT NULL,
    status           TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'sent', 'failed')),
    attempts         INTEGER NOT NULL DEFAULT 0,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    next_attempt_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    sent_at          TIMESTAMPTZ,
    last_error       TEXT
);
CREATE INDEX ix_outbox_events_status_next_attempt ON outbox_events(status, next_attempt_at);
```

Managed via Alembic from the start (one initial migration = this schema), so future schema changes have a real migration path — the legacy app had none.

## 6. Data Migration (SQLite → Postgres)

One-time script, `scripts/migrate_from_sqlite.py`, run once during cutover:

- Copies `users` and `tickets` as-is (types map directly). `tickets.slug` gets re-validated against the new `UNIQUE` constraint at migration time — collisions in existing data get the same `-2`/`-3` treatment as new tickets, applied in `id` order so migration is deterministic and repeatable.
- **`reset_tokens` is deliberately NOT migrated.** Existing tokens are MD5-based, short-lived (30 min window) security debt; by the time a migration runs they're expired garbage, and even if some were live, carrying insecure tokens forward into the new schema defeats the point of fixing them. Anyone mid-reset at cutover time just requests a new one.
- **Timestamp conversion requires a source timezone, and the script must not guess one.** `datetime.now().isoformat()` in the old code is naive — nothing in this repo records what timezone the app server ran in. The migration script takes a **required** `--source-tz` argument (e.g. `--source-tz=America/New_York`) with no default; it errors out immediately if omitted, rather than silently assuming UTC and quietly corrupting every historical timestamp by however many hours off that guess is. See Open Questions — this value must come from whoever operated the old server, not from this design doc.
- Script is re-runnable against a fresh empty Postgres schema (not incremental/idempotent against partial runs — the cutover runbook in the verification doc treats it as a single all-or-nothing step: truncate-and-reload if it needs to be re-run).

## 7. Testing Strategy (see also `docs/superpowers/verification/2026-08-09-ticketd-rewrite-verification.md`)

- `pytest-postgresql` provides an ephemeral local Postgres per test session (no Docker requirement) — Alembic migrations run against it once per session; tests share the schema and clean up rows per-test via transaction rollback.
- **Contract tests** (`tests/test_contract_quirks.py`) exist specifically to pin the 8 quirks in section 3 — these are the regression barrier against silently changing `svc-ui`-visible behavior, since the old app had zero tests to diff against.
- **Notification tests** assert the outbox row is written in the same transaction as the ticket-close/reset-request, and that the HTTP response returns without waiting on `send_mail` (achieved by not calling it from the request path at all — verified by mocking `send_mail` to raise/hang and confirming the endpoint still responds fast).
- **Worker tests** cover: claims pending rows, marks sent on success, backs off and retries on failure, dead-letters after 5 attempts, and doesn't double-send when two worker instances poll concurrently (via `SKIP LOCKED`).
- **Security tests**: no MD5 anywhere in the new codebase; `reset_tokens.token_hash` is not reversible to the mailed token; used and expired tokens both produce the generic error; rate limit still triggers at the 4th request/hour.
- **Slug tests**: collision produces `-2`, `-3` deterministically; concurrent creates with the same title don't both win the bare slug (exercise the DB unique constraint under concurrency, not just the retry loop in isolation).

## 8. Explicitly Out of Scope

- Any change to `svc-ui` or any other client.
- New endpoints or fields beyond what's needed to fix the three known problems (no pagination, no new ticket fields, no auth/login system beyond the existing reset flow).
- Removing `GET /internal/export/csv` (unused per the log, but removing unused-but-not-broken endpoints isn't one of the three problems this rewrite is chartered to fix).
- Production deployment orchestration (specific hosting target, secrets manager, load balancer config) — see Open Questions.

## 9. Open Questions

These are genuine unknowns this design had to resolve one way or another to keep moving, made autonomously because no one was available to ask. Each is a real decision point — surface these before the plan below is executed for real, not after:

1. **Source timezone for the legacy `datetime.now()` timestamps.** Required for `scripts/migrate_from_sqlite.py --source-tz=...`. Guessing wrong silently shifts every historical `created_at`/`closed_at` by a fixed offset. Needs whoever ran the old server's host (or its deploy config) to confirm.
2. **`X-Internal-Bypass: 1` header on `/api/auth/reset`.** This design drops it (unauthenticated rate-limit bypass is a security smell), but the access log has no header data, so there's no way to confirm from the data available whether some internal tool (a support script, a health check) currently depends on it. If something does, it needs a real replacement (a service-to-service auth token, not a magic string) before cutover, not a silent removal.
3. **Is Redis/Celery already running somewhere in this org's infra?** If so, using the existing broker instead of a Postgres outbox may be the better-trodden path for this team. This design chose the outbox specifically to avoid assuming infrastructure that isn't evidenced anywhere in this repo.
4. **`GET /internal/export/csv`'s real caller.** The access log shows zero hits in the sampled hour, and it's not referenced by `svc-ui`'s observed traffic, but a 1-hour sample can't prove "never used" (e.g. a monthly audit script). Kept as-is as the safe default; worth a real answer before anyone considers deprecating it.
5. **Deployment target.** Nothing in this repo (no Dockerfile, no CI, no infra-as-code) indicates where ticketd actually runs today or where the FastAPI rewrite should run. The plan below produces a Dockerfile and a `docker-compose.yml` for local dev, but the actual cutover (DNS/service discovery, secrets, monitoring hookup) needs input from whoever owns that infra.
6. **The `users` table and `assignee_id` have no create/update endpoint anywhere in the current API.** Nothing in `server.py` populates `users` — it's presumably seeded some other way (admin tooling? direct SQL? another service?) that isn't in this repo. The rewrite preserves the column and FK as-is without inventing new endpoints for it (out of scope per leadership's UI freeze — assignment UI, if any, isn't in `svc-ui`'s observed traffic either), but if user provisioning happens via a mechanism not visible in this repo, that mechanism needs to keep working against the new `users` table too.
7. **51/2000 (2.6%) `500`s in the access log sample have no visible root cause** (no stack traces in a combined access log). This design treats them as "legacy app flakiness the new test suite should simply not reproduce" rather than chasing a specific bug, since there's nothing here to root-cause. Worth a sentence of confirmation that this wasn't a known, still-relevant issue.

## 10. Spec Self-Review

- **Placeholder scan:** no TBD/TODO left in decided sections; every open question above is deliberately a flagged decision point, not an unfinished section.
- **Internal consistency:** slug design (4.3) and data model (5) agree (`slug` UNIQUE, `id` still the routing key). Outbox design (4.1) and data model (5) agree on `outbox_events` columns. Reset token design (4.2) and data model (5) agree on `reset_tokens` columns.
- **Scope:** single cohesive service (one FastAPI app, one Postgres DB, one worker process) — not decomposed into sub-projects; the three problems are small enough and share enough of the same codebase (routes, models, config) that splitting into separate specs would just fragment shared context.
- **Ambiguity check:** the one place this could still be read two ways is quirk #5 combined with the token security rewrite — "same generic error for expired and invalid" now also covers "used" tokens; made that explicit in 4.2 rather than leaving it implied.
