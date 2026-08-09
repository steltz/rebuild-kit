# ticketd
Internal ticket tracker. `python -m app.server`. Schema in db/schema.sql.

## Rewrite in progress (FastAPI + Postgres)

This app is being rewritten to fix three known problems: synchronous
SMTP-in-request (the June outage), MD5 password-reset tokens, and slug
collisions. The full workspace for that rewrite — design spec,
implementation plan, and verification plan — lives under
`docs/superpowers/`:

- `docs/superpowers/specs/2026-08-09-ticketd-rewrite-design.md` — start
  here. Read the "Open Questions" section before implementing anything.
- `docs/superpowers/plans/2026-08-09-ticketd-rewrite.md` — task-by-task
  implementation plan (TDD, one task per file/endpoint group).
- `docs/superpowers/verification/2026-08-09-ticketd-rewrite-verification.md`
  — how to stand up a test Postgres instance and confirm the rewrite is
  correct; also records what's already been validated vs. still open.

The current Flask/SQLite code in `app/` and `db/schema.sql` stays in place
and authoritative until the rewrite is implemented and cut over — nothing
in this workspace has modified it.
