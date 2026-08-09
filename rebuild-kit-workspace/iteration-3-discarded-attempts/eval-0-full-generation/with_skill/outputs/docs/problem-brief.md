# Problem Brief — ticketd
<!-- Captured 2026-08-09 from the commissioning request (leadership-sponsored rewrite, relayed
     non-interactively — no follow-up interview was possible this run; gaps are logged under
     "Open intake questions" below rather than invented). Human testimony: third evidence class
     alongside code + traces. Every entry must end the pipeline dispositioned; P9 blocks assembly
     otherwise. -->

## Motivation

Leadership signed off on a full rewrite after the June 2026 SMTP outage: closing tickets was down
for 40 minutes because notification email is sent synchronously inside the request path (PB-001).
Two more issues are already flagged and in scope for repair — MD5 password-reset tokens (PB-002)
and slug collisions (PB-003) — plus the team is moving off the current stack onto FastAPI +
Postgres (PB-004), which is their standing expertise. UI is explicitly frozen (PB-005).

## Register

### PB-001 — Synchronous notification email takes down ticket-closing under SMTP latency
- kind: defect
- severity: high
- reported_by: leadership (relayed via rewrite commission)   affected_area: notifications / ticket-close, auth/reset
- detail: `close_ticket` and `request_reset` both call `send_mail()` in-request
  (`legacy/app/server.py:76`, `legacy/app/server.py:94`), which opens a blocking SMTP connection
  with a 30s timeout (`legacy/app/notify.py:6`). When the SMTP provider is slow or down, every
  caller of these two endpoints blocks for up to 30s per request, and closing tickets is
  unavailable in practice — this is the exact June outage.
- reproduction: incident — June 2026 SMTP outage, ticket-closing unavailable ~40 minutes. No
  captured trace of the incident itself was provided this run (see OQ-101).
- disposition: REPAIR in WO-002 (async dispatch via outbox/queue; the send becomes
  fire-and-forget from the request's perspective — see ED-001 in
  `verification/replay/expected-divergences.yaml`)

### PB-002 — Password-reset tokens are MD5 hashes in a bare table
- kind: defect
- severity: high
- reported_by: security (flagged in review)   affected_area: auth/reset
- detail: `request_reset` derives the token as `md5(email + time.time())`
  (`legacy/app/server.py:90`) and stores it in plaintext in `reset_tokens`
  (`legacy/db/schema.sql:18-22`) with no expiry column enforcement beyond an application-level
  30-minute window checked at confirm time (`legacy/app/server.py:103`). MD5 is not
  cryptographically appropriate for a security token, and the table has no indexes, TTL, or
  hashing-at-rest.
- reproduction: static — token generation and storage scheme, cited above.
- disposition: REPAIR in WO-002 (mechanism is FREE: outcome required is a single-use,
  time-limited, unguessable token, not stored in reversible/weakly-hashed form; see WO-002 for
  the chosen approach and rationale)

### PB-003 — Slug collisions on similarly-named tickets
- kind: defect
- severity: medium
- reported_by: support (recurring complaint)   affected_area: tickets
- detail: `slugify()` (`legacy/app/util.py:4-6`) lowercases, strips non-alphanumerics to hyphens,
  and truncates to 64 chars, with **no uniqueness check or collision suffix at all** — confirmed
  by the DDL, which declares `tickets.slug TEXT NOT NULL` with no `UNIQUE` constraint
  (`legacy/db/schema.sql:4`) and by `create_ticket`, which inserts whatever `slugify()` returns
  without checking for an existing row (`legacy/app/server.py:50-55`). "Fix DB" and "fix db!"
  collide today, and support has to work out by ticket ID which one a report is actually about.
- reproduction: static — no uniqueness enforcement anywhere in the write path or schema.
- disposition: REPAIR in WO-001 — **the brief does not prescribe a collision-resolution
  algorithm; nobody has decided one yet.** This is logged as OQ-001 (blocks: WO-001 finalizing
  its exact suffixing scheme; does not block M0, which can ship with any reasonable placeholder
  scheme pending the ruling). The only ratified requirement is the outcome: slugs must be unique
  per ticket going forward.

### PB-004 — Target stack: FastAPI + PostgreSQL
- kind: goal
- severity: n/a
- reported_by: leadership / team (stack decision, made at commissioning)   affected_area: whole system
- detail: the new stack is decided, not open for re-litigation by this workspace: Python +
  FastAPI + PostgreSQL, chosen because it's the team's existing expertise. No framework
  bake-off is in scope.
