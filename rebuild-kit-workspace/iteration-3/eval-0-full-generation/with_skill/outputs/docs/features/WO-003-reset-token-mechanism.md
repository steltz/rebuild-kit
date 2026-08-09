id: WO-003            depends_on: [WO-000]              milestone: M2
risk: 0.65 (PB-002 severity high + security-flagged, FREE mechanism choice with real consequences
  if chosen poorly, zero legacy test coverage, security-sensitive code deserves a higher bar than
  its raw complexity score alone would suggest)
usage_weight: 0.0195 (reset-request's share; this WO is the mechanism WO-004 calls into)
pain_weight: 0.9 (security-flagged, PB-002)   context_budget: ~300 lines   gate: true

## Reading list

- `docs/problem-brief.md` — PB-002 in full.
- `docs/domain/reset_token.md` — full (this WO's primary source; every invariant listed there
  must survive the mechanism swap).
- `docs/migration/mapping.md` — table: reset_tokens (note: legacy rows are NOT migrated by
  default, `docs/open-questions.md#OQ-010` — this WO designs the NEW table shape, it does not
  need to accommodate importing old MD5 rows).
- `verification/replay/expected-divergences.yaml` — ED-002.

## Behaviors

- statement: token generation must not use MD5 or any other non-cryptographic/low-entropy
    construction. Target: a cryptographically random value with ≥128 bits of entropy (e.g.
    `secrets.token_urlsafe(32)` in Python, or the target ORM/framework's equivalent).
  fidelity: REPAIR — target ratified by PB-002 itself (the requester explicitly named this as
    security-flagged). See ED-002 (currently UNSIGNED, needs human confirmation of the exact
    algorithm — see that file's header note).
  evidence: [ticketd/app/server.py:90, docs/domain/reset_token.md]
- statement: only a hash of the token is stored server-side; the raw token exists only transiently
    (in the HTTP response... actually NOT in the HTTP response at all, see below) and in the
    outbound notification.
  fidelity: REPAIR (new requirement, not present in legacy at all — legacy stores the raw MD5
    string directly). FREE on exact hash algorithm (bcrypt/argon2/sha256 of the random token are
    all reasonable; record the choice).
  evidence: [ticketd/app/server.py:90-93 — legacy stores the raw token value directly, this is
    exactly the "bare table" problem PB-002 names]
- statement: the raw token NEVER appears in `POST /api/auth/reset`'s HTTP response body — it is
    legacy behavior that the token only ever leaves the server via the notification, never the API
    response (`{"ok": true}` only). Preserve this.
  fidelity: FIXED. evidence: [ticketd/app/server.py:95, trace: reset-request-001 — response body
    is `{"ok": true}`, no token]
- statement: tokens expire after 30 minutes; expired and not-found tokens return the IDENTICAL
    error body/status (`403 {"error": "invalid_token"}`) — deliberate non-disclosure.
  fidelity: FIXED (outcome) — the CHECK-on-read-vs-proactive-sweep mechanism is FREE, but "expired
    and invalid are indistinguishable" is a hard requirement regardless of mechanism.
  evidence: [ticketd/app/server.py:103-105, traces: reset-confirm-already-consumed-003,
    reset-confirm-invalid-004 — verified byte-identical in
    verification/characterization/test_auth_reset.py. P9 audit correction: trace 003 is a
    CONSUMED token (row deleted, hits the "row is None" disjunct), not a genuinely
    time-expired-but-still-present row (the time-based disjunct) — see that trace's note. The
    claim itself is still verified true by direct source reading (both disjuncts share one
    return), but no trace in the corpus yet exercises the time-based branch specifically; capture
    one (mint a token, wait 31 minutes or manipulate created_ts directly in a test DB, confirm)
    before treating this WO's L3 coverage of the expiry branch as complete.]
- statement: unlike legacy (no expiry sweep at all -- rows accumulate forever, part of "bare
    table"), the new storage must have a bounded-growth story: either proactive expiry cleanup (a
    scheduled job / DB-level TTL) or an equivalent guarantee that abandoned tokens don't
    accumulate indefinitely.
  fidelity: REPAIR (PB-002's "bare table" complaint is about BOTH the weak hash AND unbounded
    growth — this addresses the second half). FREE on mechanism.
  evidence: [ticketd/db/schema.sql:18-22 — no index, no PK, no expiry column beyond
    created_ts checked only at read time, docs/domain/reset_token.md]
- statement: tokens are single-use (deleted/invalidated immediately on successful confirm).
  fidelity: FIXED. evidence: [ticketd/app/server.py:106]
- statement: no relationship to the `users` table — a reset can be "requested" for any email
    string, and the response never discloses whether the email corresponds to a real user.
  fidelity: FIXED — this is a real, if perhaps accidental, security-conscious property; preserve
    it explicitly, don't let a new "does this user exist" check creep in.
  evidence: [ticketd/app/server.py:83-95, docs/domain/reset_token.md]

## Acceptance

- L1: n/a (this WO has no HTTP surface of its own — it's a library WO-004 calls; WO-004 owns the
  route-level contract).
- L2: unit tests asserting: token entropy/format (e.g. length, character set, not
  reproducible from email+timestamp the way MD5 was), only a hash is persisted (query the storage
  directly in the test and assert the raw token isn't present), expiry behavior, single-use
  behavior, and the non-disclosure property (expired vs. not-found produce identical outputs from
  this module's own API, not just at the HTTP layer — WO-004 re-verifies at HTTP level).
- L3: n/a directly (WO-004's `diff-run.sh auth-reset` exercises this WO indirectly via ED-002).
- gate: **true** — security-sensitive mechanism choice (PB-002, security-flagged). A human should
  confirm the specific hash algorithm and storage design before this closes. Record the FREE
  choice made in `ledger.json`'s `free_choices` for this WO.

## Escalation

Consult `ticketd/app/server.py:80-108` and `ticketd/db/schema.sql:18-22` only if
`docs/domain/reset_token.md` leaves the current mechanism's exact shape unclear.
