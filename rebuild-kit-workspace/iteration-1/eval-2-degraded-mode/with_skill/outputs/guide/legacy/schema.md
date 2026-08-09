# schema (how the data actually sits)

Three tables (`ticketd/db/schema.sql`, mirrored verbatim in docs/contracts/ddl.sql):

- **tickets** — the CHECKs on priority/status are the only real vocabulary enforcement in
  the system (the app's own validation is partial). Timestamps are naive local-time ISO
  *strings*; the newest-first list ordering is actually a string sort that happens to work.
- **users** — declared, constrained (UNIQUE email), and **touched by no code whatsoever**.
  It exists only as the target of `tickets.assignee_id`'s foreign key.
- **reset_tokens** — no PK, no index, no constraints beyond NOT NULL, plaintext MD5 tokens
  (PB-002), unix-float timestamps, and no cleanup path: expired rows accumulate forever.

**The trap for migration:** SQLite never enforces that assignee_id FK — the app never issues
`PRAGMA foreign_keys=ON` (server.py:20-24) — so seven years of production writes may contain
dangling assignees that Postgres will refuse. That, the true timezone of the naive
timestamps, and possible pre-CHECK vocabulary strays are exactly what the census queries
(docs/migration/census-queries.sql) are waiting to measure the day we get DB access
(OQ-INT-2). Until then every migration policy is an explicit ASK in
docs/migration/mapping.md — nothing gets repaired, dropped, or quarantined without the
owner's signature.
