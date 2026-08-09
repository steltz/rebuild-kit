# Entity: User (schema-only)

Table `users` (`ticketd/db/schema.sql:12-16`): `id` PK, `email` TEXT NOT NULL UNIQUE,
`name` TEXT NOT NULL.

**No application code reads or writes this table.** Verified against the whole tree: the only
references to `users` are the DDL and the `tickets.assignee_id` FK declaration
(`ticketd/db/schema.sql:7`). There is no login, no user CRUD, no password column, and the
reset flow never checks the email against `users` (`ticketd/app/server.py:80-108`).

Consequences:
- The password-reset flow resets a password that **has no visible storage** in this system —
  either an external system consumes the confirmed email, or the flow is vestigial. This is
  OQ-002 (blocks final disposition of the auth-reset subsystem's purpose, not its behavior).
- Production `users` rows may exist and may be referenced by `tickets.assignee_id` (unenforced
  FK) — migration carries the table as-is; census deferred (OQ-INT-2).

Invariant: `email` uniqueness is DB-enforced (UNIQUE, schema.sql:14). Nothing else is enforced
anywhere.
