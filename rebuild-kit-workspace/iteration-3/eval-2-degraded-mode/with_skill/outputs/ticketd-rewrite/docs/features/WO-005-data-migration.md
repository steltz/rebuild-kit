# docs/features/WO-005-data-migration.md
id: WO-005            depends_on: [WO-001, WO-002, WO-003]   milestone: M2
risk: 0.70 (data_census inactive — no production DB access this run [rebuild.json.evidence];
  P6 degraded-mode rule: migration WOs get elevated risk scores; the reset_tokens
  drop-with-log policy proposed in docs/migration/mapping.md is a data-destruction decision,
  which schema.md is explicit is never a generator decision)
usage_weight: none (degraded)   pain_weight: 0 (not brief-motivated; ordinary migration risk)
context_budget: ~400 lines (docs/migration/*.md + docs/contracts/ddl.sql)    gate: true

behaviors:
  - statement: Migrate tickets, users, reset_tokens from SQLite to the target Postgres schema
    per docs/migration/mapping.md's column-by-column mapping.
    fidelity: FREE for storage mechanism (types, PK strategy); FIXED for the data itself
    (values must round-trip exactly per reconciliation.sql, modulo the ASKs below).
    evidence: [docs/contracts/ddl.sql, docs/migration/mapping.md]
  - statement: created_at/closed_at timezone handling at migration time.
    fidelity: ASK — docs/migration/mapping.md's "created_at" row. No source timezone is
    confirmed (legacy values are naive local server time, offset unknown). Do not guess an
    offset; migrate as naive TIMESTAMP unless a human ruling supplies a confirmed offset.
    evidence: [legacy/app/server.py:52, docs/migration/mapping.md]
  - statement: reset_tokens rows in flight at cutover.
    fidelity: ASK — docs/migration/mapping.md recommends drop-with-log (tokens are short-lived
    and the generation mechanism is changing under PB-002 regardless), but this is a data
    destruction decision requiring explicit human sign-off at the cutover gate, not a default
    to implement unprompted.
    evidence: [docs/migration/mapping.md#reset_tokens]
  - statement: Slug collisions and any dirty data found by docs/migration/census-queries.sql
    (UNRUN this pass — no DB access) must be handled per a ratified policy, not invented at
    migration time.
    fidelity: ASK — docs/migration/census.md is entirely UNRUN. This WO cannot proceed past
    planning until census-queries.sql has been run against real data and policies ratified.
    evidence: [docs/migration/census.md, docs/problem-brief.md#OQ-INTAKE-01]

acceptance:
  replay_set: N/A (this WO is not an HTTP-surface change)
  tests: docs/migration/reconciliation.sql (row counts, checksums, stratified sample diff,
    orphaned-FK check — all UNRUN this pass, see docs/migration/reconciliation.sql header)
escalation: consult docs/migration/*.md and docs/contracts/ddl.sql only; this WO should not
  need to read legacy/ source beyond what P6 already cited.

## Gate note

`gate: true` for three independent reasons, any one of which would justify it alone: no
production data access yet (docs/problem-brief.md OQ-INTAKE-01), a live data-destruction policy
proposal awaiting ratification (reset_tokens drop-with-log), and P6's own degraded-mode rule
elevating migration WO risk automatically. Do not attempt this WO until
docs/problem-brief.md's OQ-INTAKE-01 is resolved (DB access granted) and census-queries.sql has
been run.
