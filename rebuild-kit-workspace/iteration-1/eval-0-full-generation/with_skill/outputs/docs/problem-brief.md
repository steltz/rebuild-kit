# Problem Brief — ticketd

<!-- Captured 2026-08-08, harvested from the commissioning request (non-interactive run: the
     team was not available for follow-up; gaps are recorded under "Open intake questions",
     never invented). Human testimony is the third evidence class alongside code + traces.
     Every entry must end the pipeline dispositioned; P9 blocks assembly otherwise. -->

## Motivation

ticketd is the internal ticket tracker, a Flask 1.x-era app running since 2019
(`ticketd/app/server.py:1`). Leadership signed off on a full rewrite after the June SMTP
outage took ticket-closing down for 40 minutes, because the app sends notification email
synchronously inside the request (PB-001). Security has separately flagged the password-reset
token storage (PB-002), and support keeps hitting slug collisions (PB-003). The target stack
is decided: FastAPI + Postgres (PB-004). UI changes are explicitly out of scope (PB-005) —
the API surface the existing UI consumes must be preserved.

## Register

### PB-001 — Notification email is sent synchronously inside the request
- kind: defect
- severity: high
- reported_by: commissioning team (leadership-ratified — this outage triggered the rewrite)
- affected_area: tickets/close, notification
- detail: `POST /api/tickets/<id>/close` calls `send_mail()` in-request
  (`ticketd/app/server.py:73-76`); `send_mail` blocks on SMTP with a 30s timeout
  (`ticketd/app/notify.py:5-7`, module docstring: "~2s typical, 30s on provider trouble").
  The reset flow does the same (`ticketd/app/server.py:94`). During the June SMTP outage,
  closing tickets was down for ~40 minutes.
