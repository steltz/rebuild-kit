# Entity: User

## Fields (from `ticketd-nohistory/db/schema.sql:12-16`)

| Field | Type | Constraint |
|---|---|---|
| `id` | INTEGER | PRIMARY KEY |
| `email` | TEXT | NOT NULL, UNIQUE |
| `name` | TEXT | NOT NULL |

## Status: unused by any code path

**No route, module, or SQL statement in the entire legacy tree reads, writes, or joins against
`users`.** `tickets.assignee_id` references it by foreign key but is itself never set or read
(see `docs/domain/ticket.md`). Confirmed by grepping the whole tree for `users`/`assignee`: the
only hits are the two DDL lines that define the table and the FK.

This is genuinely ambiguous, not a confident dead-code call the way `app/legacy_import.py` is
(that module at least *exists* as inert code with a self-describing docstring; `users` is a table
with zero corroborating application code either way). Filed as **OQ-005** in
`docs/open-questions.md`. Possible readings:
- **A**: assignment was planned in the original design but never shipped — the table is inert
  schema debt, safe to drop or carry forward empty.
  Evidence: no code references it at all, anywhere.
- **B**: the table is populated and used by something outside this repo (another service, a
  script, a manual process) pointed at the same SQLite file — this repo just doesn't show it.
  Evidence: none found, but absence-of-evidence isn't proof here given no runtime observability
  exists yet (PB-003) and no one confirmed "nothing else touches this database."

**Do not disposition `users`/`assignee_id` (port, drop, or repurpose) without a ruling on OQ-005.**
If real production data exists in this table once DB access lands (P6), that's decisive evidence
either way and should resolve the OQ immediately.
