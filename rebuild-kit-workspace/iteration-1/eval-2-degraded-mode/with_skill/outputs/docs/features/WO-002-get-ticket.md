# WO-002 — Get ticket (incl. the load-bearing 200-{} quirk)

id: WO-002            depends_on: [WO-001]    milestone: M1
risk: 0.15 (fully cited + traced; tiny surface)          gate: false
usage_weight: 0.15 (static-proxy)   pain_weight: 0.0
context_budget: ~150 lines (this WO + openapi.yaml paths./api/tickets/{tid} + domain/ticket.md)

behaviors:
  - statement: Known integer id → 200 full row dict (legacy column names).
    fidelity: FIXED
    evidence: [ticketd/app/server.py:64, trace: tickets-get-001]
  - statement: Unknown integer id → 200 with body exactly `{}` — NEVER 404. In-code comment
      marks the legacy UI dependency. This is the single most tempting "fix" in the codebase;
      it is FIXED until a ruling says otherwise.
    fidelity: FIXED
    evidence: [ticketd/app/server.py:61-63, trace: tickets-get-002-missing]
  - statement: Non-integer path segment → 404, framework-default body.
    fidelity: FIXED (status) / FREE (body — framework default on both sides)
    evidence: [ticketd/app/server.py:58]

acceptance:
  replay_set: core.jsonl → traces tickets-get-* must pass
  tests: characterization TestListGet::test_missing_ticket_is_200_empty_object
escalation: ticketd/app/server.py:58-64
