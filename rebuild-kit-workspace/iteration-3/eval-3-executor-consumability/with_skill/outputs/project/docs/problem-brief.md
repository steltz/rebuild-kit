# Problem Brief — ticketd

<!-- Captured 2026-08-08, non-interactive intake. Source: task instructions from engineering
     leadership (no interview session possible — this run had no human available to answer
     follow-ups). Every testimony item below is quoted or closely paraphrased from that brief;
     nothing here was invented. Gaps the brief didn't cover are listed under "Open intake
     questions" rather than guessed. -->

## Motivation

Leadership signed off on a full rewrite after the June 2026 SMTP outage: **closing tickets was
down for 40 minutes** because the app sends the notification email synchronously inside the
request (PB-001). Two more issues were named as known-wrong without a decided fix (PB-002,
PB-003). The team's own stack (FastAPI + Postgres) was chosen for the rewrite (PB-004). UI
changes are explicitly out of scope (PB-005).

## Register

### PB-001 — Synchronous notification email blocks the request thread
- kind: defect
- severity: high
- reported_by: leadership (post-incident sign-off)          affected_area: notifications (ticket close + password reset)
- detail: `notify.send_mail` opens a blocking SMTP connection (`smtplib.SMTP(..., timeout=30)`)
  directly inside the request-handling thread. Two call sites: `close_ticket` and
  `request_reset`. Provider latency or an SMTP outage stalls the HTTP response for up to the
  30s socket timeout, and — per the June incident — a sustained outage takes the *entire
  feature* (ticket closing) down with it, not just the email.
- reproduction: June 2026 SMTP outage — ticket closing unavailable for 40 minutes. No trace
  capture exists for the incident itself (pre-dates this evidence base); treated as human
  testimony, not a replayable trace.
