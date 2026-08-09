# Entity: User

## Fields (`legacy/db/schema.sql:12-16`)

| Field | Type | Constraint |
|---|---|---|
| `id` | INTEGER | PRIMARY KEY |
| `email` | TEXT | NOT NULL, UNIQUE |
| `name` | TEXT | NOT NULL |

## Status: dead in application code

`users` is declared in the DDL and referenced by `tickets.assignee_id`, but **no route in
`legacy/app/server.py` ever creates, reads, updates, or deletes a `users` row**, and no route
joins `tickets` to `users`. The password-reset flow takes a raw `email` string and never checks
it against this table (see `docs/domain/reset-token.md`).

Two readings, both plausible, neither evidenced enough to pick without a human:

- **Reading A:** `users` is genuinely vestigial — scaffolding for an auth/assignment feature that
  was planned in the schema but never built out in the route layer. Nothing depends on it; safe
  to treat as a stub in the rewrite until a real feature needs it.
- **Reading B:** `users` is populated and read by something outside this repo (an admin script,
  a BI job, a manual SQL console workflow) that this handover didn't include. Dropping or
  reshaping it in the rewrite would silently break that unseen consumer.

Filed as `docs/open-questions.md#OQ-003` — blocks no WO directly (nothing in this repo touches
the table) but flags gate review for the migration WO that will need to decide whether `users`
carries forward at all, and in what shape.
