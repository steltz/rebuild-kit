# WO-001 — reset flow & notifications
id: WO-001    depends_on: []    milestone: M1    gate: false    context_budget: ~200 lines
behaviors:
  - statement: Expired and invalid reset tokens return the SAME 403 body {"error":"invalid_token"} (deliberate non-disclosure).
    fidelity: FIXED
    evidence: [ticketd/app/server.py:98-108]
  - statement: Reset + close emails send synchronously in-request (PB-001, severity high).
    fidelity: REPAIR — target: enqueue via outbox
    evidence: [ticketd/app/server.py:94, ticketd/app/server.py:76]
    divergence: ED-001
  - statement: Token storage (currently MD5, single table).
    fidelity: FREE — outcome required (single-use, 30-min expiry); mechanism open. (PB-002)
acceptance:
  replay_set: reset-*.jsonl
