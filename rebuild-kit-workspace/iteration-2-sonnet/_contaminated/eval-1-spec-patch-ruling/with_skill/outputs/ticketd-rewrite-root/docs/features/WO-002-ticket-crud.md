# WO-002 — ticket CRUD
id: WO-002    depends_on: []    milestone: M1    gate: false    context_budget: ~250 lines
behaviors:
  - statement: GET /api/tickets/<id> returns 200 with {} for missing tickets, never 404 (legacy UI depends on it).
    fidelity: FIXED
    evidence: [ticketd/app/server.py:58-64]
  - statement: Slug generation truncates at 64 chars; legacy collides on near-identical
      titles (e.g. "Fix DB" and "fix db!" produce the same slug), silently overwriting
      lookups (PB-003, severity med).
    fidelity: REPAIR — target: slugs must be unique. On collision with an existing slug,
      append a numeric suffix (-2, -3, ...) and keep incrementing until unique. Existing
      stored slugs are NOT migrated/backfilled — this applies to newly generated slugs only
      (ruled OQ-002, Dana Ruiz, 2026-08-08).
    evidence: [ticketd/app/util.py:4-6]
    divergence: ED-002
acceptance:
  replay_set: tickets-*.jsonl
