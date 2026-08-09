# Data Census

Tables: 3 · queries generated from `docs/contracts/ddl.sql`

**Status: UNRUN.** `rebuild.json.evidence.data_census: inactive` — no production DB access was
granted during generation (this is expected/degraded-mode per `references/phases/P6-data-census.md`:
the queries below are the request being made of a human, not a result). All counts are blank
and every policy is `ASK` by construction. **A human with read-only prod access needs to run
`census-queries.sql` and paste real counts + scrubbed samples here before WO-005 (slug
uniqueness) or WO-003 (reset-token table redesign) can size their actual migration risk.**

Probes 26-28 were added by hand, not by the generator script — `census.py`'s heuristic only
probes columns that already carry a `UNIQUE` constraint in the legacy DDL, and `tickets.slug`
does **not** have one despite being PB-003's entire subject (the bug IS the missing
constraint, so the generic heuristic structurally cannot find it). Probe 26 is the single
highest-priority number in this whole census: it tells WO-005 how many existing collisions a
migration would need to resolve before a `UNIQUE` index becomes addable at all.

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
| 26 | **MANUAL — slug collision groups (PB-003, blocks WO-005)** | | | ASK |
| 27 | **MANUAL — total rows affected by a slug collision** | | | ASK |
| 28 | **MANUAL — duplicate (email, token) pairs in reset_tokens** | | | ASK |

<!-- Policies per dirty class: repair | quarantine | drop-with-log — ASK items until a human ratifies (see phases/P6-data-census.md). -->
