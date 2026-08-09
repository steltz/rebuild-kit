# ticketd Rewrite — Design Spec

**Status:** Draft, authored without live user review (autonomous run — see "How this doc was produced" below). Must be read by a human before implementation starts.

**Date:** 2026-08-09

## How this doc was produced

This spec was written by an agent working solo, without the ability to ask
clarifying questions. Every place a real design conversation would normally
resolve a choice, this doc either (a) makes a defensible choice and says why,
or (b) flags it explicitly under **Open Questions** and picks a safe default
to unblock the plan. Before implementation starts, a human should skim
**Open Questions** at minimum — everything else in this doc is safe to build
against as-is.

## 1. Problem Statement

`ticketd` (Flask 1.x, SQLite, running since 2019) is being rewritten on
FastAPI + Postgres. Three known problems motivate the rewrite:

1. **Synchronous email in the request path.** `close_ticket` and
   `request_reset` both call `send_mail()` inline
   (`app/server.py:76`, `app/server.py:94`; `app/notify.py`). SMTP is
   ~2s typical, up to the full 30s socket timeout under provider trouble.
   The June SMTP outage took ticket-closing down for 40 minutes because the
   request thread blocked on a dead SMTP connection.
2. **Password-reset tokens are MD5 hashes in a bare table.** `token =
   hashlib.md5(f"{email}{time.time()}".encode()).hexdigest()`
   (`app/server.py:90`) is stored in cleartext in `reset_tokens.token`
   with no index, no expiry column (expiry is computed at read time from
   `created_ts`), and a fully guessable input space (email is often known,
   `time.time()` has limited entropy at the moment of request). Security
   flagged this.
3. **Slug collisions.** `slugify()` (`app/util.py:4-6`) lowercases,
   strips non-alphanumerics, and truncates to 64 chars, with no uniqueness
   check anywhere in `create_ticket`. "Fix DB" and "fix db!" collide by
   design. No fix has been chosen yet — this spec chooses one (§5).

**Explicitly out of scope:** any UI changes. The existing UI client
(`svc-ui/2.1`, confirmed from `ops/access.log`) is a fixed consumer of the
current API contract. The rewrite must be a drop-in backend replacement —
same routes, same request/response shapes, same status codes, same
documented quirks — unless a change is unobservable to the client.

## 2. Goals / Non-Goals

**Goals**
- Eliminate synchronous SMTP calls from the request path.
- Replace MD5 reset tokens with cryptographically strong, properly hashed,
  expiring tokens.
- Give tickets slugs that cannot collide.
- Move persistence from SQLite to Postgres.
- Preserve the existing API contract byte-for-byte where the UI depends on
  it (see §4 for the full inventory of quirks that must survive).
- Leave a workspace (this spec + the plan + the verification doc) complete
  enough that a future Claude Code session can execute the rewrite without
  further design decisions.

**Non-goals**
- No UI changes, no new UI-facing features, no new endpoints beyond what's
  needed to satisfy the three problems above.
- No general API redesign (pagination, filtering, auth model) — those are
  real improvements but are out of scope; noted as follow-ups in §8.
- No multi-region / HA design. Nothing in the current system or the access
  log suggests that scale. If that's wrong, see Open Questions.

## 3. Traffic Profile — and a Caveat About the Access Log

`ticketd/ops/access.log` was provided as "~30 days" of access log, but the
file on disk is **2,000 lines covering a single 33-minute window on
2026-07-12, from a single user (`jdoe@corp.example.com`), a single client
(`svc-ui/2.1`), across 253 distinct source IPs**. It is not actually a
30-day log — either the wrong file was linked, or it's a synthetic sample.
Treat every number below as a *shape* signal (which endpoints matter, what
quirks are exercised), not a *scale* signal (real QPS, peak concurrency,
real user/IP diversity, error-rate baseline). This mismatch is called out
again in Open Questions — get the real log before sizing anything (worker
pool size, DB connection pool, rate limit tuning).

What the sample does tell us, reliably, about **shape**:

| Endpoint | Count | % |
|---|---|---|
| `GET /api/tickets` | 1235 | 61.8% |
| `POST /api/tickets` | 423 | 21.2% |
| `GET /api/tickets/<id>` | 184 | 9.2% |
| `POST /api/tickets/<id>/close` | 99 | 5.0% |
| `POST /api/auth/reset` | 39 | 2.0% |
| `POST /api/auth/reset/confirm` | 20 | 1.0% |

