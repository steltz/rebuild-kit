# Problem Brief — ticketd

<!-- Captured 2026-08-09 from Nicholas Stelter (intake request) + contractor handover notes.
     No git history, no access logs, no production DB access at generation time (available in
     a few weeks). Human testimony is the third evidence class alongside code + traces —
     every entry below must end the pipeline dispositioned; P9 blocks assembly otherwise. -->

## Motivation

ticketd is an internal ticket tracker inherited from a contractor with no git history and no
access logs handed over. The team wants to replatform it onto FastAPI + PostgreSQL rather than
continue operating the inherited Flask/SQLite codebase, and does not want to wait for production
DB access (expected in a few weeks) to start. This generation run proceeds code-only /
degraded-evidence per the skill's degraded-mode rules (see `rebuild.json.evidence`); PB-003
below tracks re-running the evidence-dependent phases once access lands.

## Register

### PB-001 — Notification emails send synchronously in-request
- kind: defect
- severity: high
- reported_by: engineering team, via contractor handover notes
- affected_area: ticket lifecycle (close), auth (password reset)
- detail: `send_mail()` opens a blocking SMTP connection (30s timeout) inside the request/response
  cycle. Any SMTP slowness or outage stalls the HTTP request that triggered it — closing a ticket
  or requesting a password reset. There is no queue, retry, or async dispatch.
- reproduction: code inspection — `legacy/app/server.py:76` (`close_ticket`) and
  `legacy/app/server.py:94` (`request_reset`) both call `legacy/app/notify.py:6`
  (`send_mail`, `smtplib.SMTP(..., timeout=30)`) synchronously before returning a response.
  No captured trace of an actual outage exists (no APM/logs handed over) — the defect is
  evidenced by source, not by an observed incident.
- disposition: REPAIR in WO-002 and WO-004 — target: dispatch via an async outbox/background task
  (mechanism is FREE; see modern/CLAUDE.md), request threads no longer block on SMTP.

### PB-002 — Password-reset tokens are MD5
- kind: defect
- severity: high
- reported_by: engineering team, via contractor handover notes
- affected_area: auth (password reset)
- detail: reset tokens are `md5(email + wall-clock-time)` — MD5 is not a secret-token-appropriate
  construction (no cryptographic randomness guarantee across implementations, collision-class
  weaknesses, and time-based input narrows the search space). Tokens are also stored and compared
  in plaintext in `reset_tokens.token`.
- reproduction: code inspection — `legacy/app/server.py:90`
  (`hashlib.md5(f"{email}{time.time()}".encode()).hexdigest()`).
- disposition: REPAIR in WO-004 — target: cryptographically random token (e.g. `secrets.token_urlsafe`),
  stored hashed (not plaintext) if outcome (single-use, expiring, non-enumerable) is preserved;
  mechanism is FREE, outcome (30-minute window, same error body for invalid/expired) is FIXED
  per PB-002-adjacent behavior already in legacy — see WO-004.

### PB-003 — No runtime evidence or production data access at generation time
- kind: pain
- severity: medium
- reported_by: Nicholas Stelter (intake request)
- affected_area: whole system (evidence pipeline, P2/P6)
- detail: no access logs, APM, or analytics exist/were handed over, and there is no production
  database access yet (expected "in a few weeks"). This run proceeds without them per the skill's
  degraded-mode rules: usage/pain weighting falls back to a static proxy, no perf envelopes exist,
  and the data census ships as queries-to-run rather than results.
- reproduction: n/a (absence of evidence, not a behavioral defect)
- disposition: NFR target — re-run P2 (runtime evidence) and P6 (data census) as a spec-patch
  once DB/log access lands; this is tracked as an explicit follow-up in
  `docs/open-questions.md#OQ-003` and does not block M0/M1 (walking skeleton + core CRUD do not
  require it).

## NFR targets

None were stated in intake (no SLOs, scale targets, or operability requirements given). The only
implicit target is functional parity with the two REPAIRs above. If the human wants specific
latency/throughput/availability targets, that is an intake gap — see Open intake questions below.

## Non-goals

None were stated in intake. Not stated is not the same as out-of-scope by default — if new
features beyond parity + the two named REPAIRs come up mid-rewrite, they need an explicit human
ruling (open-questions.md), not silent inclusion. Per skill scope, this is a clean-cutover rewrite,
not a strangler/incremental-facade effort — the sibling `legacy/`/`modern/` structure assumes a
single cutover.

## Open intake questions

<!-- Non-interactive run — these could not be asked; harvested from what was given, gaps recorded
     rather than invented. See docs/open-questions.md for the formal OQ register; duplicated here
     per the problem-brief template so intake gaps are visible in one place. -->

- No authentication/authorization exists on ANY endpoint in the legacy app (not raised by the
  user as a known problem, discovered during code reading). Is this in scope as a defect (the app
  is reachable only on an internal network today, so maybe not a bug) or does the rewrite need to
  add auth? Filed as `OQ-001` (pb-proposal) — not built as a fix without a ruling.
- `X-Internal-Bypass: 1` skips the password-reset rate limit entirely (`legacy/app/server.py:84`).
  No documentation of who/what uses it. Filed as `OQ-002`.
- Confirm whether "a few weeks" for DB access also implies log/APM access, or whether that
  evidence source simply doesn't exist for this app. Filed as `OQ-003`.
- No target SLOs, expected scale (ticket volume, concurrent users), or team/operability
  constraints were given — assumed "small internal tool" scale throughout; flag if wrong.
- No non-goals were stated — assumed none beyond the two named defects; flag if there are
  features explicitly NOT wanted in the rewrite.
