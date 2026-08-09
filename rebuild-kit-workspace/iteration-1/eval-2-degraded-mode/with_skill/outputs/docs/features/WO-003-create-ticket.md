# WO-003 — Create ticket (validation, priority aliases, slug derivation)

id: WO-003            depends_on: [WO-001]    milestone: M1
risk: 0.35 (two sanctioned FREE deviations to get exactly right; alias surface easy to
  under-implement)          gate: false
usage_weight: 0.20 (static-proxy)   pain_weight: 0.0
context_budget: ~300 lines (this WO + draft/tickets.md#create + openapi.yaml POST /api/tickets
  + fixtures/tickets.json)

behaviors:
  - statement: Missing/empty/whitespace title (incl. non-JSON or absent body treated as {})
      → 422 `{"error":"title_required"}`.
    fidelity: FIXED
    evidence: [ticketd/app/server.py:42-45, trace: tickets-create-422-*]
  - statement: Priority aliases — "1"/"2"/"3" and integers 1/2/3 → low/med/high; absent →
      "med"; literals low/med/high pass; extra body fields silently ignored.
    fidelity: FIXED (Hyrum register items 1-3, docs/contracts/integration-notes.md)
    evidence: [ticketd/app/server.py:47-49, trace: tickets-create-001..003]
  - statement: slug = legacy derivation exactly (lower, [^a-z0-9]+→'-', strip '-', :64);
      empty slug (symbol-only title) accepted; NOT unique; never regenerated later.
    fidelity: FIXED (derivation; OQ-003 notes purpose is unknown — port, don't improve)
    evidence: [ticketd/app/util.py:4-6, trace: tickets-create-004-symbolslug]
  - statement: Success → 201 with exactly {"id", "slug"}; row status 'open'; creation
      instant recorded (UTC in modern — DNP-004; diff rules normalize).
    fidelity: FIXED (response/status-seed) / FREE (timestamp representation)
    evidence: [ticketd/app/server.py:50-55, trace: tickets-create-001]
  - statement: Out-of-vocabulary priority → 422 `{"error":"priority_invalid"}` (legacy: 500
      via CHECK IntegrityError). Non-string title → 422 `{"error":"title_invalid"}` (legacy:
      500 via AttributeError). Sanctioned FREE deviations — divergences ED-004a/ED-004b;
      bodies are pinned by the manifest, do not invent different ones.
    fidelity: FREE — divergence: ED-004a, ED-004b
    evidence: [ticketd/app/server.py:43,47-53, trace: tickets-create-badpriority-001,
      tickets-create-badtitle-001 (observed 500s)]

acceptance:
  replay_set: core.jsonl → traces tickets-create-* must pass (ED-004a/b apply)
  tests: characterization TestCreateTicket (all)
escalation: ticketd/app/server.py:40-55, ticketd/app/util.py:4-6
