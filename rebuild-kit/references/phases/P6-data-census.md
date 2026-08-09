# P6 — Data Census & Migration Workstream

Outputs: `docs/migration/` — `census.md`, `mapping.md`, `transforms + reconciliation.sql` plan.

More rewrites die in the data than in the code, so migration is generated as ordinary,
verifiable work orders — not an appendix.

## Procedure

1. **Dirty-data census.** Generate probing queries from the DDL:
   ```bash
   python3 <skill>/scripts/census.py --root <rewrite-root> --ddl docs/contracts/ddl.sql
   ```
   The script emits per-table queries for the standard dirt taxonomy: nulls in "required"
   columns, orphaned foreign keys, encoding anomalies, out-of-range enums, duplicates under
   "unique" intent, timezone-naive datetimes. A human (or a granted read-only connection) runs
   them against prod-shaped data; results land in `census.md` with counts and scrubbed samples.
2. **Mapping & transforms.** `mapping.md` defines old→new schema mapping and an explicit policy
   per dirty class found: repair, quarantine, or drop-with-log. **Policies are ASK items until a
   human ratifies them** — data destruction is never a generator decision.
3. **Reconciliation as acceptance.** Migration WOs (cut in P8) pass only when reconciliation
   checks do: row counts, per-column checksums, stratified sampled field-level diffs between
   source and target. Write these as concrete queries in `reconciliation.sql`. The twin-boot
   harness runs both schemas locally, so census/transform/reconciliation are inner-loop
   operations, not environment requests.
4. **Rehearsal and cutover.** Document (don't schedule): a full dry run against a production
   snapshot is a gated milestone; cutover sequence and rollback plan are workspace documents
   owned by humans.

## Degraded mode

No data access: census queries are still generated and shipped (they're the request you're
making of the human), `mapping.md` is drafted from DDL alone with per-class policies all ASK,
and `rebuild.json.evidence.data_census: inactive`. Migration WOs get elevated risk scores.
