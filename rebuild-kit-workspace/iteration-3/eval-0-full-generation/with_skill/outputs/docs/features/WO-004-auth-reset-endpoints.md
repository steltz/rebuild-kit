id: WO-004            depends_on: [WO-000, WO-001, WO-003]   milestone: M2
risk: 0.5 (PB-001/PB-002/PB-008 all touch this WO; PB-008 specifically carries an unresolved ASK
  that gates part of this WO's own closure, which is itself a risk signal)
usage_weight: 0.0295 (request 1.95% + confirm 1.0%)   pain_weight: 0.6   context_budget: ~300 lines
gate: true

## Reading list

- `docs/features/draft/auth-reset.md` — full (primary source).
- `docs/domain/reset_token.md` — full.
- `docs/contracts/openapi.yaml` paths `/api/auth/reset`, `/api/auth/reset/confirm` + schemas.
- `verification/replay/traces/auth-reset.jsonl` — all 6 traces.
- `docs/open-questions.md#OQ-002` — read the current ruling field before implementing the bypass
  header behavior specifically.

## Behaviors

### POST /api/auth/reset (request)

- statement: accepts `{"email": <string>}`, missing key defaults to `""`, not validated as a real
    email address anywhere.
  fidelity: FIXED. evidence: [ticketd/app/server.py:82-83, trace: reset-request-001]
- statement: rate limit 3 requests/hour per exact `email` string match; exceeding returns
    `429 {"error": "rate_limited"}` and does NOT mint a token or send a notification.
  fidelity: FIXED. evidence: [ticketd/app/server.py:85-89, trace:
    reset-request-rate-limited-005 — traced, real 429 after 3 real requests]
- statement: token minting delegates to WO-003's mechanism (see that WO for the security REPAIR).
  fidelity: see WO-003.
- statement: notification dispatch delegates to WO-001's mechanism (async, not sync).
  fidelity: see WO-001 (ED-001b).
- statement: response is always `{"ok": true}` regardless of whether the email exists as a real
    user — no existence disclosure.
  fidelity: FIXED. evidence: [ticketd/app/server.py:83-95]

### The `X-Internal-Bypass` header — DO NOT IMPLEMENT WITHOUT READING THIS

- statement: in legacy, header `X-Internal-Bypass: 1` skips the rate-limit check entirely
    (`ticketd/app/server.py:84`), undocumented, intent unclear (PB-008).
  fidelity: **NO TAG — this is `docs/open-questions.md#OQ-002`, currently PENDING.**
    **Do not implement this behavior (either preserving it OR explicitly omitting/rejecting it)
    until OQ-002 is ruled.** Both preserving an undocumented security-bypass mechanism into a
    freshly-scrutinized rewrite AND silently dropping it are unsanctioned choices absent a
    ruling — the first ships a possible backdoor forward without confirming intent, the second is
    an uncited behavior REMOVAL, which is exactly the "drift" the skill's design principles
    forbid. **This WO's acceptance excludes the bypass-header trace
    (`reset-request-bypass-header-006`) until OQ-002 rules.** Everything else in this WO can and
    should be implemented and pass; this one code path stays a documented gap.
  evidence: [ticketd/app/server.py:84, trace: reset-request-bypass-header-006 — traced, confirms
    the mechanism works exactly as read]

### POST /api/auth/reset/confirm (confirm)

- statement: looks up by exact token match; not-found and expired return the IDENTICAL
    `403 {"error": "invalid_token"}`.
  fidelity: FIXED. evidence: [ticketd/app/server.py:100-105, traces:
    reset-confirm-already-consumed-003, reset-confirm-invalid-004]
- statement: success -> token consumed (single-use, delegates to WO-003), response
    `200 {"ok": true, "email": <associated email>}`.
  fidelity: FIXED. evidence: [ticketd/app/server.py:106-108, trace: reset-confirm-success-002]
- statement: no rate limiting on confirm itself (only on request).
  fidelity: FIXED (observed absence — do not add confirm-side rate limiting; that would be
    unsanctioned scope creep beyond what PB-002/OQ's cover). evidence: [ticketd/app/server.py:98-108]

## Acceptance

- L1: `docs/contracts/openapi.yaml` `/api/auth/reset`, `/api/auth/reset/confirm` validate against
  live responses (note the `X-Internal-Bypass` header parameter is documented in the spec as
  "observed contract," not as something this WO must implement — see above).
- L2: live-modern equivalents of `test_auth_reset.py`'s tests EXCEPT
  `test_bypass_header_defeats_rate_limit_pb008_undecided` (that one stays skipped/xfail with a
  comment pointing at OQ-002 until ruled).
- L3: `verification/harness/diff-run.sh auth-reset` — expect 5/6 traces to pass; the 6th
  (`reset-request-bypass-header-006`) is a known, documented gap, not a silent failure — the WO's
  closing note in the ledger should say so explicitly rather than the harness quietly reporting a
  mysterious failure.
- gate: **true** — PB-002 (security-flagged) + the unresolved OQ-002 bypass question both warrant
  human review before this closes, even though most of the WO is straightforward.

## Escalation

Consult `ticketd/app/server.py:80-108` only if the draft spec/traces leave something unclear. Do
not read the tickets handlers (`server.py:27-77`) — that's WO-002's scope.