- `GET /api/tickets` is never called with a `status` filter in the sample
  data (all query strings empty) — the filter code path exists but isn't
  exercised here. Preserve it anyway; it's cheap and documented in the
  route.
- `/internal/export/csv` never appears in the sample. Combined with the
  code comment ("written for the 2020 audit; no caller since"), this is
  weak-but-consistent evidence it's dead. See §4 for the decision (port it,
  don't delete it) and Open Questions for why.
- One `429` (rate-limited reset request) and 51 `500`s appear scattered
  across list/get/create/close with no discernible pattern (different IPs,
  no shared payload signature) — consistent with either synthetic noise in
  this sample file or a pre-existing intermittent bug in the Flask app.
  Nothing in `app/server.py` obviously 500s under normal input, so this
  spec does not chase it further; flagged in Open Questions in case it's a
  known issue.
- Ticket IDs `144`, `336`, `33`, `28`, `270`, `243`, `189` each get more than
  one `POST .../close` call in the sample. That's expected and already
  handled — `close_ticket` only flips status and sends mail `WHERE status
  != 'closed'` (`app/server.py:69-71`), so repeat closes are a no-op past
  the first. The rewrite must keep this idempotency.

## 4. API Compatibility Contract

Every route below must be preserved with these exact semantics. This is
the acceptance bar for "no UI changes" — the UI cannot tell the backend was
rewritten.

### `GET /api/tickets`
- Optional `?status=` query param, exact match against `status`.
- Returns a **plain JSON array** (not paginated, not wrapped in an
  envelope) of all matching tickets, `ORDER BY created_at DESC`.
- No pagination. Confirmed load-bearing by the code comment: "the UI
  relies on getting everything and filtering client-side." Do not add
  pagination in this rewrite even though it would be a real improvement —
  that's a UI-coordinated change and explicitly out of scope. Noted as a
  follow-up in §8.

### `POST /api/tickets`
- Body: `{title, priority?}`.
- `title` required, trimmed; empty/missing → `422 {"error": "title_required"}`.
- `priority` accepts **either** the strings `"low"|"med"|"high"` **or**
  the strings `"1"|"2"|"3"` (mapped `1→low, 2→med, 3→high`); anything else
  passes through as-is today (no validation) — preserve that permissiveness
  unless Open Questions resolves otherwise. Default `"med"`.
- Success: `201 {"id": <int>, "slug": <str>}`.
- Slug generation changes per §5, but the response shape does not.

### `GET /api/tickets/<id>`
- **Missing ticket returns `200 {}`, not 404.** This is called out in the
  original code as a deliberate legacy-UI dependency
  (`app/server.py:62-63`). Preserve exactly — a 404 here will break the
  existing UI's rendering path (it apparently treats `{}` as an "empty
  ticket" state rather than handling an HTTP error).
- Found ticket: `200 <ticket object>`.

### `POST /api/tickets/<id>/close`
- Idempotent: only flips `open → closed` and sets `closed_at`; already-closed
  tickets are a no-op.
- Returns `{"closed": <bool>}` — `true` if this call did the closing,
  `false` if it was already closed.
- Triggers a "ticket closed" notification to `watchers@example.internal`.
  This is the one behavior that **must** change in mechanism (async, not
  synchronous) while keeping the same eventual side effect (an email gets
  sent) — see §6.

### `POST /api/auth/reset`
- Body: `{email}`.
- Rate limit: 3 requests/hour per email, tracked by counting
  `reset_tokens` rows created in the last hour for that email.
  Exceeding it → `429 {"error": "rate_limited"}`.
- `X-Internal-Bypass: 1` header skips the rate limit check entirely.
  This is undocumented in code and in this codebase's history — see Open
  Questions. **Decision for this rewrite: preserve it as-is** (same header
  name, same value, same effect). Removing or changing an internal
  mechanism we don't have visibility into is a security-relevant change
  that needs a human decision, not something to silently alter mid-rewrite.
- On success: creates a reset token (format changes per §7), emails it
  (async per §6), returns `200 {"ok": true}`.

### `POST /api/auth/reset/confirm`
- Body: `{token}`.
- Invalid token **and** expired token return the **identical** response:
  `403 {"error": "invalid_token"}`. This is a deliberate anti-enumeration
  measure (`app/server.py:104`) — preserve it exactly; do not add detail
  that would let a caller distinguish "wrong token" from "right token, too
  late."
- Valid, unexpired token: deletes it (single-use), returns
  `200 {"ok": true, "email": <str>}`.
- Expiry window: 30 minutes (`RESET_WINDOW_MIN`), unchanged.

