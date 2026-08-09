id: WO-006            depends_on: [WO-001]                 milestone: M1
risk: 0.35 (inferred-claim ratio low-medium: the non-integer-id/Flask-404-vs-FastAPI-422
  behavior is an inferred claim about framework defaults, not a cited line of ticketd's own
  code -- see docs/features/draft/tickets-get.md; no PB touches this; complexity trivial)
usage_weight: 0.092
pain_weight: 0.0
context_budget: ~150 lines (this WO + docs/features/draft/tickets-get.md)
gate: false

## What this WO does
Implement `GET /api/tickets/{id}`, preserving the historical 200-empty-object-on-miss quirk.

behaviors:
  - statement: "Existing id -> 200 with full ticket object. Nonexistent id -> 200 {} (empty
      object), NOT 404 -- explicitly a historical quirk the legacy UI depends on (PB-005: no
      UI changes means this is frozen)."
    fidelity: FIXED
    evidence: [legacy/app/server.py:58-64, docs/features/draft/tickets-get.md]
  - statement: "A non-integer path segment does not reach this operation's logic at all in
      legacy (Flask's <int:tid> converter rejects the route match, falling through to Flask's
      generic 404). FastAPI's default int path-param validation would instead return a
      structured JSON 422 -- an observable divergence if not deliberately matched."
    fidelity: FIXED (inferred confidence — this is Flask/FastAPI framework-default behavior,
      not a line of ticketd's own code; verify empirically against the actual legacy boot
      before treating as settled, don't just trust the inference)
    evidence: [legacy/app/server.py:58 (inferred from Flask <int:tid> semantics),
      verification/replay/traces/legacy/tickets-get.jsonl#tickets-get-003-non-integer-id
      (ACTUALLY CAPTURED from a real legacy boot -- this is traced, not just inferred; see
      that trace file's response: Flask's plain-text 404 page, confirmed empirically)]

acceptance:
  replay_set: tickets-get-*.jsonl (3 traces, captured T2 golden, self-check validated)
  tests: verification/characterization/test_against_golden.py
  l1: docs/contracts/openapi.yaml /api/tickets/{id} (note the x-legacy-note on the non-integer
    case)
  l3: verification/harness/diff-run.sh tickets-get

escalation: legacy/app/server.py:58-64 only.
