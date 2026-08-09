# Migration Mapping — SQLite (legacy) → PostgreSQL (target)

Drafted from `docs/contracts/ddl.sql` alone (no production data available this run — see
`census.md`). All policies below are **ASK until a human ratifies them** (schema.md: "data
destruction is never a generator decision"). This is a structural mapping proposal, not an
executed migration.

## tickets

| legacy column | legacy type | target column | target type | notes |
|---|---|---|---|---|
| id | INTEGER PK | id | BIGINT / IDENTITY PK | Postgres `GENERATED ALWAYS AS IDENTITY` recommended (FREE — mechanism, not observable behavior). |
| title | TEXT NOT NULL | title | TEXT NOT NULL | Direct copy. |
| slug | TEXT NOT NULL | slug | TEXT NOT NULL | Direct copy — **do not add a UNIQUE constraint** without a ruling; legacy data may already contain collisions (docs/domain/ticket.md) and a naive migration-time UNIQUE would fail load. Policy: ASK (repair by disambiguating vs. quarantine vs. accept-as-is — see below). |
| priority | TEXT CHECK | priority | TEXT CHECK or Postgres ENUM | FREE mechanism; CHECK domain (low/med/high) is FIXED behavior. |
| status | TEXT CHECK | status | TEXT CHECK or Postgres ENUM | Same as priority. |
| assignee_id | INTEGER REFERENCES users(id) | assignee_id | BIGINT REFERENCES users(id) | Carried forward as schema shape only — no behavior exists to migrate (OQ-004). Policy for orphaned FKs: ASK, pending census #12. |
| created_at | DATETIME (naive local) | created_at | TIMESTAMP or TIMESTAMPTZ | **ASK**: legacy values are naive local server time with no recorded offset (legacy/app/server.py:52). Converting to `TIMESTAMPTZ` requires assuming a source timezone — which one is unconfirmed (no ops documentation available). Candidate policy: migrate as `TIMESTAMP` (no tz) verbatim, preserving legacy ambiguity rather than guessing an offset; ratify before M0's migration WO closes. |
| closed_at | DATETIME, nullable | closed_at | TIMESTAMP or TIMESTAMPTZ, nullable | Same ASK as created_at. |

## users

| legacy column | legacy type | target column | target type | notes |
|---|---|---|---|---|
| id | INTEGER PK | id | BIGINT / IDENTITY PK | Direct. |
| email | TEXT NOT NULL UNIQUE | email | TEXT NOT NULL UNIQUE | Direct — UNIQUE already enforced in source, expected safe to carry forward (census #20 should confirm zero violations). |
| name | TEXT NOT NULL | name | TEXT NOT NULL | Direct. |

Table has zero application behavior (OQ-004) — migrated structurally for forward-compatibility
only; not exercised by any WO's acceptance criteria.

## reset_tokens

| legacy column | legacy type | target column | target type | notes |
|---|---|---|---|---|
| email | TEXT NOT NULL | email | TEXT NOT NULL | Direct. |
| token | TEXT NOT NULL (MD5 hex, no UNIQUE) | token | TEXT NOT NULL UNIQUE (target) | **Not a direct copy** — PB-002 (WO-003) replaces the token generation mechanism going forward. Historical MD5 tokens in flight at cutover are, by design, short-lived (30-min window, `RESET_WINDOW_MIN`) — the migration policy is DROP, not carry-forward: any reset_tokens row that survives to migration is already expired or about to be, and per the non-disclosure invariant (docs/domain/reset_token.md) an expired token must be indistinguishable from an invalid one regardless of which generator made it. Recommended policy: **drop-with-log** all reset_tokens rows at migration time rather than porting live tokens across a token-format change. This is a migration-execution decision, not a defect-fix decision, but it touches PB-002-adjacent data — flag for explicit human sign-off at the cutover gate rather than silently deciding. |
| created_ts | REAL (Unix epoch) | issued_at | TIMESTAMPTZ | Only relevant if the drop-with-log policy above is overridden; otherwise moot. |

No structural PK exists on `reset_tokens` in legacy (`legacy/db/schema.sql:18-22`) — target
schema should add one (FREE, Postgres wants a real PK); this is a mechanism choice, not a
migrated-data concern given the drop-with-log recommendation above.

## Rehearsal & cutover (documented, not scheduled)

Per P6 procedure, this section documents the plan; scheduling and execution are human-owned
gated milestones (`ledger.json` milestone gates), not generator actions.

1. **Rehearsal**: run the full migration script (once written, in a WO) against a restored
   production snapshot in a non-production environment; run `reconciliation.sql` against the
   result; a human reviews the report before any cutover date is set.
2. **Cutover sequence** (draft, ratify before use): (a) freeze legacy writes, (b) run migration
   script, (c) run reconciliation, (d) human sign-off gate, (e) flip traffic to `modern/`,
   (f) keep the legacy SQLite file as a cold backup for a human-decided retention period.
3. **Rollback plan**: since legacy is read-only evidence in this workspace and its production
   counterpart is a separate live system, rollback means re-pointing traffic back to the legacy
   deployment — not reversing the migration script. No destructive operation against the legacy
   production DB is ever part of this plan.

All of the above is blocked on `docs/problem-brief.md` OQ-INTAKE-01 (no DB access yet) and is
therefore not scheduled to any milestone in `backlog.md`/`ledger.json` — it is recorded here as
the plan to execute once access lands, consistent with degraded-mode rules in `rebuild.json`.
