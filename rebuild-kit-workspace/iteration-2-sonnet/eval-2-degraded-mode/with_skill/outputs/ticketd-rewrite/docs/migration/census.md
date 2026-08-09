# Data Census

<!-- DEGRADED MODE: rebuild.json.evidence.data_census = inactive. No production database access
     was granted this run ("maybe in a few weeks" per intake) — every count/sample column below
     is blank because there is no prod-shaped data to query yet. The queries themselves ARE the
     deliverable of this phase in degraded mode: they're the concrete ask of the human once
     access exists. Running them against the empty local dev sqlite (legacy/db/ticketd.sqlite3,
     if/when seeded) would tell us about a synthetic seed, not production dirt, so that was not
     done here — it would produce a false sense of completion. Revisit via spec-patch once DB
     access lands: run docs/migration/census-queries.sql, fill this table, then ratify mapping.md
     policies (currently all ASK, per P6). -->

Tables: 3 · queries generated from `docs/contracts/ddl.sql`

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

<!-- Policies per dirty class: repair | quarantine | drop-with-log — ASK items until a human ratifies (see phases/P6-data-census.md). -->
