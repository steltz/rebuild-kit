# Rehearsal & Cutover — human-owned plan (documented, not scheduled)

Gated milestone M3 (`backlog.md`). Nothing here executes without human sign-off.

## Rehearsal (gate for WO-008)

1. Obtain a production snapshot of `db/ticketd.sqlite3` (needs the access requested in
   `docs/problem-brief.md` intake q5; PII scrub approval covers emails in `users` and
   `reset_tokens`).
2. Run the census (`census-queries.sql`) against the snapshot; ratify every ASK policy in
   `mapping.md` against real counts.
3. Run the migration loader (WO-007) against the snapshot; run `reconciliation.sql`; all
   expects green.
4. Full L3 regression: twin-boot with the migrated snapshot as the modern seed, entire
   T2 suite + expected divergences.

## Cutover sequence (proposed; ratify at the M3 gate)

1. Announce freeze; stop legacy writes (stop the Flask process — there is no other writer).
2. Final incremental migrate + reconciliation (minutes; the DB is small).
3. `reset_tokens` intentionally starts empty (mapping.md policy — in-flight resets fail
   with the standard 403; users re-request).
4. Switch `svc-ui` (or the fronting proxy) to the FastAPI service. The UI is unchanged
   (PB-005) — the switch is a base-URL/port change only.
5. Smoke: run the T2-core replay set read-only subset against prod-modern.

## Rollback

Legacy process + SQLite file remain untouched by cutover; rollback = point the proxy back.
Tickets created during the modern window would be lost on rollback — hold rollback decision
to within a short observation window, or export-and-replay them (`POST /api/tickets` is
re-drivable). Decide the window length at the gate.
