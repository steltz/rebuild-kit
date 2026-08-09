# Entity: User

## Fields (from `legacy/db/schema.sql:12-16`)

| Field | Type | Notes |
|---|---|---|
| `id` | `INTEGER PRIMARY KEY` | |
| `email` | `TEXT NOT NULL UNIQUE` | only field with a uniqueness constraint anywhere in the schema |
| `name` | `TEXT NOT NULL` | |

## Status: defined but unused

No route in `legacy/app/server.py` creates, reads, updates, or deletes a `users` row. The only
reference to `users` anywhere in the code is the FK declaration on `tickets.assignee_id`
(`db/schema.sql:7`), which nothing ever populates. There is no login/session system, no auth
beyond the reset-token flow (which operates purely on a free-text `email` string, not a `users`
row — see `docs/domain/reset_token.md`).

## Scope call for this rewrite

This is a static-evidence finding, not a problem-brief entry — the requester did not mention
users/auth/assignment as a known problem, and no testimony exists either way. Default disposition:
`users` and ticket assignment are **out of behavioral scope** for the work orders in this first
pass (there is no legacy behavior to preserve, repair, or leave alone — there is no behavior at
all). If assignment is actually a wanted feature, that is new functionality, not a rewrite target,
and belongs in a separate brief entry from a human, not something this pipeline should invent.
Table is still carried into the Postgres DDL (P5) since it's part of the schema footprint, but no
work order in this backlog implements user/assignment behavior.
