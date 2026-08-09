# WO-006 — Password-reset confirm (the PB-002 repair, part 2)

id: WO-006            depends_on: [WO-005]          milestone: M2
risk: 0.45 (claims cited+traced, small surface; one inferred-only unknown — OQ-006 —
  reviewed at the M2 milestone gate)
usage_weight: 0.01    pain_weight: 0.20             context_budget: ~250 lines   gate: false

Reading list: this file · `docs/contracts/openapi.yaml` (confirm) ·
`docs/domain/reset-token.md` · `docs/open-questions.md#OQ-006`.

behaviors:
  - statement: body JSON, token defaults to ""; lookup by token (modern: constant-time
      compare against stored hash — mechanism FREE within PB-002's target).
    fidelity: FIXED (observable contract)
    evidence: [ticketd/app/server.py:100-102, trace: t2-core#auth-reset-confirm-001]
  - statement: unknown token AND expired token (age > 30 min) return the IDENTICAL response:
      403 {"error":"invalid_token"} — deliberate non-disclosure; never differentiate.
    fidelity: FIXED
    evidence: [ticketd/app/server.py:103-105 (comment "deliberate"), trace:
      auth-reset-confirm-003; expiry leg: characterization
      test_auth_reset.py::test_expired_token_same_body_as_invalid (passes vs legacy boot,
      harness baseline)]
  - statement: valid token → consume it (single-use) → 200 {"ok": true, "email": <email>}.
      Modern consumption must be atomic (DELETE..RETURNING or equivalent) — same observable
      behavior, closes legacy's SELECT-then-DELETE race (mechanism note, not a divergence).
    fidelity: FIXED
    evidence: [ticketd/app/server.py:106-108, traces: auth-reset-confirm-001/002]
  - statement: no rate limit, no bypass logic on confirm.
    fidelity: FIXED
    evidence: [ticketd/app/server.py:98-108 (absence)]
  - statement: what downstream consumes the returned email is unknown (no password store
      exists in this system).
    fidelity: ASK — open-questions.md#OQ-006 (blocks: none; flags M2 milestone review).
      Implement the observable contract exactly; change nothing about the response shape.
    evidence: [ticketd/db/schema.sql:12-16, docs/domain/user.md]

acceptance:
  replay_set: auth-reset-confirm-001..003 from t2-core (no divergences apply — the response
    surface is unchanged by ED-002)
  tests: verification/characterization/test_auth_reset.py (confirm-side tests,
         CHAR_TARGET=modern)
escalation: consult ticketd/app/server.py:98-108 only on ambiguity.
