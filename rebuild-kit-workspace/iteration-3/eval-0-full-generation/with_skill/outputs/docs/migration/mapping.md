# Migration Mapping — SQLite (legacy) → Postgres 16 (target)

Drafted from DDL alone (`docs/contracts/ddl.sql`) — no production data was available to this
generator run (`rebuild.json.evidence.data_census: inactive`). Per-dirty-class policies below are
**ASK until a human ratifies them against real census results** (`docs/migration/census.md`) —
data destruction/quarantine is never a generator decision.

## Table: tickets

| legacy column | legacy type | target column | target type | transform | policy for dirt found |
|---|---|---|---|---|---|
| `id` | `INTEGER PRIMARY KEY` (SQLite rowid) | `id` | `BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY` | Direct copy of existing ids (preserve numbering — external references, if any, depend on it); switch generation mechanism for new rows only. | Census #1 (null ids): SQLite `INTEGER PRIMARY KEY` cannot be null by construction — expect 0; if census finds any, that's a census-tooling bug, not real dirt, investigate before trusting the rest of the census. |
| `title` | `TEXT NOT NULL` | `title` | `TEXT NOT NULL` | Direct copy. | Census #2/#3 (nulls/encoding): **ASK** — repair (strip control chars) vs. quarantine (flag row, migrate as-is, fix later) vs. drop-with-log. Given `title` is required at the app layer on every write path, nulls found here would mean either direct DB writes bypassing the app, or app-layer regressions in an earlier version — worth understanding *why* before picking a policy, not just what. |
| `slug` | `TEXT NOT NULL` (not unique) | `slug` | `TEXT NOT NULL` | Direct copy of the value; **whether a uniqueness constraint is added at the target depends entirely on OQ-001's ruling** — do not add a `UNIQUE` constraint speculatively, it would make otherwise-valid legacy data (duplicate slugs, PB-003) fail migration outright. | Census #4/#5 + manual #26 (duplicates): the duplicate-count itself is direct input to OQ-001's ruling, not a "dirty data" problem to fix during migration — see census.md row 26. |
| `priority` | `TEXT CHECK IN (...)` | `priority` | Postgres `CHECK` (keep as TEXT+CHECK, or promote to a native `ENUM` — **FREE**, no behavior depends on the storage mechanism, only on the allowed value set) | Direct copy for values already in `{low,med,high}`. | Census #13 (out-of-range enum): **ASK** — if any row violates the CHECK (possible if it was ever relaxed, or written outside the app), repair-to-nearest vs. quarantine vs. drop-with-log needs a human call; this could also mean a target CHECK that's `NOT VALID` initially, with cleanup as a separate follow-up. |
| `status` | `TEXT CHECK IN ('open','closed')` | `status` | Same treatment as `priority` | Direct copy. | Census #14: same ASK shape as priority; lower risk since only two values and heavily exercised by every write path (`server.py`'s only status-setting code is at insert (`'open'`, hardcoded) and close (`'closed'`, hardcoded) — no other value has ever been written by the app). |
| `assignee_id` | `INTEGER REFERENCES users(id)` (unenforced — no `PRAGMA foreign_keys`) | `assignee_id` | `BIGINT REFERENCES users(id)` (Postgres enforces FKs by default — **this is a behavior change from "declared, never enforced" to "declared and enforced"**) | Direct copy — but see policy. | Census #12 (orphaned FK): if any legacy row has an `assignee_id` pointing at a nonexistent `users.id` (possible precisely because SQLite never enforced it), enabling real enforcement in Postgres will reject that row's migration outright. **ASK, high-stakes**: null-out the orphaned reference (data loss of the association, but the association was already dangling/meaningless) vs. quarantine those rows vs. defer FK enforcement (`NOT VALID`) until cleaned up. Given `docs/domain/users.md`'s finding that no application code ever reads/writes this column anyway, nulling out orphans is the low-risk default recommendation, but it is still a data-destructive-adjacent choice reserved for a human. |
| `created_at` | `DATETIME NOT NULL` (naive local ISO string, e.g. `datetime.now().isoformat()`) | `created_at` | `TIMESTAMPTZ NOT NULL` if OQ-006 rules "fix to UTC-aware" (REPAIR), else `TIMESTAMP NOT NULL` (naive, FIXED) — **depends on OQ-006, do not pick unilaterally** | If TIMESTAMPTZ: every existing naive value needs an assumed source timezone to convert correctly — **which timezone the legacy server actually ran in was not supplied to this generator run** (not in README, not in any config file in evidence) and is itself an open gap; if TIMESTAMP: direct string-to-timestamp cast. | Census #10 (out-of-range datetimes): **ASK**, but also blocked on: what timezone was the legacy server's `datetime.now()` actually running in? This needs a human answer regardless of which way OQ-006 rules, because "naive local time" migrated to *any* explicit representation requires knowing what "local" meant. Recorded as **OQ-009** in `docs/open-questions.md`. |
| `closed_at` | `DATETIME` (nullable) | `closed_at` | Same treatment as `created_at`, nullable | Same as `created_at`. | Census #11 + same OQ-009 dependency. |

