# Data Census

Tables: 3 · queries generated from `docs/contracts/ddl.sql`

**STATUS: UNRUN.** No production database access is available this run — see
`rebuild.json.evidence.data_census = inactive` and `docs/problem-brief.md` OQ-INTAKE-01. The 25
queries in `census-queries.sql` are the concrete request this workspace makes of a human once
read-only access is granted (expected "in a few weeks" per the task owner). Every row below is
blank by construction, not by oversight — filling them in is P6's re-run in spec-patch mode, not
a P8/M0 blocker for code that has no data dependency yet.

| # | probe | count | scrubbed sample | policy (ASK until ratified) |
|---|---|---|---|---|
| 1 | nulls in required column tickets.id | UNRUN | UNRUN | ASK |
| 2 | nulls in required column tickets.title | UNRUN | UNRUN | ASK |
| 3 | encoding anomalies / control chars in tickets.title | UNRUN | UNRUN | ASK |
| 4 | nulls in required column tickets.slug | UNRUN | UNRUN | ASK |
| 5 | encoding anomalies / control chars in tickets.slug | UNRUN | UNRUN | ASK |
| 6 | encoding anomalies / control chars in tickets.priority | UNRUN | UNRUN | ASK |
| 7 | nulls in required column tickets.status | UNRUN | UNRUN | ASK |
| 8 | encoding anomalies / control chars in tickets.status | UNRUN | UNRUN | ASK |
| 9 | nulls in required column tickets.created_at | UNRUN | UNRUN | ASK |
| 10 | timezone-naive / out-of-range datetimes in tickets.created_at | UNRUN | UNRUN | ASK |
| 11 | timezone-naive / out-of-range datetimes in tickets.closed_at | UNRUN | UNRUN | ASK |
| 12 | orphaned FK tickets.assignee_id → users.id | UNRUN | UNRUN | ASK |
| 13 | out-of-range enum values in tickets.priority | UNRUN | UNRUN | ASK |
| 14 | out-of-range enum values in tickets.status | UNRUN | UNRUN | ASK |
| 15 | nulls in required column users.id | UNRUN | UNRUN | ASK |
| 16 | nulls in required column users.email | UNRUN | UNRUN | ASK |
| 17 | encoding anomalies / control chars in users.email | UNRUN | UNRUN | ASK |
| 18 | nulls in required column users.name | UNRUN | UNRUN | ASK |
| 19 | encoding anomalies / control chars in users.name | UNRUN | UNRUN | ASK |
| 20 | duplicates under unique intent users(email) | UNRUN | UNRUN | ASK |
| 21 | nulls in required column reset_tokens.email | UNRUN | UNRUN | ASK |
| 22 | encoding anomalies / control chars in reset_tokens.email | UNRUN | UNRUN | ASK |
| 23 | nulls in required column reset_tokens.token | UNRUN | UNRUN | ASK |
| 24 | encoding anomalies / control chars in reset_tokens.token | UNRUN | UNRUN | ASK |
| 25 | nulls in required column reset_tokens.created_ts | UNRUN | UNRUN | ASK |

Two probes worth flagging by inspection even before real data (structural, not data-dependent):
- **#12 (orphaned FK tickets.assignee_id → users.id)**: given no route in the legacy app ever
  writes `assignee_id` or `users` (`docs/open-questions.md#OQ-004`), this count is expected to
  be either 0 or the entire non-null population if some out-of-band process populated it — a
  strong signal either way about whether OQ-004 reading A or B is correct once real data exists.
- **#20 (duplicate emails in users)**: schema declares `UNIQUE` on `users.email`
  (`legacy/db/schema.sql:14`), so violations should be structurally impossible under SQLite's
  constraint enforcement — a nonzero count here would indicate the constraint was bypassed
  (bulk-loaded, ALTER'd around) rather than a real dirty-data class.

<!-- Policies per dirty class: repair | quarantine | drop-with-log — ASK items until a human ratifies (see phases/P6-data-census.md). -->
