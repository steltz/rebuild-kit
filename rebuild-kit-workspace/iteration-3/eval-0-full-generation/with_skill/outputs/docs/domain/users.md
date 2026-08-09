# Entity: User

Table: `users` (`ticketd/db/schema.sql:12-16`). **No route in the entire application reads,
writes, or references this table.** It exists in the schema (`id`, `email UNIQUE NOT NULL`, `name
NOT NULL`) and is the FK target of `tickets.assignee_id` (`schema.sql:7`), but:

- No route creates a user.
- No route lists, reads, or authenticates against users.
- No route sets `tickets.assignee_id`.
- The reset-token flow (`docs/domain/reset_token.md`) takes a free-text `email` field entirely
  decoupled from this table — it never looks up or validates against `users`.

## Disposition

This is not evidenced as a *currently used* entity — it's schema-only. It is **not** proposed for
`do-not-port.md` (that register is for code/routes with zero references; this is a *table*, and
dropping a table is a data-model decision, not a dead-code cleanup — a real production database
could have populated `users` rows even though no *code path in this snapshot* touches them, and
losing that data by omission would be a much worse mistake than keeping an unused table
definition). Recorded here as: **carry the `users` table forward in the Postgres DDL (P5), but do
not build any application logic around it** unless a work order says otherwise — this is a
data-census question (P6: does real data exist in this table?) as much as a code question, and it
could not be answered from the evidence available (no production database was supplied — see
`rebuild.json.evidence.data_census: inactive`).

If P6's census (once real data is available) shows `users` is genuinely empty/unused in
production, this becomes a much stronger do-not-port candidate; if it has real rows, the
assignee/ownership feature this table implies (never built, or built and abandoned before this
snapshot) is a legitimate scope question for a human, not something this rewrite should decide
unilaterally either way.
