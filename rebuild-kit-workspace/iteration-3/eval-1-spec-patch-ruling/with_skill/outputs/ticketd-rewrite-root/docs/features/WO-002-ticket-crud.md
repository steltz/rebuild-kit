# WO-002 — ticket CRUD
id: WO-002    depends_on: []    milestone: M1    gate: false    context_budget: ~250 lines
behaviors:
  - statement: GET /api/tickets/<id> returns 200 with {} for missing tickets, never 404 (legacy UI depends on it).
    fidelity: FIXED
    evidence: [ticketd/app/server.py:58-64]
  - statement: Slug generation truncates at 64 chars (unchanged mechanism; PB-003, severity med).
      Legacy silently collides on near-identical titles (e.g. "Fix DB" and "fix db!" produce the
      same slug and the later insert's slug is indistinguishable from the earlier one on lookup).
      Target behavior (ruled OQ-002): slugs must be unique. On collision, append a numeric suffix
      to the truncated slug — first collision `<slug>-2`, next `<slug>-3`, etc. Existing stored
      slugs in migrated data are left exactly as they are; uniqueness is enforced only for newly
      created tickets going forward.
    fidelity: REPAIR — target: unique slug with numeric collision suffix (ruled OQ-002)
    evidence: [ticketd/app/util.py:4-6, ticketd/app/server.py:50-55]
    divergence: ED-002
acceptance:
  replay_set: tickets-*.jsonl (ED-002 applies; add slug-collision cases — see
    verification/replay/expected-divergences.yaml)
escalation: implement uniqueness as an application-level check-and-suffix at write time
  (query existing slugs / retry on conflict), not a table-level UNIQUE constraint — legacy
  data may already contain duplicate slugs, and OQ-002's ruling explicitly leaves already-stored
  slugs unmigrated, so a hard DB constraint could reject a straight carry-over of legacy rows.
  If docs/migration/ later defines a carry-over path for `tickets`, re-check this note against it.
