# Migration mapping — SQLite (legacy) → PostgreSQL (modern)

Drafted from DDL alone (`docs/contracts/ddl.sql`) — no production data access was granted, so
every dirty-data policy below is `ASK` per P6 degraded mode (`rebuild.json.evidence.data_census:
inactive`). **Data destruction is never a generator decision** — none of these policies are
ratified; they are the menu a human picks from once `census.md`'s counts come back.

## tickets

| Legacy column | Type | Modern column | Type | Change | Rationale |
|---|---|---|---|---|---|
| `id` | INTEGER PK | `id` | `BIGINT GENERATED ALWAYS AS IDENTITY PK` | mechanical | Postgres idiom |
| `title` | TEXT NOT NULL | `title` | `TEXT NOT NULL` | none | FIXED |
| `slug` | TEXT NOT NULL | `slug` | `TEXT NOT NULL` | **+ `UNIQUE` constraint** | PB-003/WO-005 — the outcome (unique) is ratified by the brief; **policy for pre-existing collisions is ASK** (census #26/27 needed first: reject the migration and force manual retitle? auto-suffix existing dupes at migration time? See OQ-001 — the resolution mechanism for NEW collisions and the backfill policy for EXISTING ones are related but distinct decisions; both blocked on the same OQ-001 ruling plus real counts). |
| `priority` | TEXT CHECK | `priority` | Postgres `CHECK` (or native `ENUM` — FREE) | none behaviorally | FIXED outcome, FREE mechanism |
| `status` | TEXT NOT NULL CHECK | `status` | same shape | none | FIXED |
| `assignee_id` | INTEGER REFERENCES users(id), **unenforced** (OQ-005) | `assignee_id` | `BIGINT REFERENCES users(id)`, **enforced** (Postgres FKs are on by default) | tightening | See OQ-005 — Postgres will enforce this by default where SQLite silently didn't. Census #12 (orphaned FKs) must come back **zero**, or this migration will fail on constraint creation and orphans need a policy (nullify orphaned refs? quarantine those ticket rows?) — ASK, blocked on real data. |
| `created_at` | DATETIME (naive local) | `created_at` | `TIMESTAMPTZ` | **ASK — OQ-003** | If OQ-003 rules "bug," backfill needs a policy for interpreting existing naive timestamps' offset (assume a fixed org timezone? UTC?) — ASK either way. If ruled "intentional," modern stores naive too (`TIMESTAMP` without tz) and this mapping reverts. |
| `closed_at` | DATETIME, nullable | `closed_at` | `TIMESTAMPTZ`, nullable | same as above | OQ-003 |

## users

| Legacy column | Type | Modern column | Type | Change | Rationale |
|---|---|---|---|---|---|
| `id` | INTEGER PK | `id` | `BIGINT GENERATED ALWAYS AS IDENTITY PK` | mechanical | |
| `email` | TEXT NOT NULL UNIQUE | `email` | `TEXT NOT NULL UNIQUE` | none | FIXED — already the one column with real uniqueness enforcement in legacy |
| `name` | TEXT NOT NULL | `name` | `TEXT NOT NULL` | none | FIXED |

**Open question independent of column mapping**: OQ-007 — no route in the legacy tree ever
populates `users`. Before migrating this table's *data* (as opposed to its *shape*), someone
needs to confirm where the source rows actually come from. If the answer is "nowhere, it's
empty/vestigial," the migration for this table is trivial (empty table, same shape). If rows
exist and matter, the migration needs to know their source system.

## reset_tokens — full redesign, not a column-by-column mapping (PB-002, WO-003)

The legacy table (`email TEXT, token TEXT, created_ts REAL` — no PK, no index, no expiry
column) is being redesigned outright, not translated 1:1. Target shape (mechanism is `FREE`
per `modern/CLAUDE.md`; this is a reasonable default, not a ruling):

```sql
CREATE TABLE reset_tokens (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email TEXT NOT NULL,
    token_hash TEXT NOT NULL,        -- SHA-256 (or similar) of a secrets.token_urlsafe() value;
                                       -- the RAW token is never stored, only its hash (PB-002)
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,  -- DB-level expiry in addition to app-level checks
    consumed_at TIMESTAMPTZ           -- nullable; set instead of (or in addition to) deleting,
                                       -- FREE choice -- legacy deletes on confirm (single-use,
                                       -- FIXED outcome), whether modern deletes or soft-marks
                                       -- is an implementation detail as long as a consumed or
                                       -- expired token behaves identically to legacy's "gone"
);
CREATE UNIQUE INDEX ON reset_tokens (token_hash);
CREATE INDEX ON reset_tokens (email, created_at);  -- the rate-limit query's access pattern
```

**Migration policy for existing `reset_tokens` rows: ASK.** Given the security framing of
PB-002 (MD5-derived, plaintext-equivalent tokens), the safest default is **drop-with-log**
(any outstanding reset tokens are invalidated by the migration; users who wanted a reset simply
request a new one post-cutover) rather than attempting to re-hash and carry forward
plaintext-derivable legacy tokens into the new hashed scheme. This is a recommendation, not a
ratified policy — a human must confirm, especially re: any user-visible impact ("your
in-flight password reset link will stop working after the cutover").

## Reconciliation

See `reconciliation.sql` for the concrete queries. Row-count and per-column checksum parity are
required for `tickets` and `users` (straight translation); `reset_tokens` reconciliation is
necessarily different (it's a redesign, not a translation) — reconciliation there checks
*structural* invariants (every non-expired legacy token has *some* corresponding modern row
pre-cutover, if the drop-with-log policy above is NOT chosen) rather than field equality.