- disposition: NFR target — recorded in `rebuild.json.target_stack` and `modern/CLAUDE.md`

### PB-005 — No UI changes
- kind: non-goal
- severity: n/a
- reported_by: leadership (scope boundary at commissioning)   affected_area: whole system
- detail: this rewrite is API/backend/data only. Whatever currently consumes `/api/*` (an
  internal UI, per `legacy/app/server.py:35` "the UI relies on getting everything and filtering
  client-side" and `legacy/app/server.py:63` "the legacy UI depends on it") must keep working
  against an equivalent contract. No client-visible behavior may change outside what PB-001/
  PB-002/PB-003 sanction, and no new/removed/renamed response fields on existing endpoints.
- disposition: out-of-scope (ruled at commissioning) — enforced via `docs/contracts/openapi.yaml`
  being the frozen boundary; any endpoint response-shape change requires an OQ ruling first.

## NFR targets

- **Async notification dispatch** (PB-001): ticket-close and reset-request requests must not
  block on SMTP; a downstream SMTP outage must not take `/api/tickets/*/close` or
  `/api/auth/reset` unavailable. Target: p99 request latency for these two endpoints independent
  of mail-provider latency/availability.
- **Reset token security** (PB-002): tokens single-use, expiring (≤30 min, matching current
  window unless PB-002's REPAIR ruling changes it), not derivable from public inputs, not stored
  in a form usable to forge a reset if the table leaks.
- **Slug uniqueness** (PB-003): `tickets.slug` unique at the database level going forward; exact
  collision-resolution UX is OQ-001.
- **Stack** (PB-004): FastAPI + PostgreSQL, no re-litigation.
- **Contract stability** (PB-005): `/api/tickets*`, `/api/auth/reset*` response shapes frozen
  per `docs/contracts/openapi.yaml`, including documented quirks the UI depends on (e.g. 200 +
  `{}` for a missing ticket ID, not 404 — `legacy/app/server.py:61-63`).

## Non-goals

- UI changes of any kind (PB-005).
- Framework/database re-evaluation (PB-004) — FastAPI + Postgres is final.
- New features not tied to a PB entry — this is a rewrite, not a roadmap exercise.

## Open intake questions

This run was non-interactive (no human available to answer follow-ups); the following gaps are
recorded rather than guessed, and should be ruled before the WOs they block can close:

- **OQ-101** — No captured trace, APM export, or incident timeline for the June SMTP outage was
  provided, only the narrative in the commissioning request. `usage-weights.json` /
  `perf-envelopes.json` (P2) are therefore derived from `ops/access.log`, and that log turns out
  to cover roughly one hour of synthetic single-user traffic on 2026-07-12 (see the P2 evidence
  notes and OQ-102), not the "~30 days" it was described as — usage weighting should be treated
  as directional, not load-bearing, until a real production window is available.
- **OQ-102** — The task described `ops/access.log` as a "~30-day access log." The file that
  exists (`legacy/ops/access.log`, 2000 lines) spans exactly one calendar hour
  (2026-07-12T10:00:00Z–10:59:59Z), one client IP pool, one user (`jdoe@corp.example.com`), one
  user-agent (`svc-ui/2.1`). It reads as synthetic/generated fixture data, not a real production
  capture. Flagged so a human can confirm whether a real 30-day log exists elsewhere and should
  replace this one before usage-weight-driven backlog ordering is trusted for anything but M0.
- **OQ-001** — see PB-003: what collision-resolution scheme for ticket slugs (numeric suffix,
  longer hash suffix, id-based disambiguator, reject-and-require-manual-title, something else)
  and whether existing colliding slugs in production data get backfilled or left as-is
  (feeds `docs/migration/mapping.md`).
- **Auth/session model** — the legacy app has no visible authentication on `/api/tickets*`
  (only the reset-password flow touches identity) and no session/auth middleware appears in
  `legacy/app/server.py`. Is the FastAPI rewrite expected to add real request auth (e.g. because
  it's now internet-reachable, or moving off some perimeter-level control not visible in this
  code), or does it inherit the same "trusted internal network" posture? No testimony was given
  either way. Recorded as **OQ-103** (below); assumed out-of-scope/FREE-with-no-op pending a
  ruling, since inventing an auth model would be an unsanctioned feature.
- **Retention / compliance for reset tokens and closed tickets** — no testimony on data
  retention requirements for the Postgres migration. Recorded as **OQ-104**; P6 migration
  planning proceeds without a retention policy assumption.

(OQ-001, OQ-101–OQ-104 are filed in full in `docs/open-questions.md`.)
