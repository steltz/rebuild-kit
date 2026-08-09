# Open Questions — ASK register & PB proposals

Executor + generator both append here. Never delete entries; rulings are appended. Each OQ below
was raised during generation (P0 intake / P2 evidence review), since this was a non-interactive
run with no human available to answer follow-ups. None of these block scaffolding or the bulk of
the backlog; each entry states precisely what it does block.

## OQ-001 — What should happen on a ticket-title slug collision?
- raised_by: generator P0 (from PB-003, direct testimony: "nobody has decided yet what the fix
  should be")
- kind: ambiguity
- readings:
  - A: Reject the second create with `409 Conflict` and let the client retitle. Evidence: no
    current uniqueness constraint exists (`ticketd/db/schema.sql:1-10`, `ticketd/app/util.py:4-6`)
    so this is a new behavior, not a preserved one.
  - B: Auto-disambiguate by appending a suffix (`-2`, `-3`, …) or the ticket's own numeric `id` to
    colliding slugs. Preserves "every create succeeds" semantics but changes what a slug means
    (no longer purely derived from title).
  - C: Stop treating slug as a semantic/unique identifier at all — keep it as a display-only,
    non-unique field, and key everything (URLs, lookups) off `id` the way `GET /api/tickets/<id>`
    already does. Lowest implementation risk; sidesteps the collision question entirely.
  - D: Drop the fixed 64-char lowercase-alnum slug format itself and reconsider — no evidence
    either way, listed for completeness only.
- blocks: []  (does NOT block WO-002's close: preserving the CURRENT collision-permitting
  behavior — reading "do nothing differently" — requires no ruling at all, since it's just
  implementing what's already evidenced (`docs/features/draft/tickets-crud.md`, trace
  `tickets-create-slug-collision-002`). A ruling is only needed to CHANGE this behavior, which
  would be new, separately-scoped work opened once OQ-001 resolves — not a blocker on WO-002
  shipping the legacy-faithful baseline now.)
- ruling: PENDING

