# docs/features/WO-002-tickets-close.md
id: WO-002            depends_on: [WO-001, WO-004]       milestone: M1
risk: 0.45 (inferred-claim ratio low, fully boot-verified; but embeds a REPAIR whose
  expected-divergence entry is unratified [see WO-004], and legacy test coverage is zero —
  pushed just under the 0.5 gate threshold since the close-endpoint's OWN state-transition
  logic is fully FIXED/cited and low-complexity; the REPAIR risk is carried by WO-004's gate)
usage_weight: none (degraded)   pain_weight: 1.0 (PB-001)   context_budget: ~250 lines
gate: false (see WO-004 for the gated portion this WO depends on)

behaviors:
  - statement: Close a ticket — sets status='closed' + closed_at, only if not already closed
    (idempotent; repeat close is a no-op, response reflects whether THIS call transitioned it,
    not current status). No 404 case; closing a nonexistent id returns `{"closed": false}`.
    fidelity: FIXED
    evidence: [legacy/app/server.py:67-77, verification/replay/traces/tickets.legacy.jsonl#tickets-close-happy,
      #tickets-close-already-closed, #tickets-close-missing]
  - statement: On successful transition, dispatch a notification to watchers@example.internal
    (hardcoded, single recipient, no per-ticket/team watcher concept exists) via WO-004's
    dispatch boundary — NOT synchronously in-request.
    fidelity: REPAIR — see WO-004 for the dispatch mechanism; this WO's own scope is calling
    the boundary correctly and only on a real transition (matching legacy's `if changed:` guard
    exactly — legacy/app/server.py:73).
    evidence: [legacy/app/server.py:73-76]   divergence: ED-001

acceptance:
  replay_set: verification/replay/corpus/tickets.requests.jsonl (traces: tickets-close-happy,
    tickets-close-already-closed, tickets-close-missing)
  tests: verification/characterization/test_tickets.py (test_close_idempotent_already_closed,
    test_close_missing_ticket, test_close_dispatches_notification_asynchronously)
escalation: consult legacy/app/server.py:67-77 only.
