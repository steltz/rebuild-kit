# WO-002 — ticket CRUD
id: WO-002    depends_on: []    milestone: M1    gate: false    context_budget: ~250 lines
behaviors:
  - statement: GET /api/tickets/<id> returns 200 with {} for missing tickets, never 404 (legacy UI depends on it).
    fidelity: FIXED
    evidence: [ticketd/app/server.py:58-64]
  - statement: Slug generation truncates at 64 chars and collides on near-identical titles.
    fidelity: REPAIR — target: slugs must be unique; on collision, append a numeric suffix (-2, -3, ...) to the generated slug. Existing stored slugs are not migrated (ruling on open-questions.md#OQ-002)
    evidence: [ticketd/app/util.py:4-6]
    divergence: ED-002
acceptance:
  replay_set: tickets-*.jsonl