- reproduction: June incident (testimony). Mechanism directly visible at
  `ticketd/app/server.py:76` ("sends synchronously in-request; SMTP outages take
  ticket-closing down with them").
- disposition: REPAIR in WO-004 (close notification) and WO-005 (reset email) — target:
  email dispatch decoupled from the request path; request success must not depend on SMTP
  availability. Mechanism FREE within that outcome (see OQ-004 for the team's preference).
  Expected divergences ED-001, ED-003.

### PB-002 — Password-reset tokens are MD5 hashes in a bare table
- kind: defect
- severity: high
- reported_by: security team (flagged; relayed by commissioning team)
- affected_area: auth/reset
- detail: token = `md5(email + time.time())` (`ticketd/app/server.py:90`), stored cleartext
  in `reset_tokens` — a bare table with no PK, no expiry column, no index
  (`ticketd/db/schema.sql:18-22`). Predictable input space, cleartext at rest, expired rows
  never purged (deletion only on successful confirm, `ticketd/app/server.py:106`).
- reproduction: static — the table and the generation site above.
- disposition: REPAIR in WO-005/WO-006 — target: cryptographically random token, stored
  hashed at rest, single-use and 30-minute expiry preserved (those two outcomes are existing
  behavior: `ticketd/app/server.py:16,103-107`). Storage mechanism FREE within that outcome.
  Expected divergence ED-002.

### PB-003 — Slug collisions between similarly-named tickets
- kind: defect
- severity: medium
- reported_by: support team (recurring; relayed by commissioning team)
- affected_area: tickets/create, slug generation
- detail: `slugify()` lowercases, collapses non-alphanumerics to `-`, truncates to 64
  (`ticketd/app/util.py:4-6` — its own comment: "collisions possible: two tickets named
  'Fix DB' and 'fix db!' share a slug"). No uniqueness constraint on `tickets.slug`
  (`ticketd/db/schema.sql:4`). **Nobody has decided what the fix should be.**
- reproduction: create two tickets titled "Fix DB" and "fix db!" — identical slugs
  (frozen in replay trace `tickets-create-006`/`007`).
- disposition: REPAIR in WO-002 — problem is sanctioned but the target behavior is
  **pending ruling OQ-001** (options drafted in `guide/briefs/OQ-001-ruling-brief.md`).
  Until ruled, slug generation is implemented exactly as legacy and WO-002's gate flags it.

### PB-004 — Target stack: FastAPI + Postgres
- kind: goal
- severity: —
- reported_by: commissioning team ("the new stack is decided ... our team's expertise")
- affected_area: whole system
- detail: Python / FastAPI / PostgreSQL. Rationale: team expertise.
- disposition: recorded in `rebuild.json.target_stack` and `modern/CLAUDE.md`. Implies a
  SQLite → Postgres data migration workstream (WO-007, `docs/migration/`).

### PB-005 — No UI changes (non-goal)
- kind: non-goal
- severity: —
- reported_by: commissioning team ("Explicitly out of scope: any UI changes")
- affected_area: entire HTTP surface consumed by the UI (`svc-ui/2.1` per
  `ticketd/ops/access.log`)
- detail: the existing UI must keep working unchanged. Consequence: every observed API
  behavior the UI may depend on is FIXED unless a PB entry sanctions the change — including
  the 200-with-`{}` missing-ticket quirk (`ticketd/app/server.py:62-63`), the no-pagination
  full-listing contract (`ticketd/app/server.py:35`), and int-or-string priority coercion
  (`ticketd/app/server.py:47-49`).
- disposition: out-of-scope ruling recorded here; enforced as FIXED tags across the specs
  and by the L3 replay suite.

## NFR targets

- **NFR-1 (from PB-001):** Ticket operations (create/close/list/get) remain available and
  within latency envelope while SMTP is fully down. Acceptance: close-ticket replay passes
  with the harness mail sink stopped.
- **NFR-2 (from PB-004/PB-005):** No route regresses its observed latency envelope
  (`perf-envelopes.json`, 30-day window) — the UI is unchanged, so responsiveness must be too.
- **NFR-3 (from PB-002):** Reset tokens unusable if the token store leaks: random ≥128-bit,
  hashed at rest, single-use, ≤30-minute validity.

## Non-goals

- PB-005 — any UI change, including "nicer" API shapes, pagination, or error-body cleanups
  not sanctioned by a PB entry.
- New features (auth/login, assignees UI, priorities rework) — nothing in the commissioning
  request sanctions feature work; this is a replatform + the three sanctioned repairs.

## Open intake questions

The team was not available during generation. These are the questions we would have asked in
the intake interview; each is also filed in `docs/open-questions.md` where it affects a WO.

1. **Slug fix decision (PB-003)** — which behavior do you want? Options drafted in OQ-001.
2. **Email dispatch mechanism (PB-001)** — is there existing queue infrastructure (Redis,
   RabbitMQ, cron workers) we should target, or is a Postgres transactional outbox + worker
   acceptable? OQ-004.
3. **`X-Internal-Bypass` header** (`ticketd/app/server.py:84`) — undocumented rate-limit
   bypass; who uses it, keep or drop? OQ-002.
4. **`/internal/export/csv`** — comment says "no caller since" the 2020 audit
   (`ticketd/app/server.py:112`) and the 30-day log shows zero traffic; drop it? OQ-003.
5. **Production data access** — we had schema + access log only. Grant a read-only prod DB
   connection (or a scrubbed snapshot) so the migration census queries can run? PII-scrub
   approval for that data is also needed. (Recorded in `rebuild.json.evidence`.)
6. **Timezone policy** — legacy stores naive local-time strings
   (`ticketd/app/server.py:52` — "naive local time!"). What timezone does the server run in,
   and should Postgres store `timestamptz` UTC? OQ-005.
7. **What consumes `POST /api/auth/reset/confirm`'s `{ok, email}` response?** The `users`
   table has no password column (`ticketd/db/schema.sql:12-16`); where does the reset
   actually land? OQ-006.
8. **Invalid priority values** — a priority outside {1,2,3,low,med,high} currently violates
   the DB CHECK and returns a 500; preserve or validate? OQ-007.
9. **SLOs / scale expectations** for the new service beyond NFR-2, and who signs gates
   during execution.
