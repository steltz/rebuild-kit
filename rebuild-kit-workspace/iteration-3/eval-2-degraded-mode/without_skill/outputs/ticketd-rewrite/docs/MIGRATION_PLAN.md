# Cutover plan (draft — needs real evidence before execution)

This is a sketch, not a runbook — we don't have production access yet, so
none of the timing/verification steps below have been rehearsed.

## Pre-conditions before attempting cutover

- [ ] Production DB access (expected in a few weeks per handover).
- [ ] Access logs covering at least one full traffic cycle, to answer the
      items in `OPEN_QUESTIONS.md` (especially #1, #2, #4 — behavior quirks
      that affect whether cutover is safe).
- [ ] Confirmation of real SMTP endpoint/credentials for production (legacy
      used `smtp.internal:25` with no auth — confirm whether that's still
      accurate).
- [ ] Confirmation of notification volume, to validate the outbox-poller
      design in `DESIGN.md` is adequate (or needs to move to a real queue
      first).

## Steps (draft)

1. Stand up Postgres, run `alembic upgrade head` against it (schema is in
   `migrations/versions/0001_initial.py`).
2. Run `scripts/migrate_from_sqlite.py <path-to-ticketd.sqlite3>` against a
   copy of the production SQLite file (read-only — never point it at the
   live file while the legacy app is running) to backfill `tickets` and
   `users`. `reset_tokens` intentionally not migrated (see `DESIGN.md`).
3. Run the rewrite in parallel with the legacy app, pointed at the migrated
   Postgres DB, without cutting over traffic. Compare `GET /api/tickets`
   output between both for a sample window (needs the two services to share
   a DB, or a read-only replica of the legacy SQLite kept in sync — TBD once
   we know what production deployment actually looks like).
4. Cut over reads first (`GET` routes), then writes, then auth/reset flow
   last (highest blast radius if something's wrong with the token change).
5. Decommission legacy Flask app once a full rate-limit window (1 hour) plus
   a full reset-token window (30 min) has passed with no errors and no
   support tickets referencing broken resets.

## Rollback

Legacy app + SQLite file stay untouched and deployable until step 5. Nothing
in this plan deletes or mutates the legacy database.
