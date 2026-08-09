id: WO-005            depends_on: [WO-002, WO-004]        milestone: M3
risk: 0.7 (data-destructive-adjacent decisions, two unresolved OQs directly gate parts of this
  WO's scope, no production data was available to this generator run to pre-validate any of it)
usage_weight: n/a (one-time operation)   pain_weight: n/a   context_budget: ~300 lines   gate: true

## Reading list

- `docs/migration/mapping.md` — full (this WO's primary source).
- `docs/migration/census.md` + `census-queries.sql` — run these against real data FIRST, this WO
  cannot proceed meaningfully without real census results (see Degraded Mode note below).
- `docs/migration/reconciliation.sql` — this WO's acceptance queries.
- `docs/open-questions.md#OQ-009` and `#OQ-010` — both must be ruled before this WO can fully
  close (see Behaviors).
- `docs/do-not-port.md` and `#OQ-003` — the cutover checklist item.

## Degraded mode notice — read this first

`rebuild.json.evidence.data_census: inactive` — **no production database or SQLite data file was
available to this generator run.** Every row in `docs/migration/census.md` is unfilled by design.
**This WO cannot responsibly execute until a human runs `census-queries.sql` (plus its manual
addition, query #26, for slug duplicates) against real production-shaped data and the results are
recorded in `census.md`.** Do not invent plausible-sounding data characteristics to fill this gap.
If this WO is picked up before that census exists, the correct action is to file/escalate the
census request (it's already drafted, just needs someone with data access to run it), not to
proceed on assumptions.

## Behaviors

- statement: `tickets` and `users` table data migrates with ids preserved (both are FK/referenced
    by ids elsewhere) and every column direct-copied except where a policy below applies.
  fidelity: FIXED intent (preserve data), FREE on exact migration tooling (a script, an ETL tool,
    manual `COPY` + transform SQL are all fine).
  evidence: [docs/migration/mapping.md tables: tickets, users]
- statement: `tickets.priority`/`tickets.status` values outside their legacy CHECK-constrained
    enum sets (if any are found by census #13/#14) need a ratified policy (repair/quarantine/
    drop-with-log) before migrating — **do not pick one unilaterally**.
  fidelity: ASK — blocked on census results + human ratification of the specific policy, per
    `docs/migration/mapping.md` and `references/schema.md`'s "data destruction is never a
    generator decision" rule (which extends to this WO's execution, not just this workspace's
    generation).
- statement: `tickets.assignee_id` orphaned-FK handling (rows pointing at nonexistent `users.id`,
    possible because SQLite never enforced this FK) needs a ratified policy before migrating,
    since Postgres will enforce it by default and reject orphaned rows outright.
  fidelity: ASK — blocked on census #12 results + ratification. Recommended default (not a
    unilateral choice, a recommendation for the human ratifying): null-out orphaned references,
    since `docs/domain/users.md` confirms no app code ever reads this column anyway.
- statement: `tickets.created_at`/`closed_at` migration transform depends on OQ-006's ruling
    (naive-preserve vs. UTC-aware REPAIR) AND OQ-009 (what timezone did legacy actually run in?).
  fidelity: ASK — blocked on BOTH OQ-006 and OQ-009. This WO cannot correctly migrate these two
    columns without both answers; everything else in this WO can proceed independently.
- statement: `reset_tokens` legacy rows are NOT migrated by default (every row is transient,
    already consumed/expired/superseded by WO-003's new mechanism).
  fidelity: ASK (pb-proposal) — blocked on OQ-010's ruling, though the generator's stated default
    (don't migrate) needs only a human's explicit sign-off to proceed, not a contested decision.
  evidence: [docs/migration/mapping.md table: reset_tokens]
- statement (cutover checklist, not a migration-of-data behavior): before legacy is decommissioned,
    confirm no out-of-band consumer of `GET /internal/export/csv` exists (PB-009/OQ-003) — the
    supplied access-log evidence for this is weaker than the genuine 30-day window the original
    request described (see `docs/open-questions.md#OQ-003` and `rebuild.json.evidence.notes`).
  fidelity: n/a (process step, not a code behavior) — but this WO's milestone (M3, cutover) should
    not close without this checklist item explicitly signed off.

## Acceptance

- L1/L2: n/a (data migration, not a route).
- L3 (reconciliation, this WO's real acceptance bar): every query in
  `docs/migration/reconciliation.sql` run against BOTH source (legacy SQLite, once real data
  exists) and target (freshly migrated Postgres) must agree: row counts exact match, per-column
  checksums match (modulo the ratified policies above for any dirty data found), the FK-integrity
  query returns 0 on both sides (or a documented, ratified count of intentionally-nulled
  orphans), and a stratified sample field-level diff shows no unexplained deltas.
- gate: **true** — data-destructive-adjacent, blocked on two open questions, and this generator run
  had zero production data to validate any of it against. This is the highest-risk WO in the
  backlog and should not be treated as routine even though its acceptance criteria are mostly
  mechanical once the blocking ASKs are ruled.

## Escalation

Consult `ticketd/db/schema.sql` (whole file, 22 lines) if `docs/migration/mapping.md` leaves a
column's legacy type/constraint unclear. Do not read `ticketd/app/server.py` for this WO — data
shape questions are answered by the DDL and domain docs, not the route handlers.