## OQ-002 — Is `X-Internal-Bypass` a sanctioned escape hatch or dead scaffolding?
- raised_by: generator P0/P4 (source citation, no testimony either way)
- kind: ambiguity
- readings:
  - A: Sanctioned internal mechanism (e.g. for an internal caller that legitimately needs to
    request resets on a user's behalf without hitting the rate limit) — evidence: it exists only
    on the rate-limit branch, not on token minting itself, suggesting deliberate scoping
    (`ticketd/app/server.py:84-89`).
  - B: Forgotten debug/test scaffolding — evidence: completely undocumented (README, comments give
    no rationale beyond "undocumented bypass header"), and the supplied access-log sample shows no
    distinguishable use of it (Combined Log Format doesn't capture custom headers, so this is
    inconclusive rather than confirming disuse).
- blocks: [WO-004]  (the reset-request endpoint's rate-limit behavior is FIXED and unblocked; only
  whether to carry the bypass mechanism forward into the new stack is gated)
- ruling: PENDING

## OQ-003 — Confirm no out-of-band consumer of `/internal/export/csv` before dropping it
- raised_by: generator P2 (zero-traffic finding, weakened by an evidence-quality caveat)
- kind: discrepancy
- readings:
  - A: Safe to do-not-port — zero hits in the supplied access-log sample, zero in-tree callers,
    and the code's own comment says "no caller since [2020]" (`ticketd/app/server.py:111-115`).
  - B: The supplied log is NOT the genuine ~30-day window the rewrite request described (see the
    P2 evidence-quality note in `usage-weights.json` / this brief's PB-004 entry) — it is a
    single synthetic day replayed with one user and randomized source IPs. A real batch/manual
    consumer that runs monthly or quarterly (plausible for a "2020 audit" export) would not show
    up in this sample even if it exists.
- blocks: []  (does not block any WO; do-not-port disposition stands provisionally in
  `docs/do-not-port.md`. Flags the M0→cutover gate for a human check, not implementation.)
- ruling: PENDING

## OQ-004 — Should `GET /api/tickets/<id>` start returning 404 for missing tickets?
- raised_by: generator P0 (from PB-007)
- kind: pb-proposal
- readings:
  - A: Keep FIXED (200 + `{}`) — required by PB-006 (UI changes out of scope) for this rewrite.
  - B: Fix to a standard 404 — the generator's opinion of the "right" behavior, but explicitly
    unsanctioned given the UI freeze; not actionable now.
- blocks: []  (WO-002 implements reading A; this is recorded so the idea isn't lost for a future
  project once/if UI changes come into scope)
- ruling: PENDING — expected disposition is "declined for this rewrite" per PB-006, but left open
  for an explicit human ruling rather than assumed.

## OQ-005 — Add structured error tracking/APM in the new stack to close the PB-004 root-cause gap?
- raised_by: generator P2 (from PB-004)
- kind: pb-proposal
- readings:
  - A: Yes — add request-scoped error logging/tracing so a future 5xx spike is diagnosable, unlike
    this rewrite's inability to root-cause the legacy 2.55% error rate from Combined Log Format
    alone.
  - B: No — out of scope; NFR target (error rate should drop) is enough, tooling choice deferred.
- blocks: []  (non-blocking suggestion, not gating any WO)
- ruling: PENDING

## OQ-006 — Should ticket timestamps move from naive-local to UTC-aware?
- raised_by: generator P4 (from PB-010; PB proposal — the generator flags this as probably wrong,
  but it is unsanctioned)
- kind: pb-proposal
- readings:
  - A: REPAIR to UTC-aware `timestamptz` columns — even the legacy author's own comment flags the
    naive-local-time choice as suspect (`ticketd/app/server.py:52,71`), and Postgres makes the
    correct choice nearly free.
  - B: Preserve naive-local-time-equivalent semantics for strict fidelity, since nobody reported
    this as a problem and PB-006 (no UI change) implies no client-visible contract should shift
    without cause.
- blocks: []  (WO-002/WO-004 implement reading B — i.e. FIXED — as the conservative default until
  ruled; switching to A later is a low-risk, additive migration)
- ruling: PENDING

## OQ-007 — Does the rewritten API need real caller authentication?
- raised_by: generator P0 (gap in intake — not addressed by the request)
- kind: ambiguity
- readings:
  - A: No — legacy has no auth/session middleware anywhere in `ticketd/app/server.py`; the access
    log shows exactly one caller identity (`svc-ui/2.1`, presumably trusted via network placement
    as an "internal" tool). Preserve that trust model; FastAPI service stays unauthenticated,
    fronted by the same network boundary as today.
  - B: Yes — a full rewrite is a natural point to add authentication, especially given PB-002's
    security-flagged reset-token handling shows this system already handles sensitive auth flows.
- blocks: []  (M0 proceeds unauthenticated, matching legacy — reading A — but any milestone that
  changes the service's network exposure should re-open this before shipping)
- ruling: PENDING

## OQ-008 — Does `POST /api/tickets` with an explicit `{"title": null}` really 500?
- raised_by: generator P4 (`docs/features/draft/tickets-crud.md`, inferred-only claim)
- kind: inferred-only
- readings:
  - A: Yes, unhandled `AttributeError` (`None.strip()`) → Flask default `500` — this is what a
    close source reading of `body.get("title", "").strip()` implies for an explicit JSON `null`
    (`.get()`'s default only applies when the key is absent, not when its value is `null`),
    at `ticketd/app/server.py:43`.
  - B: No — some earlier Flask/Werkzeug version behavior, a WSGI-layer error handler, or something
    else not visible in this file intercepts it differently. Not evidenced either way; the
    access-log sample has 12 `POST /api/tickets` 500s (`usage-weights.json`) but no request-body
    capture (T1 inactive) to attribute any of them to this specific cause versus the
    priority-CHECK-constraint-violation path noted in `docs/domain/tickets.md`.
- blocks: []  (WO-002 implements the evidenced empty/missing-title 422 path as FIXED; the
  null-title case defaults to "preserve whatever the legacy code actually does")
- ruling: **RESOLVED BY TRACE EVIDENCE, not a human ruling** — P7 booted legacy locally
  (`verification/harness/run-legacy.sh`) and captured the real response: reading A confirmed
  exactly (trace `tickets-create-null-title-900`, `verification/replay/traces/tickets-crud.jsonl`
  — HTTP 500, HTML error page, not the JSON 422 path). No human judgment call was needed once the
  ambiguity became directly observable; this OQ is left in the register (never delete) as a record
  of how it was resolved. WO-002 implements this as FIXED with `confidence: traced`.

## OQ-009 — What timezone did the legacy server run `datetime.now()` in?
- raised_by: generator P6 (`docs/migration/mapping.md`)
- kind: ambiguity
- readings: no readings evidenced at all — nothing in the supplied evidence (README, code,
  access log) states the deployment timezone. This is a pure gap, not a conflict between two
  citable readings.
- blocks: []  (does not block M0; blocks the `created_at`/`closed_at` migration transform
  specifically once real data exists to migrate — WO-005, the data-migration WO, should not
  proceed on this column pair without an answer)
- ruling: PENDING

## OQ-010 — Should any legacy `reset_tokens` rows be migrated, or start clean?
- raised_by: generator P6 (`docs/migration/mapping.md`)
- kind: pb-proposal (generator recommends a default, not a build)
- readings:
  - A (generator's recommended default): don't migrate — every row is either consumed, expired
    past a 30-minute window, or represents the exact weak-credential pattern PB-002 replaces; no
    forward value under the new mechanism.
  - B: migrate anyway for audit-trail purposes (e.g. "who requested a reset and when," stripped of
    the token value itself) — plausible if there's a compliance/audit reason not captured in this
    brief.
- blocks: [WO-005]  (data-migration WO should not silently drop this data without an explicit
  ruling, even though dropping it is the generator's recommendation)
- ruling: PENDING

## OQ-011 — Capture traces for the 4 gaps P9 audit found (PB-011) before WO-002 closes
- raised_by: generator P9 (fresh-context audit agent found these; generator independently
  verified 3 of 4 against source, see PB-011)
- kind: discrepancy (coverage gap, not a behavioral ambiguity — the expected behavior is already
  known/verified by source reading, this OQ is about closing the evidence gap, not resolving an
  unknown)
- readings: n/a — this isn't a disputed reading, it's a "go do the verification work" item. Listed
  in the OQ register per the skill's convention of routing all P9 coverage-gap findings through
  this register rather than silently patching specs.
- blocks: [WO-002, WO-003]  (WO-002 should not be marked `done` until traces exist for: non-object
  JSON body to create, explicit `priority: null`, empty-string `?status=` filter, and non-numeric
  id on close — see PB-011 for exact repro steps for the first three; the fourth needs to be run,
  not just reasoned about. WO-003 should not be marked `done` until a trace exists for a
  genuinely time-expired-but-still-present reset token — the corpus currently only covers the
  "already consumed" disjunct of the expired/invalid non-disclosure check, not the time-based one;
  see `verification/replay/traces/auth-reset.jsonl`'s `reset-confirm-invalid-004` note and
  WO-003's own evidence citation for this same gap.)
- ruling: PENDING (not a ruling in the ASK sense — this resolves automatically once the relevant
  WO's implementer runs the missing captures and updates `verification/replay/traces/*.jsonl`
  accordingly; recorded here so it isn't silently dropped)

## PB proposals summary

Two entries above (OQ-004, OQ-006) are PB proposals under the fidelity taxonomy's ASK rule: the
generator observed a legacy behavior it believes should change, but no PB entry or human ruling
sanctions the change, so it is filed here rather than built. Both currently resolve to "keep FIXED
as the conservative default" pending ruling — neither blocks any work order.
