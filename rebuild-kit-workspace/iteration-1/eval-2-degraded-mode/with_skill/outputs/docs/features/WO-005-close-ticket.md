# WO-005 — Close ticket + watcher notification (PB-001 call site 1)

id: WO-005            depends_on: [WO-001, WO-004]    milestone: M1
risk: 0.40 (REPAIR call site; idempotency semantics; commit-before-send hazard replaced)
gate: false
usage_weight: 0.15 (static-proxy)   pain_weight: 0.5 (PB-001 high — "SMTP outages take
  ticket-closing down with them", in-code comment)
context_budget: ~250 lines (this WO + draft/tickets.md#close + openapi.yaml close path)

behaviors:
  - statement: Open ticket → status 'closed', closed_at set, response `{"closed": true}`.
      Already-closed or unknown id → no state change, `{"closed": false}`, 200 (no 404
      distinction). Transition guard equivalent to `status != 'closed'` (concurrency-safe
      single UPDATE, not read-then-write).
    fidelity: FIXED
    evidence: [ticketd/app/server.py:67-77, trace: tickets-close-001..003]
  - statement: Exactly one notification per successful transition to hardcoded-in-legacy
      `watchers@example.internal`, content marker `closed: <title>`; none on no-op close.
      Recipient becomes env-config in modern (mechanism), the address value and trigger
      condition stay behavior.
    fidelity: FIXED (trigger + recipient + content marker) / FREE (config surface)
    evidence: [ticketd/app/server.py:73-76, trace: tickets-close-001 (email observed),
      tickets-close-002-again (no email observed)]
  - statement: Dispatch goes through WO-004's seam — queued, never in-request; the legacy
      500-after-commit failure shape (close committed, response 500, no email) ceases to
      exist; response is 200 whenever the state transition succeeds.
    fidelity: REPAIR — PB-001; divergence: ED-001
    evidence: [ticketd/app/server.py:72-76 (commit-before-send),
      ticketd/app/notify.py:1 (latency docstring); failure shape inferred — no fault-
      injection trace exists yet]

acceptance:
  replay_set: core.jsonl → traces tickets-close-* must pass (ED-001 applies)
  tests: characterization TestCloseTicket; modern/tests: SMTP-down close still returns
    {"closed": true} and the event is durably queued
escalation: ticketd/app/server.py:67-77
