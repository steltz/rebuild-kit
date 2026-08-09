# Data Census

Tables: 3 · queries generated from `docs/contracts/ddl.sql`

**Degraded mode (`rebuild.json.evidence.data_census: inactive`)**: no production database or
snapshot was supplied to this generator run — only the DDL (`ticketd/db/schema.sql`). No SQLite
data file exists anywhere in the evidence either (`find . -iname "*.sqlite*"` in the legacy tree
returns nothing). Every row below is therefore unfilled by design, not by omission — this table
*is* the request to a human: run `census-queries.sql` (plus the manual query #26 added below,
specific to PB-003) against real data, paste counts/scrubbed samples here, then ratify a policy
per dirty class before any migration work order is implemented against it. All 26 rows carry
elevated migration-WO risk until this happens (see `docs/features/WO-005-data-migration.md`'s
risk score).

| # | probe | count | scrubbed sample | policy (ASK until ratified) |
|---|---|---|---|---|
| 1 | nulls in required column tickets.id | | | ASK |
| 2 | nulls in required column tickets.title | | | ASK |
| 3 | encoding anomalies / control chars in tickets.title | | | ASK |
| 4 | nulls in required column tickets.slug | | | ASK |
| 5 | encoding anomalies / control chars in tickets.slug | | | ASK |
| 6 | encoding anomalies / control chars in tickets.priority | | | ASK |
| 7 | nulls in required column tickets.status | | | ASK |
| 8 | encoding anomalies / control chars in tickets.status | | | ASK |
| 9 | nulls in required column tickets.created_at | | | ASK |
| 10 | timezone-naive / out-of-range datetimes in tickets.created_at | | | ASK |
| 11 | timezone-naive / out-of-range datetimes in tickets.closed_at | | | ASK |
| 12 | orphaned FK tickets.assignee_id → users.id | | | ASK |
| 13 | out-of-range enum values in tickets.priority | | | ASK |
| 14 | out-of-range enum values in tickets.status | | | ASK |
| 15 | nulls in required column users.id | | | ASK |
| 16 | nulls in required column users.email | | | ASK |
| 17 | encoding anomalies / control chars in users.email | | | ASK |
| 18 | nulls in required column users.name | | | ASK |
| 19 | encoding anomalies / control chars in users.name | | | ASK |
| 20 | duplicates under unique intent users(email) | | | ASK |
| 21 | nulls in required column reset_tokens.email | | | ASK |
| 22 | encoding anomalies / control chars in reset_tokens.email | | | ASK |
| 23 | nulls in required column reset_tokens.token | | | ASK |
| 24 | encoding anomalies / control chars in reset_tokens.token | | | ASK |
| 25 | nulls in required column reset_tokens.created_ts | | | ASK |
| 26 | *(manual, not script-generated)* duplicate `tickets.slug` values — direct evidence for PB-003/OQ-001; the census script only checks DB-declared unique constraints, and `slug` has none, so this probe has to be added by hand. Query: `SELECT slug, COUNT(*) FROM tickets GROUP BY slug HAVING COUNT(*) > 1;` (appended to `census-queries.sql`). | | | Not a dirty-data repair/quarantine/drop decision like the others — this is the actual evidence base for whichever OQ-001 collision-handling mechanism gets ruled (append-suffix, reject-on-create, id-only-identity, etc.). Run it before that ruling, not after — the real collision rate should inform the choice. |

<!-- Policies per dirty class: repair | quarantine | drop-with-log — ASK items until a human ratifies (see phases/P6-data-census.md). -->
