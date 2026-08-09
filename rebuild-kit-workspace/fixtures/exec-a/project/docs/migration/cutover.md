# Rehearsal & cutover — documented, not scheduled

Per P6: this is a plan for humans to execute and gate, not something the executor runs
unattended. ticketd is small (3 tables, no evidence of large data volume — OIQ-5 unresolved)
and has a single known consumer (`svc-ui`), which keeps this simpler than most migrations.

## Rehearsal (gated milestone, human-scheduled)

1. Snapshot production SQLite data (or the nearest available prod-shaped copy).
2. Run `docs/migration/census-queries.sql` against it for real; fill `census.md`.
3. Ratify the ASK policies in `mapping.md` (slug-collision backfill, orphaned FK policy,
   reset_tokens carry-forward-or-drop, OQ-003 timestamp representation) based on real counts —
   a zero-count census answers most of these trivially; a nonzero one needs an actual decision.
4. Run the migration transform against the snapshot into a scratch Postgres instance.
5. Run every query in `reconciliation.sql` against snapshot vs. scratch-Postgres; all must
   pass (R4/R5 in particular, since those are the ones a stale mental model could get wrong).
6. Boot `modern/` against the scratch Postgres instance and run the full L3 replay suite
   (`verification/harness/diff-run.sh` for every WO's replay set) — this is the actual
   Milestone-close gate, not just the migration's own reconciliation.

## Cutover sequence (draft — human-owned, not executor-owned)

1. Freeze writes to legacy (maintenance window — duration driven by how long the real
   migration transform takes against real data volume, unknown until rehearsal).
2. Final incremental migration run (or full run if volume is small enough that a full
   re-migration during the freeze window is cheaper than incremental delta logic — TBD by
   rehearsal timing).
3. Reconciliation queries, one more time, against the real cutover data.
4. Flip `svc-ui`'s backend target to `modern/`.
5. Keep `legacy/`'s data store available read-only for a rollback window (length: human
   decision, not specified here).

## Rollback plan (draft)

If reconciliation fails at cutover or `modern/` misbehaves post-flip: flip `svc-ui` back to
legacy (its data store was untouched — legacy stops taking writes at step 1 above, so as long
as no *new* legacy-side data was created after the freeze, rollback is a pure traffic-routing
change, not a data operation). This assumes the freeze in step 1 actually holds; if any
write path bypasses it (unknown — not evidenced either way), rollback gets more complex and
that gap should be closed before cutover, not discovered during it.

## What's deliberately not decided here
Freeze-window duration, whether migration runs full or incremental, rollback-window length,
and the actual cutover date are human/operational decisions with no evidence basis in this
codebase to derive them from. Recorded as gaps, not guessed.
