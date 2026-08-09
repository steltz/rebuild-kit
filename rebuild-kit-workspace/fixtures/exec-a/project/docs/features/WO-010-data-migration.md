id: WO-010            depends_on: [WO-001, WO-003, WO-005]  milestone: M2
risk: 0.75 (data destruction risk if mishandled; multiple ASK policies unratified;
  data_census currently inactive -- no real counts exist yet; "more rewrites die in the data
  than in the code")
usage_weight: n/a (not a route)
pain_weight: n/a
context_budget: ~500 lines (this WO + docs/migration/*.md + docs/migration/census-queries.sql
  + docs/migration/reconciliation.sql)
gate: true (data migrations are always gated; additionally blocked on human-run census results
  and on OQ-001/OQ-003/OQ-005/OQ-007's rulings where they affect migration policy)

## What this WO does
Execute the migration plan in `docs/migration/`: run the census for real against prod-shaped
data, get every ASK policy ratified, run the transform, reconcile, rehearse per
`docs/migration/cutover.md`. This WO CANNOT be picked up by an unattended executor session in
full — steps 1-3 below are human-gated by design (P6: "data destruction is never a generator
decision").

behaviors:
  - statement: "tickets and users migrate as a straight column-mapped translation (see
      mapping.md) with one addition: a UNIQUE constraint on tickets.slug (WO-005's outcome)
      and enforced (not just declared) tickets.assignee_id -> users.id referential integrity
      (Postgres default -- see OQ-005)."
    fidelity: REPAIR (the two tightenings) / FIXED (everything else about the shape)
    evidence: [docs/migration/mapping.md, docs/open-questions.md OQ-005]
  - statement: "reset_tokens is a full redesign per WO-003, not a translated table. Policy for
      pre-existing legacy rows at cutover time (drop-with-log recommended, not ratified)."
    fidelity: ASK — see mapping.md's reset_tokens section; requires human ratification before
      this WO can close, independent of WO-003's mechanism already being implemented.
    evidence: [docs/migration/mapping.md]
  - statement: "Backfill policy for any pre-existing tickets.slug collisions (found by census
      probe #26/#27) must be decided before the UNIQUE constraint from WO-005 can even be
      added to a populated table."
    fidelity: ASK — blocked on real census numbers (currently unrun) AND on OQ-001's ruling.
    evidence: [docs/migration/census.md probes 26-27]

acceptance:
  replay_set: n/a (migration correctness is verified by reconciliation.sql, not a replay set)
  tests: docs/migration/reconciliation.sql — every query (R1-R7 at minimum; R8 or R8-alt
    depending on the ratified reset_tokens policy) must pass against a real or rehearsal
    dataset
  l1: n/a
  l3: after migration, the FULL replay suite (all 7 suites) re-run against modern booted from
    migrated data, not just the T2 seed fixture — this is the actual proof the migration
    didn't silently corrupt anything the seed-fixture-based per-WO replay sets wouldn't catch

escalation: this WO is mostly human process (docs/migration/cutover.md), not code — read the
  whole docs/migration/ directory, not a legacy code citation.
