# WO-006 — Data migration (tickets, users, reset_tokens)

id: WO-006            depends_on: [WO-002, WO-003]      milestone: M2
risk: 0.80 (elevated per P6's degraded-mode rule: data_census is inactive, every dirty-data
  policy in docs/migration/mapping.md is ASK, and OQ-001/OQ-003/OQ-005 all block or flag pieces
  of this WO. This is the highest-risk WO in the backlog by design — it's the one most starved
  of evidence.)
usage_weight: n/a (migration WO, not a route)
pain_weight: n/a
context_budget: ~500 lines (this WO + docs/migration/*.md + docs/domain/*.md + all three OQ
  entries it depends on)
gate: true (data destruction/transformation is never a generator or executor decision — every
  policy here needs an explicit human ruling first)

## BLOCKED — this WO cannot start until:

1. Production database access exists (per the rewrite request: "maybe in a few weeks") and
   `docs/migration/census.md`'s queries have been run — every row in that table is currently
   blank.
2. `docs/open-questions.md#OQ-001` (naive-local-time -> UTC conversion — needs to know which
   server timezone legacy actually ran in) is ruled.
3. `docs/open-questions.md#OQ-003` (is `users`/`assignee_id` dead or externally maintained) is
   ruled — determines whether `users` migrates at all and whether the `assignee_id` FK gets
   enforced.
4. `docs/open-questions.md#OQ-005` (slug uniqueness) is ruled — determines whether a UNIQUE
   constraint is added during migration or collision-permissive behavior carries forward.
5. Every "policy: ASK" cell in `docs/migration/mapping.md` is ratified (repair / quarantine /
   drop-with-log, per class).

## What this WO does once unblocked

Implement the ratified mapping from `docs/migration/mapping.md`, run the census queries for
real, execute the migration against a snapshot, and pass every check in
`docs/migration/reconciliation.sql` (row counts, per-column checksums, stratified field-level
diffs, orphan-FK check if OQ-003 rules `users` stays and FK enforcement is turned on).

## Escalation

None yet — this WO is blocked on human input, not on legacy source. Do not read ahead into
`legacy/db/schema.sql` beyond what `docs/contracts/ddl.sql` already gives you; there's nothing
more to extract from source here, only rulings to obtain.

## Acceptance

- Reconciliation: 100% of `docs/migration/reconciliation.sql`'s checks pass between the SQLite
  source and the Postgres target on a real (or realistic snapshot) dataset.
- Gate: STOP for human sign-off — this WO closes only with an explicit approval recorded in
  `ledger.json` (`gate_approved_by`), given the data-destruction stakes.
