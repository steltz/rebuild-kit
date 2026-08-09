# Entity: User

## Fields
(source: `legacy/db/schema.sql:12-16` only — no application code references this table)

| Field | Type | Constraint | Notes |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY | |
| `email` | TEXT | NOT NULL, UNIQUE | |
| `name` | TEXT | NOT NULL | |

## Lifecycle

None observable — no route in `legacy/app/server.py` creates, reads, updates, or deletes a
`users` row. The only reference to `users` anywhere outside the DDL is the FK declaration on
`tickets.assignee_id` (legacy/db/schema.sql:7).

## Status

Schema-only entity. See `docs/open-questions.md#OQ-004` for the two competing readings (planned-
but-never-shipped vs. shipped-elsewhere-not-in-this-handover). No WO in this backlog implements
user-facing behavior for this entity; the rewrite's schema carries the table shape forward as a
FREE structural choice so a future assignment feature isn't blocked, but no behavior is
characterized or tested against it.
