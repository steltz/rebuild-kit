# Entity: User

## Fields (cited: `ticketd/db/schema.sql:12-16`)

| Field | Type | Nullable | Notes |
|---|---|---|---|
| `id` | INTEGER PK | no | |
| `email` | TEXT | no (`NOT NULL UNIQUE`) | Only `UNIQUE` constraint anywhere in the schema — notable contrast with `tickets.slug`'s complete absence of one (PB-003). |
| `name` | TEXT | no (`NOT NULL`) | |

## Evidence discipline note

**No route in `app/server.py` reads, writes, creates, or references the `users` table at all.**
It exists only as: (1) the `tickets.assignee_id` FK target, and (2) implicitly, as *who a
reset token's `email` field probably corresponds to* — but `POST /api/auth/reset` never
actually looks up `users`, so a reset can be issued for an email with no matching user row.

This means the entire `users` table's population, and `assignee_id` assignment, happen through
some mechanism **outside this legacy tree** (direct DB writes? an admin tool not in this repo?
unknown). Confirmed via P1 static inventory (zero references) — not inferred, not guessed.
Carried as an open item for the migration workstream (P6) rather than invented: if `users` is
populated externally today, the rewrite's migration plan needs to know where those rows come
from, or the table (and `assignee_id`) may be legacy vestige from a feature that was removed.
See `docs/open-questions.md` OQ-007.

## Lifecycle / invariants

None observable — no code path creates, updates, or deletes a `users` row. Nothing to preserve
behaviorally beyond the schema shape itself, which the migration DDL should retain (PB-005
doesn't apply here since nothing user-facing touches this table, but silently dropping it would
be an unsanctioned decision if it turns out to be populated externally).
