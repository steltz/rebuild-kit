# Problem Brief — ticketd

Captured 2026-08-09 from Nicholas Stelter (product/eng owner), in the request that commissioned
this rewrite. This is a non-interactive generator run — no follow-up interview was possible.
Human testimony is the third evidence class alongside code citations and the access-log traces
below; every entry here is dispositioned by the end of this pipeline (P8/P9), several of them by
the generator itself from code + log evidence rather than direct testimony — those say so.

## Motivation

Leadership signed off on a full rewrite after the June 2026 SMTP outage (see PB-001) took ticket
closing down for 40 minutes — a synchronous side effect on the request path turned a third-party
mail outage into a core-workflow outage. That incident is the forcing function; PB-002 (MD5 reset
tokens) and PB-003 (slug collisions) were already-known problems that piggyback on the rewrite.
Target stack is decided (FastAPI + Postgres — PB-005); UI is explicitly frozen (PB-006).

## Register

### PB-001 — Synchronous SMTP call blocks ticket-closing under provider outage
- kind: defect
- severity: high
- reported_by: Nicholas Stelter (product/eng owner)   affected_area: ticket close / notifications
- detail: `POST /api/tickets/<id>/close` calls `send_mail()` in-request
  (`ticketd/app/server.py:76`, `ticketd/app/notify.py:5-7`); `notify.py`'s own docstring records
  "~2s typical, 30s on provider trouble." The June 2026 outage held SMTP latency at the high end
  long enough that closing tickets was unavailable for ~40 minutes org-wide, since every close
  request blocked on the mail call before returning.
- reproduction: incident testimony (June 2026 SMTP outage, ~40 min impact to ticket-closing).
  Corroborating code evidence: `ticketd/app/server.py:67-77`, `ticketd/app/notify.py:1-7`.
  Corroborating P2 runtime evidence (`perf-envelopes.json`, healthy-SMTP conditions): `close`
  (p50 110ms / p95 287ms / p99 352ms) and `reset`/`reset/confirm` (p50 92-119ms / p95 212-301ms) —
  the three endpoints that call `send_mail()` synchronously — run 4-5x slower at p50 than the
  non-mail-sending `list`/`create`/`get` endpoints (p50 24-25ms) even under normal conditions,
  before any provider degradation. This is same-day sample data (see the P2 evidence-quality
  caveat in `zero-traffic.md`), so treat the exact multiplier as illustrative, not a precise SLO.
- disposition: REPAIR in WO-001 — decouple notification dispatch from the request/response cycle
  (async outbox/queue in the new stack); target behavior ratified by this brief, no further ruling
  needed. See ED-001 in `verification/replay/expected-divergences.yaml`.

### PB-002 — Password-reset tokens are MD5 hashes in a bare table
- kind: defect
- severity: high
- reported_by: Security (flagged; relayed by Nicholas Stelter)   affected_area: auth/reset
- detail: `request_reset()` mints `hashlib.md5(f"{email}{time.time()}".encode()).hexdigest()` and stores it
  in plaintext in an index-free `reset_tokens(email, token, created_ts)` table with no row ever
  purged except on successful confirm (`ticketd/app/server.py:90-95`, `ticketd/db/schema.sql:18-22`).
  MD5 is not a credential-appropriate hash/token construction, and unconsumed tokens (rate-limited
  or abandoned flows) accumulate forever.
- reproduction: source citation only — no incident tied to this beyond the security flag.
  `ticketd/app/server.py:80-108`, `ticketd/db/schema.sql:18-22`.
- disposition: REPAIR in WO-003 — replace with a cryptographically random token (secrets.token_urlsafe
  or equivalent, ≥128 bits), store only a hash of the token server-side, add expiry-based cleanup.
  Outcome-preserving requirements (30 min expiry, same error body for expired vs. invalid, 3/hour
  rate limit) stay FIXED — only the token *mechanism* is REPAIR. See ED-002.

### PB-003 — Slug collisions on similarly-named tickets
- kind: defect
- severity: medium
- reported_by: Support (relayed by Nicholas Stelter)   affected_area: ticket creation / slugify
- detail: `slugify()` lowercases, strips to `[a-z0-9]` runs joined by `-`, truncates to 64 chars,
  and is invoked with **no uniqueness check** at the call site (`ticketd/app/util.py:4-6`,
  `ticketd/app/server.py:50-55`). The source even carries a same-session comment flagging it:
  "collisions possible: two tickets named 'Fix DB' and 'fix db!' share a slug." Support has hit
  this in practice; **the fix has not been decided** — that is explicit testimony, not an inference.
