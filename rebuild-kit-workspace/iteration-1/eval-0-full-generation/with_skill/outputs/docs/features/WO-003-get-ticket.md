# WO-003 — Get ticket

id: WO-003            depends_on: [WO-001]          milestone: M1
risk: 0.15 (three claims, all cited+traced; one Hyrum-critical quirk)
usage_weight: 0.092   pain_weight: 0.0              context_budget: ~150 lines   gate: false

Reading list: this file · `docs/contracts/openapi.yaml` (GET /api/tickets/{tid}).

behaviors:
  - statement: integer path param; non-integer path does not match the route → 404 with a
      text/html framework error page (body free — diff rules compare status + media type).
    fidelity: FIXED
    evidence: [ticketd/app/server.py:58, trace: t2-core#tickets-get-003]
  - statement: existing id → 200, full row as a JSON object (same field set as the list route).
    fidelity: FIXED
    evidence: [ticketd/app/server.py:60-64, trace: tickets-get-001]
  - statement: missing id → 200 with {} — NOT 404. The legacy UI depends on this. Do not fix.
    fidelity: FIXED
    evidence: [ticketd/app/server.py:61-63 (comment), PB-005, trace: tickets-get-002]

acceptance:
  replay_set: tickets-get-001..003 from t2-core (3 traces; no divergences apply)
  tests: verification/characterization/test_tickets.py::test_get_missing_returns_200_empty_object
escalation: consult ticketd/app/server.py:58-64 only on ambiguity.
