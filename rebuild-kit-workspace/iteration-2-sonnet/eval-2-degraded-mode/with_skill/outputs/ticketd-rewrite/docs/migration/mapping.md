# Schema Mapping — SQLite (legacy) -> PostgreSQL (target)

<!-- P6. Drafted from DDL alone (data_census inactive — see census.md). Every policy below is
     ASK until a human ratifies it against real counts; data destruction is never a generator
     decision. -->

## tickets

| Legacy column | Legacy type | Target column | Target type | Notes / policy |
|---|---|---|---|---|
| `id` | INTEGER PK | `id` | `BIGSERIAL PRIMARY KEY` (FREE — or `INTEGER` if row volume is known to stay small; no evidence either way) | mechanism FREE |
| `title` | TEXT NOT NULL | `title` | `TEXT NOT NULL` | direct |
| `slug` | TEXT NOT NULL | `slug` | `TEXT NOT NULL` | **policy ASK**: add a UNIQUE constraint now (closes OQ-005) or carry the collision-permissive behavior forward? Depends on the OQ-005 ruling, which depends on real data (are there already collisions in prod?) — census query needed once DB access exists (not in the generated set; add `SELECT slug, COUNT(*) FROM tickets GROUP BY slug HAVING COUNT(*)>1` when access lands). |
| `priority` | TEXT CHECK | `priority` | `TEXT NOT NULL DEFAULT 'med' CHECK (priority IN ('low','med','high'))` | **policy ASK**: legacy allows `priority IS NULL` (no NOT NULL constraint) even though the app always supplies a default of `'med'` — census query #13 (out-of-range enum) will show if any NULL/invalid values exist in practice; policy (repair-to-default vs. quarantine) depends on that count. |
| `status` | TEXT NOT NULL CHECK | `status` | `TEXT NOT NULL CHECK (status IN ('open','closed'))` | direct |
| `assignee_id` | INTEGER REFERENCES users(id), unenforced (SQLite FK pragma off) | `assignee_id` | `BIGINT REFERENCES users(id)`, FK enforced by Postgres by default | **policy ASK, blocked by OQ-003**: do not enable FK enforcement until it's known whether `users`/`assignee_id` carries real data — an enforced FK on migration could reject rows that were silently orphaned under SQLite's unenforced FK. Census query #12 (orphaned FK) must run before this constraint is added. |
| `created_at` | DATETIME NOT NULL, naive local time | `created_at` | `TIMESTAMPTZ NOT NULL` | **policy ASK, blocked by OQ-001**: converting naive-local timestamps to UTC on migration requires knowing which timezone the app server ran in — not recorded anywhere in this handover. Do not guess a timezone; ask. |
| `closed_at` | DATETIME, nullable, naive local time | `closed_at` | `TIMESTAMPTZ` nullable | same as `created_at` |

## users

| Legacy column | Target column | Notes |
|---|---|---|
| `id`, `email` (UNIQUE), `name` | unchanged shape | **policy ASK, blocked by OQ-003**: table may be entirely vestigial (zero application code touches it). Migrate as-is (schema only, whatever row count exists) pending that ruling — do NOT drop the table without a human decision, since "no code touches it" is not the same evidence as "no data matters." |

## reset_tokens

| Legacy column | Target column | Notes |
|---|---|---|
| `email`, `token`, `created_ts` (REAL, unix epoch) | `email TEXT NOT NULL`, `token TEXT NOT NULL UNIQUE`, `created_at TIMESTAMPTZ NOT NULL` | **policy ASK**: legacy table has no primary key at all. Target adds `id BIGSERIAL PRIMARY KEY` (FREE, uncontroversial) and a `UNIQUE` constraint on `token` (this one needs a ruling — legacy never enforced it, but nothing in the app logic requires duplicates, so this is a low-risk tightening; still flagged since "tightening a constraint during migration" is exactly the kind of change that should be a conscious yes). Rows are ephemeral (30-minute TTL by application logic) — migrating in-flight (not-yet-expired) tokens at cutover means a user mid-reset gets a working token post-cutover; migrating expired rows is pointless (policy: **drop-with-log** for `created_ts` older than 30 minutes at migration time — proposed, not yet ratified). |

## Cross-cutting

No PB entry or ASK ruling currently sanctions dropping any table or column. Every "should we drop
X" question above is filed to `docs/open-questions.md` and stays a proposal, not a plan, until
ruled.
