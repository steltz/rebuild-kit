# Problem Brief — ticketd
<!-- Captured 2026-08-08, non-interactively, from the owner's intake request and the
     contractor handover notes as relayed in that request. The owner was not reachable
     during generation; gaps are recorded as open intake questions, not invented.
     Human testimony: third evidence class alongside code + traces.
     Every entry must end the pipeline dispositioned; P9 blocks assembly otherwise. -->

## Motivation
ticketd is an internal ticket tracker inherited from a contractor. It arrived as a source
snapshot only: no git history, no access logs, no production database access (expected "in a
few weeks"). The owner wants the rewrite workspace generated now, code-only, with production
evidence layered in later via spec-patch. The rewrite targets FastAPI + Postgres (PB-003).
Known problems are limited to two items from the handover notes (PB-001, PB-002) — the owner
stated "that's genuinely all we know."

## Register

### PB-001 — Notification emails send synchronously inside requests and block them
- kind: defect
- severity: high (inferred from handover phrasing "block them"; unconfirmed — OQ-INT-1)
- reported_by: contractor handover notes (relayed by owner, 2026-08-08)
  affected_area: notifications — `ticketd/app/notify.py`, close-ticket and reset endpoints
- detail: `send_mail` opens a blocking SMTP connection inside the request thread
  (`ticketd/app/notify.py:5-7`, timeout 30s; its own docstring: "~2s typical, 30s on provider
  trouble"). Callers: ticket close (`ticketd/app/server.py:76`, in-code comment: "SMTP outages
  take ticket-closing down with them") and password-reset request (`ticketd/app/server.py:94`).
- reproduction: code-derived only (no logs available). Stall/point an SMTP server that delays
  accept; POST `/api/tickets/<id>/close`; the request blocks up to 30s.
- disposition: REPAIR in WO-005 (close-path) and WO-006 (reset-path); divergences ED-001, ED-002.

### PB-002 — Password-reset tokens are MD5
- kind: defect
- severity: high (security; unconfirmed exposure — OQ-INT-1)
- reported_by: contractor handover notes (relayed by owner, 2026-08-08)
  affected_area: auth/reset — `ticketd/app/server.py:90`
- detail: reset tokens are `md5(email + time.time())` — predictable input space, weak digest,
  stored in plaintext in `reset_tokens` (`ticketd/db/schema.sql:18-22`). Tokens are single-use
  (deleted on confirm, `ticketd/app/server.py:106`) and expire after 30 minutes
  (`ticketd/app/server.py:16,103`) — those two *outcomes* are load-bearing and kept.
- reproduction: code-derived: request a reset, read the token from the DB or email; observe
  it is a 32-hex MD5 of guessable inputs.
- disposition: REPAIR in WO-006; divergence ED-003. Token *mechanism* is FREE (CSPRNG,
  hashed at rest per modern/CLAUDE.md); single-use + 30-min expiry stay FIXED.

### PB-003 — Target stack: FastAPI + Postgres
- kind: goal
- severity: —
- reported_by: owner (intake request, 2026-08-08)   affected_area: whole system
- detail: rewrite lands on FastAPI + PostgreSQL. Implies a SQLite→Postgres data migration
  (planned in `docs/migration/`, blocked on DB access — OQ-INT-2).
- disposition: NFR target (recorded in rebuild.json `target_stack`; governs modern/CLAUDE.md).

### PB-004 — Evidence arrives late: workspace must be regenerable against production data
- kind: goal
- severity: —
- reported_by: owner (intake request, 2026-08-08)   affected_area: workspace process
- detail: owner explicitly wants to "layer the evidence in later" — logs and prod DB access
  are expected in a few weeks. The workspace must record exactly which claims are code-derived
  so the later spec-patch can upgrade or falsify them.
- disposition: NFR target — degraded-mode ledger in rebuild.json.evidence; confidence labels
  on every spec claim; OQ-INT-1..3 hold the re-entry points.

## NFR targets
- PB-003: FastAPI + Postgres stack; async request handling.
- PB-004: every code-derived claim labeled; spec-patch re-entry points enumerated in
  docs/open-questions.md (OQ-INT-*).
- No further NFRs were given (no SLOs, scale numbers, or operability targets) — see OQ-INT-3.
  Do not invent targets; PB-001's repair is verified behaviorally (dispatch decoupled from
  request), not against a latency number.

## Non-goals
None stated. The owner gave no explicit out-of-scope list — recorded as a gap (OQ-INT-3).
Generator note: nothing in this brief sanctions feature additions (auth hardening beyond
PB-002, pagination, UI changes). Absent a ruling, everything not covered by a PB entry is
fidelity-bound.

## Open intake questions
<!-- Mirrored as OQ-INT-* in docs/open-questions.md; each is a spec-patch re-entry point. -->
- OQ-INT-1: Confirm severities and real-world impact of PB-001/PB-002 (no logs or incident
  history available). Any known exploitation of the MD5 tokens? Any users table actually in
  use for auth? (Code never reads `users` for login; there is no login endpoint at all —
  reset flow exists without a visible password store. See OQ-002.)
- OQ-INT-2: Production database access — required for the data census, migration mapping
  validation, and dirty-data handling. Blocks milestone M3 (migration/cutover).
- OQ-INT-3: Missing testimony: NFR targets (scale, SLOs), non-goals, who consumes
  `/internal/export/csv` today (code comment says "no caller since 2020" —
  `ticketd/app/server.py:112`), and whether the undocumented `X-Internal-Bypass` rate-limit
  header (`ticketd/app/server.py:84`) is load-bearing for any internal tool.