## Table: users

| legacy column | legacy type | target column | target type | transform | policy for dirt found |
|---|---|---|---|---|---|
| `id` | `INTEGER PRIMARY KEY` | `id` | `BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY` | Direct copy, preserve ids (referenced by `tickets.assignee_id`). | Census #15: same reasoning as `tickets.id`. |
| `email` | `TEXT NOT NULL UNIQUE` | `email` | `TEXT NOT NULL UNIQUE` (or `CITEXT` if case-insensitive matching turns out to matter — **FREE**, no legacy behavior evidences either way since no route ever queries `users` by email) | Direct copy. | Census #16/#17/#20 (nulls/encoding/dup-under-unique-intent): standard ASK — but see the table-level note below, this whole table may be moot. |
| `name` | `TEXT NOT NULL` | `name` | `TEXT NOT NULL` | Direct copy. | Census #18/#19: standard ASK. |

**Table-level note**: per `docs/domain/users.md`, no application code path reads or writes `users`
at all in this snapshot. Migrate the table and its data (if any exists — census will reveal row
count) faithfully regardless, since dropping populated data because *current* code doesn't use it
would be a real, irreversible mistake — but do not build any new application logic around it
beyond what a work order explicitly requires.

## Table: reset_tokens

| legacy column | legacy type | target column | target type | transform | policy for dirt found |
|---|---|---|---|---|---|
| `email` | `TEXT NOT NULL` (no index) | *(none — see below)* | *(none)* | **Not migrated as data.** PB-002's disposition (REPAIR in WO-003) replaces the entire token mechanism; legacy `reset_tokens` rows are transient, single-use-or-expired-within-30-minutes credentials, not durable records with any long-term value. | N/A — this is a REPAIR-driven schema replacement, not a data-preserving migration. Recommended default: **do not migrate any `reset_tokens` rows** (they're either already consumed, already expired past the new mechanism's window, or represent exactly the weak-credential problem being fixed) — flagged as **OQ-010** for explicit human ratification since "don't migrate this data" is itself a data-destructive-adjacent decision this generator should not finalize alone. |
| `token` | `TEXT NOT NULL` | *(none — see below)* | *(none)* | Same as above. | Same as above — MD5 tokens have no forward value under the new mechanism regardless. |
| `created_ts` | `REAL NOT NULL` | *(none — see below)* | *(none)* | Same as above. | Same as above. |

Target schema for the new mechanism (token hash, expiry, etc.) is WO-003's job to design against
`docs/domain/reset_token.md`'s invariants — this mapping table only addresses what happens to
*existing* legacy rows, which is: nothing, pending OQ-010's ruling.

## New open questions raised in this phase

- **OQ-009**: what timezone did the legacy server actually run `datetime.now()` in? Needed to
  correctly migrate `tickets.created_at`/`closed_at` under either OQ-006 outcome.
- **OQ-010**: should any `reset_tokens` rows be migrated at all, or is a clean-slate start
  (recommended default) correct given PB-002's REPAIR disposition?