### Timestamp serialization (`created_at`, `closed_at`)

The legacy backend stores and emits naive-local timestamps via
`datetime.now().isoformat()` (`app/server.py:52`) — e.g.
`"2026-07-12T10:00:00.123456"`, no timezone offset, implicitly the
server's local time. Postgres `timestamptz` + a JSON serializer will
naturally want to emit an offset, e.g.
`"2026-07-12T10:00:00.123456+00:00"`. That's a real shape difference in
every ticket response.

**Decision: emit UTC with an explicit `Z`/`+00:00` offset going forward**
(store as `timestamptz`, always UTC). This is a correctness improvement
(today's naive timestamps are already an admitted bug — see the `# naive
local time!` comment) and standard `Date` parsing (JS `new Date(...)`,
Python `datetime.fromisoformat`) handles an offset-bearing ISO string
correctly, which is very likely how any consumer already parses it. If the
UI does something more fragile (e.g. string-slicing the timestamp instead
of parsing it), this would break — nothing in the codebase suggests that,
but there's no UI source available to confirm it either. Flagged in Open
Questions.

### `GET /internal/export/csv`
- No evidence of any current caller (code comment + absent from the access
  log sample, though that sample only covers 33 minutes — see §3 caveat).
- **Decision: port it as-is**, unchanged output format
  (`id,title,status` CSV, no escaping — matches current behavior, don't
  improve it silently since that could be a breaking change for whatever
  unknown consumer might exist). Mark it `deprecated` in an internal
  comment. Do not delete it in this rewrite — deleting a route we can't
  prove is dead is a bigger risk than carrying it forward unchanged. Revisit
  deletion once a real access log confirms zero calls over a full 30-day
  window (see Open Questions).

## 5. Slug Collisions — Decision

**Chosen approach: DB-enforced uniqueness with a numeric-suffix retry loop
on collision.**

- Add a `UNIQUE` constraint on `tickets.slug` at the Postgres level (the
  real fix — SQLite schema never had one).
- On create: compute `base = slugify(title)`. Attempt insert with
  `slug = base`. On a unique-violation, retry with `base-2`, `base-3`, …
  incrementing until the insert succeeds (bounded at 50 attempts, which is
  generous — collisions this deep would indicate a data problem, not normal
  use; if ever hit, append a short random suffix instead and log a
  warning).
- This keeps slugs clean/readable in the overwhelming common case (no
  collision → `base` unchanged, matching today's output byte-for-byte) and
  only decorates on an actual collision, which is what "support keeps
  hitting slug collisions" is asking to have fixed — the *symptom* being
  fixed is two tickets ending up with the *same* slug, not that slugs look
  ugly.
- Rejected alternative: always suffix with the ticket's own `id` (e.g.
  `fix-db-243`). This is simpler to implement (no retry loop, trivially
  race-free) but changes the slug format for *every* ticket, including the
  99%+ that never collide — a bigger observable change for API consumers
  that read `slug`, for a problem that only needs solving in the collision
  case. Rejected on YAGNI grounds.
- Rejected alternative: random suffix (e.g. `fix-db-a1b2`) always or on
  every collision. Rejected because sequential numeric suffixes are more
  predictable/debuggable for support staff triaging slug collisions, which
  is the exact audience that reported this problem.
- Concurrency: two simultaneous creates with the same title could both
  attempt `base` and race. The retry loop handles this correctly because
  the DB unique constraint is the source of truth — a losing insert gets a
  constraint violation and retries with the next suffix, it doesn't
  pre-check-then-insert (which would have a TOCTOU race). Implement with a
  real retry-on-IntegrityError loop, not a `SELECT COUNT` pre-check.

## 6. Async Notifications — Transactional Outbox

**Chosen approach: transactional outbox table in Postgres + a separate
worker process, no new infra (no Redis/Celery/etc.).**

- Add a `notifications` table: `id, to_addr, body, created_at, sent_at
  (nullable), attempts, last_error (nullable)`.
- `close_ticket` and `request_reset` write a row into `notifications` in
  the **same transaction** as the ticket-status update / token insert, then
  commit and return the HTTP response immediately. No network call to SMTP
  happens in the request path at all.
- A separate worker (`app/worker.py`, run as `python -m app.worker`, a
  long-lived asyncio loop) polls `notifications WHERE sent_at IS NULL`,
  sends via SMTP, and marks `sent_at` on success or increments `attempts` /
  records `last_error` on failure, with exponential backoff between
  retries (e.g. 30s, 2m, 10m, capped, giving up after N attempts and
  leaving the row for manual/alerted follow-up rather than silently
  dropping it).
- Why outbox-over-Postgres instead of Celery+Redis or FastAPI
  `BackgroundTasks`: the team is already committed to Postgres, this adds
  zero new infrastructure, and — critically — it's the only option of the
  three that survives a process restart. `BackgroundTasks` runs in-process
  and loses queued work on crash/restart, which is a real risk for a
  service coming off an incident where the failure mode was exactly "email
  delivery had a bad day." An outbox with a durable row is worse-case
  bounded: if the worker is down, notifications back up in the table and
  drain once it's back, instead of vanishing.
- This directly fixes the root cause: SMTP being slow or down can no longer
  block ticket-closing, because ticket-closing never touches SMTP.

## 7. Password Reset Tokens — Redesign

- Generate the token with `secrets.token_urlsafe(32)` (256 bits of
  entropy) instead of `md5(email + time.time())`. The old scheme's input
  space is small and partially guessable (email is often known to an
  attacker targeting a specific user; `time.time()` at request time can be
  narrowed via timing).
- **Store only a hash of the token**, not the token itself — `sha256(token)`
  in a `token_hash` column. If the `reset_tokens` table ever leaks (backup
  exposure, read replica misconfig, etc.), the hashes are not directly
  usable as reset tokens.
- Add an actual `expires_at` column (`created_ts + 30 minutes`, computed
  at insert time) instead of computing expiry at read time from
  `created_ts` — same effective behavior, but makes the expiry an explicit,
  indexable fact rather than logic buried in the confirm handler.
- Add a `UNIQUE` index on `token_hash` and an index on `(email,
  created_ts)` to keep the rate-limit count query (currently a full scan of
  matching rows) fast as the table grows — SQLite never needed this at
  ticketd's current scale, Postgres should have it from day one since we
  don't know the real request volume (§3 caveat).
- Keep single-use-by-delete (`DELETE ... WHERE token = ?` on confirm) —
  no change to that behavior.
- Keep the invalid/expired-return-identical-body behavior (§4) — this is
  an application-layer property, unaffected by the storage change.

## 8. Explicitly Deferred (Not This Rewrite)

Real improvements that surfaced during this review but are out of scope
because they'd require UI coordination or aren't part of the three stated
problems. Listed so they don't get silently lost, and so nobody re-derives
them from scratch later:

- Pagination on `GET /api/tickets` (currently unbounded, full-table,
  client-filters).
- Replacing `GET /api/tickets/<id>` returning `200 {}` for a missing
  ticket with a real `404` — requires a coordinated UI change.
- A documented, non-magic-header mechanism for whatever
  `X-Internal-Bypass` is protecting.
- Deciding whether `/internal/export/csv` can be deleted (needs a real
  access log over a full window, not the 33-minute sample here).
- Structured `priority` validation (today accepts arbitrary strings past
  the known set with no rejection).

## 9. Data Migration (SQLite → Postgres)

- One-time migration script, run during a maintenance window (see Open
  Questions for why a maintenance window is the assumed cutover strategy).
- `tickets` and `users`: copy rows as-is; types map cleanly
  (`TEXT`→`text`, `INTEGER`→`integer`/`bigint`, `DATETIME` stored as ISO
  strings today → parse and store as `timestamptz`; the existing
  `datetime.now().isoformat()` calls are naive-local-time, callout in
  `app/server.py:52` — treat as the server's local timezone at migration
  time and normalize to UTC explicitly, don't assume UTC silently).
- `tickets.slug`: re-slugify nothing — copy existing slugs as-is, then
  apply the new `UNIQUE` constraint. If any existing collisions are found
  at migration time (this is the whole reason for the rewrite item, so
  expect some), resolve them with the same numeric-suffix scheme as §5,
  applied once, in `id` order, so the result is deterministic and
  reproducible if the migration needs to be re-run against a fresh copy of
  the source data.
- `reset_tokens`: **do not migrate.** Tokens are 30-minute-lived; by the
  time a maintenance-window migration runs, any pre-existing token is
  already expired or about to be. Start the new `reset_tokens` table empty.
  This also sidesteps migrating MD5 tokens into the new hashed-token
  schema, which would otherwise require either keeping a legacy verification
  path or accepting a class of tokens that were never actually
  `sha256(secrets.token_urlsafe(32))`-shaped.
- `notifications` table: new, starts empty, no migration needed.
- Verification of the migration is covered in the verification doc
  (`docs/superpowers/verification/2026-08-09-ticketd-rewrite-verification.md`).

## 10. Open Questions

These are the things a normal design conversation would have resolved with
the team. Nobody was available to answer during this run, so each got a
documented default so the plan isn't blocked — but a human should confirm
or override these before/while executing.

1. **The access log isn't actually 30 days.** `ops/access.log` is a
   33-minute, single-user, single-IP-diversity-but-one-client sample. If
   real 30-day logs exist somewhere else, get them before finalizing
   connection pool sizes, worker concurrency, or rate-limit tuning — this
   spec's traffic assumptions (§3) are shape-only. *Default taken: sized
   everything conservatively for a low-traffic internal tool (single
   Postgres instance, single worker process, no autoscaling).*
2. **What is `X-Internal-Bypass` for, and who sends it?** It's undocumented
   in the codebase and skips reset rate-limiting entirely — worth a
   security look independent of this rewrite. *Default taken: preserved
   as-is, unchanged, no scope creep into redesigning it.*
3. **Can `/internal/export/csv` be deleted?** Code comment says no caller
   since 2020; the access log sample doesn't confirm or deny it (too short
   a window). *Default taken: ported unchanged, marked deprecated, not
   deleted.*
4. **Cutover strategy: is a maintenance window acceptable?** This spec
   assumes yes, based on the app's apparent scale (single SQLite file,
   simple schema, internal tool) — a blue-green or dual-write migration
   would be considerably more engineering for a tool this size. *Default
   taken: single maintenance-window cutover, see §9. If ticketd cannot
   tolerate any downtime, this needs to be revisited before implementation
   — dual-write is a materially different plan.*
5. **The scattered `500`s and one `429` in the access sample** — is the
   `500` rate a known pre-existing bug in the Flask app, or an artifact of
   this being sample/synthetic data? Nothing in `app/server.py` obviously
   produces a 500 under normal conditions. *Default taken: not
   investigated further as part of this rewrite; the rewrite's own test
   suite (see verification doc) will catch it if it's real and
   reproducible.*
6. **Deployment target.** Nothing in the repo indicates how this is
   currently deployed (systemd unit? container? PaaS?) or how the rewrite
   should be. *Default taken: this spec and the plan stay
   deployment-agnostic (a FastAPI app + a worker process + Postgres), and
   packaging (Dockerfile, systemd unit, whatever) is called out as a
   plan task using whatever convention the team already uses elsewhere —
   the plan cannot invent that convention blind.*
7. **Does anything consume `created_at`/`closed_at` in a way that would break
   if the timestamp gains a timezone offset?** (§4 Timestamp serialization).
   *Default taken: switch to explicit UTC-with-offset, since the current
   naive-local behavior is an admitted bug, not a feature.*
8. **SQLAlchemy async + asyncpg vs. psycopg3, and Alembic for migrations**
   — chosen in the plan as the standard, well-supported combination for
   FastAPI + Postgres. No signal in the existing codebase pointed to an
   existing team convention to match instead; if the team has one, swap it
   in.

## 11. Testing & Verification Summary

Full detail lives in
`docs/superpowers/verification/2026-08-09-ticketd-rewrite-verification.md`.
Summary:

- Unit/integration tests (pytest) for every route in §4, explicitly
  asserting each documented quirk (the `200 {}` on missing ticket, the
  identical invalid/expired body, the idempotent close, the
  `X-Internal-Bypass` behavior, the int-or-string `priority`).
- A slug-collision test that creates two tickets with colliding titles and
  asserts distinct slugs, plus a concurrency test (parallel creates, same
  title) asserting no unique-constraint crash reaches the client.
  Concurrency test also asserts an upper bound on request latency (< 200ms
  including the sync DB commit) — the point of §6 is that no request should
  ever wait on SMTP again.
- An outbox drain test: stop the worker, hit `close`/`reset`, assert the
  HTTP response returns immediately and a `notifications` row exists
  unsent; start the worker, assert it drains and marks `sent_at`.
- A "SMTP is down" regression test: point the worker's SMTP client at a
  closed port, assert `close_ticket`/`request_reset` still return fast
  (this is the direct regression test for the June incident).
- A replay of `ops/access.log` against the new API (script provided in
  `ops/verify/`) as a smoke test — not a load test (see Open Question 1),
  just a shape-compatibility check that every logged request pattern gets
  handled without error by the new backend.
- Migration verification: row counts match pre/post per table, spot-check
  a sample of tickets for field-for-field equality, and an explicit check
  that zero duplicate slugs exist post-migration.