- evidence: `legacy/app/server.py:75-76` (close_ticket), `legacy/app/server.py:94`
  (request_reset), `legacy/app/notify.py:1,6` (docstring: "Blocks the request thread; ~2s
  typical, 30s on provider trouble.")
- disposition: REPAIR in WO-002, WO-004 (target: asynchronous/queued dispatch — decouple
  ticket-close and reset-request success from mail-transport availability)

### PB-002 — Password-reset tokens are MD5 hashes in a bare table
- kind: defect
- severity: high
- reported_by: security review          affected_area: auth/reset
- detail: `token = hashlib.md5(f"{email}{time.time()}".encode()).hexdigest()` — token is deterministic
  from two knowable-ish inputs (target email + wall-clock time) hashed with a broken,
  non-cryptographic digest; not a cryptographically random secret. Stored in `reset_tokens`,
  a table with no primary key, no index on `token` or `email`, and no DB-level expiry — the
  30-minute window is enforced only in application code (`RESET_WINDOW_MIN`, checked at
  confirm time), so an unexpired row is a plaintext-equivalent, directly usable credential for
  as long as it sits in the table.
- reproduction: static — `legacy/app/server.py:90` (token generation),
  `legacy/db/schema.sql:18-22` (bare `reset_tokens` table: `email TEXT, token TEXT,
  created_ts REAL` — no PK, no indexes, no FK).
- disposition: REPAIR in WO-003 (target: cryptographically random single-use token, stored
  hashed at rest, indexed and with an enforced expiry; single-use semantics — delete-on-confirm
  — and the deliberate same-error-body-for-invalid-and-expired non-disclosure behavior are
  both `FIXED` and must be preserved, see WO-003)

### PB-003 — Slug collisions on similarly-named tickets
- kind: defect
- severity: medium
- reported_by: support (recurring complaint)          affected_area: tickets (slug generation)
- detail: "support keeps hitting slug collisions where two similarly-named tickets end up with
  the same slug." Confirmed in code: `slugify()` lower-cases, strips non-`[a-z0-9]` runs to a
  single `-`, and truncates to 64 chars — "Fix DB" and "fix db!" both produce `fix-db`. The
  `tickets.slug` column carries no `UNIQUE` constraint at the DB level either, so collisions
  are silently stored, not even rejected.
- reproduction: `legacy/app/util.py:4-6` (the collision is called out in the function's own
  comment); `legacy/db/schema.sql:1-10` (no unique constraint on `slug`).
- **nobody has decided what the fix should be** — leadership named the problem, not the
  resolution. The outcome (slugs must be collision-free) is ratified by this brief; the
  *mechanism* (reject + re-title? numeric suffix? include the ticket id? content hash
  suffix?) and whether existing slug consumers (if any external system parses ticket slugs)
  need a stable format are open. See OQ-001.
- disposition: REPAIR in WO-005 (outcome: unique slugs, ratified here); mechanism: **ASK —
  OQ-001**, ruling required before WO-005 can close

### PB-004 — Target stack: FastAPI + Postgres
- kind: goal
- severity: n/a (decision, not a defect)
- reported_by: leadership          affected_area: whole system
- detail: "The new stack is decided: FastAPI + Postgres, our team's expertise." Recorded
  verbatim as the human stack decision this whole workspace depends on downstream (blocks
  `modern/CLAUDE.md` and Milestone 0 if left pending — it is not pending).
- disposition: NFR target / architecture decision — recorded in `rebuild.json.target_stack`
  and `modern/CLAUDE.md`; not a per-WO REPAIR, it is the substrate every WO builds on

### PB-005 — No UI changes
- kind: non-goal
- severity: n/a
- reported_by: leadership          affected_area: HTTP contract surface (API consumed by `svc-ui`)
- detail: "Explicitly out of scope: any UI changes." The existing frontend (seen only as
  `User-Agent: svc-ui/2.1` in the access log; its source is not part of this legacy tree) is
  assumed to keep working unmodified against the new backend. This is the strongest constraint
  on P5 contract fidelity: every response shape, status code, and field name the current UI
  might depend on (including the two documented historical quirks — 200-with-empty-object on
  a missing ticket, and int-or-string `priority` coercion) is `FIXED`, not open for cleanup,
  unless a PB entry says otherwise.
- disposition: out-of-scope (ruled by leadership at kickoff, 2026-08-08) — binding constraint
  on all HTTP-surface work orders (see `docs/contracts/openapi.yaml`, `integration-notes.md`)

## NFR targets

- **NFR-001** (from PB-001): ticket-close and password-reset-request requests must complete
  (2xx/4xx) without their latency or availability depending on mail-transport reachability.
  No numeric SLO was given by leadership; a reasonable floor pending human confirmation is "P99
  request latency for these two routes independent of SMTP round-trip time" — **flagged as an
  open intake question (OIQ-1)**, not invented as a hard number.
- **NFR-002** (from PB-002): reset tokens must be unguessable (drawn from a CSPRNG, not derived
  from email+timestamp) and unrecoverable from the stored value (hashed at rest). No specific
  bit-strength or hashing-algorithm mandate was given — FastAPI/Postgres-idiomatic choice is
  `FREE`, the outcome requirement is `FIXED`.
- **NFR-003** (from PB-003): `tickets.slug` must be unique at the database level (currently
  unenforced) regardless of which collision-resolution mechanism OQ-001 settles on.

## Non-goals

- **PB-005**: No UI changes — see above.
- Not stated but inferred as implied by "explicitly out of scope: any UI changes" and not
  contradicted anywhere in the brief: no *new* end-user-facing features. This rewrite is a
  same-behavior replatform, not a feature expansion, except where a PB entry explicitly calls
  for a behavior change (PB-001, PB-002, PB-003). Flagged for confirmation — see OIQ-2.

## Open intake questions

<!-- Gaps this non-interactive intake could not fill. No human was available during this run;
     these are surfaced here (and mirrored into docs/open-questions.md as OQ entries where they
     block specific work) rather than answered by assumption. -->

- **OIQ-1** — No numeric SLO/latency target was given for NFR-001. What ticket-close /
  reset-request P99 latency (or "independent of SMTP" is sufficient and no number is needed) is
  actually required? Affects whether WO-002/WO-004 need a synchronous queue-enqueue-then-return
  design vs. a stronger delivery guarantee (at-least-once outbox, retry/backoff policy, DLQ).
- **OIQ-2** — Is any new feature work implicitly in scope (e.g. the brief only lists fixes), or
  is this strictly a same-behavior replatform aside from PB-001/002/003? Assumed the latter;
  confirm before Milestone 1 features beyond parity are considered.
- **OIQ-3** — `ops/access.log` was described as "a ~30-day access log." The file that exists
  (`legacy/ops/access.log`, 2,000 lines) in fact spans a **single synthetic hour**: 60 distinct
  timestamps (`10:00:00`–`10:59:59`), one calendar date (`12/Jul/2026`), one user
  (`jdoe@corp.example.com`), cycling twice. This is flagged, not silently treated as 30 days of
  real traffic — see `docs/migration/../P2 notes` and `usage-weights.json.notes`. If a real
  30-day log exists elsewhere, re-running P2 against it would materially improve usage-weight
  and perf-envelope confidence, particularly for endpoints this log shows zero traffic for.
- **OIQ-4** — No authentication/authorization code exists anywhere in `legacy/app/server.py` —
  every route is open. The access log's user field (`jdoe@corp.example.com`, in the position
  Apache's `%u` remote-user field would occupy) suggests an authenticating reverse proxy sits
  in front of ticketd in production and injects identity, but nothing in the legacy tree
  confirms this. Does the FastAPI rewrite need to implement auth itself, or does it keep
  assuming an upstream proxy handles authn and (optionally) passes identity via a header? This
  materially changes WO scope and is currently unresolved — mirrored as OQ-002.
- **OIQ-5** — Expected data scale (ticket count, growth rate) for the Postgres migration and
  for sizing the `GET /api/tickets` no-pagination behavior (PB-005 freezes the *shape*, but
  scale affects whether that shape stays viable — an NFR question for leadership, not a
  behavior change for this rewrite).
- **OIQ-6** — `GET /internal/export/csv` shows zero requests in the (admittedly 1-hour) access
  log and the code comment says "written for the 2020 audit; no caller since." Is this route
  still needed by anyone outside logged traffic (e.g. an annual manual `curl`)? See
  `docs/do-not-port.md`.
