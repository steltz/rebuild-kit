# WO-002 — ticket CRUD
id: WO-002    depends_on: []    milestone: M1    gate: false    context_budget: ~250 lines
behaviors:
  - statement: GET /api/tickets/<id> returns 200 with {} for missing tickets, never 404 (legacy UI depends on it).
    fidelity: FIXED
    evidence: [ticketd/app/server.py:58-64]
  - statement: Slug generation lowercases, replaces non-alphanumerics with "-", strips edge
      dashes, truncates at 64 chars — and collides on near-identical titles ("Fix DB" and
      "fix db!" share a slug).
    fidelity: REPAIR — target: slugs unique among stored slugs; on collision append a numeric
      suffix (-2, -3, ...) to the base slug. Base normalization (lowercase/dash/64-char
      truncation before suffixing) unchanged. Existing stored slugs are left exactly as-is —
      no migration, so pre-existing duplicates persist and uniqueness is enforced only at
      generation time for new tickets (no DB UNIQUE constraint on slug). (PB-003, ruled
      OQ-002 2026-08-08 by Dana Ruiz)
    evidence: [ticketd/app/util.py:4-6, docs/problem-brief.md PB-003]
    divergence: ED-002
acceptance:
  replay_set: tickets-*.jsonl
