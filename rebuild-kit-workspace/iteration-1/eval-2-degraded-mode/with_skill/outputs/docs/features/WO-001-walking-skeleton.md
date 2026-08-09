# WO-001 — Walking skeleton: FastAPI + Postgres + harness plumbing + list tickets

id: WO-001            depends_on: []          milestone: M0
risk: 0.55 (first contact with stack + harness contract; no legacy coverage; systemic
  misreads surface here by design)          gate: true (M0 gate)
usage_weight: 0.35 (static-proxy — GET /api/tickets)   pain_weight: 0.0
context_budget: ~400 lines (this WO + modern/CLAUDE.md + harness/README.md + openapi.yaml
  paths./api/tickets.get + domain/ticket.md)

## Scope
One thin end-to-end slice in `modern/`: app boots against Postgres via env config, serves
GET /api/tickets, and satisfies the harness boot contract so L3 runs at all. This WO exists
to prove the plumbing while errors cost one WO, not nine.

behaviors:
  - statement: GET /api/tickets returns all rows (all 8 legacy columns, closed_at/assignee_id
      null when unset), newest-first; optional exact-match `?status=` filter, unvalidated —
      unknown values yield [] with 200. No pagination.
    fidelity: FIXED
    evidence: [ticketd/app/server.py:27-37, trace: tickets-list-001..004, skeleton-list-001]
  - statement: Response rows carry legacy column names and value vocabularies (med not
      medium; open/closed) — the DB schema is modern (timestamptz, enums) but the JSON
      surface is legacy-shaped.
    fidelity: FIXED
    evidence: [docs/contracts/openapi.yaml#/components/schemas/Ticket, ticketd/db/schema.sql:1-10]
  - statement: Harness boot contract — `modern/harness/boot.sh` (PORT/HARNESS/SEED_JSON;
      fresh DB from seed; `__harness__/state` + `__harness__/emails`; stdout env lines).
    fidelity: FIXED (it is the harness API — see verification/harness/README.md)
    evidence: [verification/harness/README.md, verification/harness/run-modern.sh]
  - statement: Storage layout, ORM usage, migration tooling, process model.
    fidelity: FREE — per modern/CLAUDE.md (Alembic owns the schema; UTC timestamptz per
      DNP-004). Record choices in ledger free_choices.

acceptance:
  replay_set: skeleton.jsonl → traces skeleton-list-001 + session-end-state must pass
    (full core set not required until M1 close)
  tests: characterization TestListGet::test_bogus_status_filter_empty_200 (others need M1 WOs)
  l1: GET /api/tickets response validates against openapi.yaml
gate_packet: guide/briefs/gate-M0.md — stack sanity, harness proof (report.json), FREE choices
escalation: ticketd/app/server.py:27-37 only if the list contract seems ambiguous
