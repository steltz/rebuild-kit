# WO-007 — Data migration: SQLite → Postgres

id: WO-007            depends_on: [WO-002, WO-003, WO-004, WO-005, WO-006]   milestone: M3
risk: 0.75 (data_census INACTIVE — no prod counts; OQ-005 blocks the timestamp policy;
  migration errors are the classic rewrite-killer)
usage_weight: —       pain_weight: 0.15             context_budget: ~400 lines   gate: true
blocked_by_asks: [OQ-005]

Reading list: this file · `docs/migration/mapping.md` · `docs/migration/census.md` ·
`docs/migration/target-schema.sql` · `docs/migration/reconciliation.sql` ·
`docs/contracts/ddl.sql`.

behaviors:
  - statement: implement the loader per mapping.md — users, then tickets, then sequences;
      single transaction; source opened read-only.
    fidelity: FREE — mechanism (Python loader vs pgloader vs COPY) is open; mapping.md's
      table is the contract.
  - statement: created_at/closed_at conversion policy.
    fidelity: ASK — OQ-005 BLOCKS this WO (naive local strings; server TZ unknown; target
      timestamptz). Do not guess a timezone.
    evidence: [ticketd/app/server.py:52 (comment "naive local time!"), docs/migration/mapping.md]
  - statement: reset_tokens are NOT migrated (cutover starts empty).
    fidelity: REPAIR-adjacent policy (PB-002/DNP-003) — ratify at this WO's gate; the
      mapping.md proposal is not yet human-approved.
    evidence: [docs/migration/mapping.md]
  - statement: dirty-data policies (orphan assignee FKs, out-of-range enums, I4 violations)
      per census results.
    fidelity: ASK — census not yet run (needs prod access, problem-brief intake q5);
      every repair/quarantine/drop policy needs a human ruling against real counts.
    evidence: [docs/migration/census.md (NOT RUN), docs/migration/census-queries.sql]

acceptance:
  replay_set: none (not a behavior WO)
  reconciliation: every query in docs/migration/reconciliation.sql returns its "expect"
    value against a migrated copy of a prod-shaped snapshot (harness inner loop: migrate
    the seeded SQLite fixture; rehearsal gate: the real snapshot, WO-008).
  tests: loader unit tests in modern/ per its conventions.
escalation: docs/contracts/ddl.sql is the source schema authority; ticketd/db/schema.sql
  only via the pin.