- reproduction: `POST /api/tickets` twice with titles that normalize to the same slug (e.g. "Fix DB"
  and "fix db!") — both succeed, both get slug `fix-db`, nothing disambiguates them downstream.
- disposition: **FIXED for this rewrite** — WO-002 implements ticket creation faithfully,
  including the current collision-permitting behavior (no uniqueness check), matching legacy
  exactly. This is a scoping decision the generator can make without a human ruling: shipping
  legacy-faithful behavior needs no sanction, only CHANGING it would. Whether to actually improve
  collision handling remains open as **OQ-001** for a human to decide as a possible follow-up
  (separately scoped work, not blocking this rewrite's completion) — see
  `docs/open-questions.md#OQ-001` for the candidate approaches.

### PB-004 — Elevated 5xx rate in the access-log sample (root cause now traced, P7)
- kind: pain
- severity: medium
- reported_by: generator (P2 runtime-evidence analysis, not direct testimony); root cause
  traced by the generator in P7   affected_area: `GET /api/tickets`, `GET /api/tickets/<id>`,
  `POST /api/tickets`, and by extension any write endpoint (`close`, `reset`)
- detail: 51/2000 requests (2.55%) in the supplied access log return HTTP 500, concentrated on the
  three highest-traffic endpoints (`usage-weights.json`, generated from `ticketd/ops/access.log`).
  Originally root-cause-unconfirmed (Combined Log Format carries no stack trace). **P7 booted the
  legacy app locally (verification/harness/run-legacy.sh) and reproduced a concrete, citable root
  cause**: `db()` (`ticketd/app/server.py:20-24`) opens a fresh `sqlite3.connect()` per Flask
  request context but never closes or rolls it back — no `teardown_appcontext` exists anywhere in
  the file. When a handler raises before `commit()` (e.g. the `priority` CHECK-constraint
  violation captured in `tickets-create-invalid-priority-906`, or the `None.strip()`
  `AttributeError` on an explicit `{"title": null}` captured in `tickets-create-null-title-900` —
  see OQ-008, now resolved by this same trace run), that connection's implicit write transaction
  can outlive the request, and SQLite's single-writer lock stays held until Python finalizes the
  orphaned connection object — non-deterministically. A subsequent write request on the same
  server process can then fail with `sqlite3.OperationalError: database is locked` (uncaught,
  surfaces as another 500). **P9 audit correction (2026-08-09):** an earlier draft of this entry
  described "three consecutive database-is-locked 500s" as directly reproduced and cited as fact;
  a fresh-context audit correctly flagged that this specific detail was only ever observed
  transiently during the generation session's terminal output and was never captured to a
  committed artifact (no saved raw log, no traceback file) — the only artifact actually in this
  repo, trace `tickets-crud-lock-cascade-901`, shows a *successful* follow-up request, not a
  locked one, matching the timing-dependent nature this defect should have. The **mechanism**
  (leaked connection, no `teardown_appcontext`, non-deterministic lock) is independently,
  statically verifiable by reading `ticketd/app/server.py:20-24` directly — that part is solid.
  The specific "it locked three times in a row" claim is downgraded from "reproduced" to
  "plausible based on the mechanism, observed once transiently during generation but not
  preserved as evidence" — treat it as a strong hypothesis, not a proven fact, until someone
  captures it properly (rerun `verification/harness/run-legacy.sh`, fire the null-title request,
  then immediately fire a write request, and this time save the server log).
- reproduction: `verification/replay/traces/tickets-crud.jsonl` trace
  `tickets-crud-lock-cascade-901` (successful follow-up in that specific capture run) plus its
  `note` field documenting the earlier run's full `sqlite3.OperationalError` traceback rooted at
  `server.py:69` (`close_ticket`'s `UPDATE`) and `server.py:91` (`request_reset`'s `INSERT`).
  Statistical pattern: `usage-weights.json` (error-rate field).
- disposition: **NFR target, now with a concrete mechanism** — the new stack's connection handling
  (SQLAlchemy/asyncpg session-per-request with guaranteed cleanup via FastAPI dependency teardown,
  plus Postgres's proper multi-writer concurrency vs. SQLite's single-writer lock) structurally
  eliminates this exact failure mode; 5xx rate on these routes should regress to near-zero. Not
  filed as a REPAIR against a specific PB defect (no PB entry named "close DB connections" before
  this), since the *outcome* (low error rate) was already the NFR target — this just upgrades the
  target from a hoped-for improvement to a **structurally guaranteed one** given the target stack.
  Still logged as OQ-005 (should the
  rewrite instrument error tracking additionally to close this gap for good) — non-blocking.

### PB-005 — Target stack: FastAPI + Postgres
- kind: goal
- severity: n/a
- reported_by: Nicholas Stelter (product/eng owner)   affected_area: whole system
- detail: "The new stack is decided: FastAPI + Postgres, our team's expertise." Recorded verbatim
  as the human stack decision required by P0; propagated to `rebuild.json.target_stack` and
  `modern/CLAUDE.md`.
- reproduction: n/a (decision, not defect)
- disposition: out-of-scope for further debate — ratified. Rationale = team expertise, not a
  technical requirement derived from the legacy system's failure modes; recorded as-is.

### PB-006 — UI changes are explicitly out of scope
- kind: non-goal
- severity: n/a
- reported_by: Nicholas Stelter (product/eng owner)   affected_area: whole system (API surface)
- detail: "Explicitly out of scope: any UI changes." This makes every currently-observable HTTP
  contract quirk that the UI depends on a FIXED requirement for the new API, not a bug to clean up
  in this rewrite — most notably PB-007 (200-with-empty-object on missing ticket) and the
  int-or-string `priority` field (`ticketd/app/server.py:47-49`).
- reproduction: n/a (scope decision)
- disposition: out-of-scope — ratified; drives multiple FIXED dispositions below and in the WOs.

### PB-007 — `GET /api/tickets/<id>` returns 200 + `{}` for a missing ticket, not 404
- kind: grievance (technical debt, not user-facing pain)
- severity: low
- reported_by: generator (source citation, not direct testimony)   affected_area: ticket read API
- detail: `get_ticket()` returns `jsonify({}), 200` when no row matches, with an explicit code
  comment: "historical quirk: 200 with empty object, NOT 404 — the legacy UI depends on it"
  (`ticketd/app/server.py:58-64`). Ordinarily a rewrite would fix this; PB-006 (UI frozen) forecloses
  that option for this pass.
- reproduction: `GET /api/tickets/999999` against legacy → `200 {}`. No trace captured (T1 inactive);
  behavior confirmed by source citation and code comment only.
- disposition: FIXED in WO-002 — preserve exactly (contract citation: `ticketd/app/server.py:58-64`).
  Flagged in `docs/open-questions.md` OQ-004 as a candidate for a *future* rewrite once the UI is
  back in scope; not actionable now.

### PB-008 — Undocumented `X-Internal-Bypass` header defeats reset rate limiting
- kind: grievance (possible security-relevant dead/undocumented behavior)
- severity: medium
- reported_by: generator (source citation, not direct testimony)   affected_area: auth/reset
- detail: `request_reset()` skips the 3/hour rate-limit check entirely when the request carries
  header `X-Internal-Bypass: 1` (`ticketd/app/server.py:84`), with only a same-line code comment
  ("undocumented bypass header") as explanation. No caller of this header appears anywhere in the
  supplied evidence (access log has no header data to confirm either way — Combined Log Format
  does not capture arbitrary request headers). Intent is genuinely unclear: could be a legitimate
  internal-service escape hatch, or forgotten debug scaffolding.
- reproduction: source citation only, `ticketd/app/server.py:80-89`.
- disposition: **out-of-scope for this rewrite pass (deferred)** — unlike PB-003, this generator
  will NOT default to preserving this behavior, because blindly carrying forward an undocumented
  security-relevant bypass mechanism without confirming intent is a materially different risk than
  preserving a cosmetic slug-collision quirk. WO-004 implements the rate limit itself (FIXED) but
  explicitly does NOT implement the `X-Internal-Bypass` header path either way (neither preserving
  nor removing it) until a human rules **OQ-002** — see `docs/open-questions.md#OQ-002` and
  WO-004's own "DO NOT IMPLEMENT WITHOUT READING THIS" section. This is a real, closed scoping
  decision for this rewrite (the gap is documented and gated, not silently missing).

### PB-009 — Two modules with zero live callers
- kind: grievance (dead code)
- severity: low
- reported_by: generator (source citation + zero-traffic corroboration)
  affected_area: `internal/export/csv`, legacy_import
- detail: `export_csv()` (`ticketd/app/server.py:111-115`, comment: "written for the 2020 audit; no
  caller since") has zero hits in the supplied 2,000-row access-log sample. `legacy_import.py`
  (`ticketd/app/legacy_import.py`) carries the docstring "Nothing imports this module" and is not
  referenced from `server.py` or anywhere else in the tree.
- reproduction: `grep -c "export/csv" ticketd/ops/access.log` → 0; `grep -rn "import_spreadsheet\|legacy_import" ticketd/app/` → no callers outside the module itself.
- disposition: do-not-port (see `docs/do-not-port.md`) — evidenced by zero traffic + zero
  in-tree references + the code's own comments disclaiming callers. Flagged as OQ-003 (confirm
  before the M0/M1 cutover that no *external/manual* consumer of `/internal/export/csv` exists —
  the access log only covers the sampled window, see the P2 evidence caveat) rather than a hard
  block, since removing a zero-evidence endpoint is low-risk and reversible pre-cutover.

### PB-010 — `created_at`/`closed_at` are naive local timestamps
- kind: grievance (latent correctness issue, not reported as user pain)
- severity: low
- reported_by: generator (source citation only — original author flagged it in-line, not the
  requester)   affected_area: ticket timestamps
- detail: `datetime.now().isoformat()` is used with an in-line author comment "naive local time!"
  (`ticketd/app/server.py:52`, `:71`) — no timezone, so values are ambiguous across DST changes and
  any multi-region deployment. Nobody in this brief's intake reported this as a problem; it
  surfaces only from the code's own admission.
- reproduction: source citation only, `ticketd/app/server.py:40-77`.
- disposition: **FIXED for this rewrite** — same reasoning as PB-003: shipping legacy-faithful
  (naive-local-time-equivalent) behavior needs no sanction. WO-000/WO-002 implement timestamp
  columns as naive `TIMESTAMP` (not `TIMESTAMPTZ`) as the interim default. The generator's belief
  that this should eventually become a REPAIR to UTC-aware storage remains open as **OQ-006** (a
  PB proposal, per `docs/open-questions.md#OQ-006`) for a human to decide as possible follow-up
  work — not pre-sanctioned by any testimony, so not built now, and not blocking this rewrite.

### PB-011 — Additional unhandled-500 branches found by P9 adversarial audit (2026-08-09)
- kind: grievance (technical debt, same family as PB-004/OQ-008)
- severity: low
- reported_by: generator, P9 fresh-context audit agent (independently verified by the generator
  against source before recording here)   affected_area: ticket creation (`POST /api/tickets`),
  ticket listing (`GET /api/tickets?status=`)
- detail: the P9 audit found four gaps the earlier P4/P7 passes missed, none previously traced or
  documented:
  1. A non-object JSON body to `POST /api/tickets` (e.g. `[]`, `"hello"`, `42` — anything that
     survives `get_json(silent=True) or {}`'s truthiness check but isn't a dict) causes
     `body.get(...)` to raise `AttributeError` -> unhandled 500. Same family as OQ-008's
     `{"title": null}` case but a distinct trigger. (`ticketd/app/server.py:42-43`)
  2. Explicit `{"priority": null}` (key present, value JSON `null`) is NOT caught by
     `body.get("priority", "med")`'s default (which only applies when the key is *absent*) — it
     becomes the literal string `"None"` via `str(None)`, which is not in `("1","2","3")`, is
     passed through unchanged, and violates the DB CHECK constraint -> unhandled 500. Distinct
     from the already-traced `tickets-create-invalid-priority-906` case (arbitrary bad string) in
     trigger, though not in outcome. (`ticketd/app/server.py:47`)
  3. `GET /api/tickets?status=` (empty string, e.g. a bare trailing `?status` with no value) does
     NOT behave like "any other invalid value returns an empty array" (as WO-000 currently
     documents) — Python/Flask's `request.args.get("status")` returns `""`, and
     `if status:` treats empty string as falsy, so **no filter is applied at all** and the full
     unfiltered list returns instead. (`ticketd/app/server.py:29,32-34`)
  4. `POST /api/tickets/<id>/close` with a non-numeric `<id>` (e.g. `/api/tickets/abc/close`) is
     never documented or traced, unlike the identical case for `GET /api/tickets/<id>` (which IS
     traced, `tickets-get-non-numeric-id-009`). Same Flask `<int:tid>` converter almost certainly
     applies identically (framework-level 404), but this was never verified end-to-end for the
     close route specifically.
- reproduction: (1)-(3) independently verified by the generator via direct code reading after the
  audit flagged them (not yet captured as traces — see disposition). (4) not yet verified at all,
  flagged as a gap only.
- disposition: **FIXED for this rewrite** (items 1-3, same reasoning as PB-003/PB-010 — preserving
  already-evidenced-by-source behavior needs no sanction) — **added to WO-002's scope** as
  additional behaviors to implement faithfully and, ideally, capture as traces before that WO
  closes (not yet done as of this generation run — flagged in WO-002 and
  `docs/open-questions.md#OQ-011` rather than silently assumed complete). Item 4 is an
  **NFR-adjacent verification gap** (do the verification, no behavior change expected) — same
  disposition, same OQ.

## NFR targets

- **Notification delivery must not block the request/response cycle for any endpoint** (from
  PB-001) — target: p99 API latency for `close`/`reset` endpoints independent of SMTP provider
  health, and materially below the legacy same-day baseline (`perf-envelopes.json`: close p99
  352ms, reset p99 306ms, reset/confirm p99 305ms) once mail dispatch is decoupled from the
  response path; verified by WO-001's replay set forcing a slow/failing mail backend.
- **5xx rate on `GET /api/tickets`, `GET /api/tickets/<id>`, `POST /api/tickets` should trend
  toward 0%** against the legacy baseline of 2.55% (from PB-004), pending root-cause confirmation
  the generator could not establish from available evidence.
- **Reset-token storage must not persist recoverable secrets** (from PB-002) — hash-at-rest,
  single-use, time-boxed.

## Non-goals

- **No UI changes** (PB-006) — every HTTP contract behavior the current UI depends on (status
  codes, response shapes, the `priority` int-or-string acceptance, the empty-object-on-missing-id
  quirk) is FIXED, not up for cleanup, in this pass.
- **No strangler/incremental migration** — out of rebuild-kit's own scope per the skill's design;
  this is a clean-cutover rewrite (confirmed appropriate given the app's size: ~165 LOC across 4
  modules, 6 routes, 3 tables).
- Debating the FastAPI + Postgres stack choice (PB-005) is out of scope — ratified upstream of
  this workspace.

## Open intake questions

Because this run was non-interactive (autonomous background job, no human available to answer
clarifying questions mid-run), the following gaps could not be closed by follow-up and are
promoted to `docs/open-questions.md` rather than guessed:

- **OQ-001** (from PB-003): what should happen on a slug collision — reject with 409, append a
  disambiguating suffix, drop the human-readable slug as the identifying key, something else?
- **OQ-002** (from PB-008): is `X-Internal-Bypass` a sanctioned internal escape hatch to preserve
  (and if so, for whom/how in the new stack) or dead/forgotten scaffolding to drop?
- **OQ-003** (from PB-009): confirm no out-of-band consumer of `/internal/export/csv` exists before
  it is dropped at cutover (the 30-day access-log framing in the original ask does not match what
  was actually supplied — see the P2 evidence-quality note — so "zero traffic" here is weaker
  evidence than it would be against a genuine full month).
- **OQ-004** (from PB-007): once UI changes come back into scope in some future project, should
  `GET /api/tickets/<id>` start returning 404 for missing tickets? Not actionable now, recorded so
  it isn't lost.
- **OQ-005** (from PB-004): worth adding structured error tracking/APM to the new stack specifically
  to close the root-cause gap this brief couldn't fill? Non-blocking suggestion.
- **OQ-006** (from PB-010): should ticket timestamps become explicit UTC-aware values (a real
  behavior change, needs sanction) or should the rewrite preserve naive-local-time-equivalent
  semantics for fidelity's sake even though nobody asked for either?
- **Auth/session model**: nothing in the legacy app authenticates API callers beyond the reset-token
  flow itself — `ticketd/app/server.py` has no session/auth middleware at all, and the access log
  shows a single synthetic user (`jdoe@corp.example.com`) with no auth header captured. Whether the
  new FastAPI service should introduce real request authentication, or continue to trust its
  caller the way the legacy service implicitly does (presumably via network placement — "internal"
  ticket tracker), was not addressed in the intake and could not be inferred safely. Recorded as
  **OQ-007**, non-blocking for M0 (the rewrite can start unauthenticated, matching legacy, and this
  gets ruled before any milestone that exposes the service beyond its current network boundary).
