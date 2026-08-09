# Entity: User

Table `users` (`ticketd/db/schema.sql:12-16`).

| field | type | notes |
|---|---|---|
| id | INTEGER PK | referenced by `tickets.assignee_id` FK (`schema.sql:7`) |
| email | TEXT NOT NULL UNIQUE | only unique constraint in the schema |
| name | TEXT NOT NULL | |

**No application code reads or writes this table.** Verified: `app/server.py` contains no
reference to `users`; the reset flow keys on raw email strings without checking registration
(`app/server.py:82-92`). There is no password column anywhere — which makes the
"password-reset" flow's ultimate effect unobservable from this repo (OQ-006).

Port decision: the table is part of the schema and referenced by an FK, so it migrates
as-is (WO-007). No behavior WO touches it.
