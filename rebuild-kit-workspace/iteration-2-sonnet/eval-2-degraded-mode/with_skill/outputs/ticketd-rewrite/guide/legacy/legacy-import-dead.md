# Legacy Import (dead) (how it works today)

`legacy/app/legacy_import.py`, 7 lines, one function (`import_spreadsheet`), a one-off importer
from the 2019 spreadsheet-to-database migration. Its own docstring says it plainly: "Nothing
imports this module." A search of the entire codebase confirms it — zero inbound imports, zero
route registrations. This is the one piece of ticketd that DOES meet the evidence bar for
do-not-port (`docs/do-not-port.md#DNP-001`): not because a comment says so, but because static
evidence independently confirms it. Contrast with `admin-export.md`'s CSV route, which has a
similar "probably unused" comment but doesn't meet the same bar (it's still a registered,
reachable route) — the difference between those two is exactly what the do-not-port evidence
threshold is for.
