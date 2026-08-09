# Migration Mapping — SQLite `db/ticketd.sqlite3` → PostgreSQL

Source schema: `docs/contracts/ddl.sql` (verbatim from `ticketd/db/schema.sql`).
Target schema: `docs/migration/target-schema.sql` (proposed — FREE choices flagged, ASK
items block until ruled). Policies here are **ASK until a human ratifies them** — data
destruction or transformation is never a generator decision.

## tickets → tickets

| source | target | transform | policy status |
|---|---|---|---|
| id INTEGER PK | id BIGINT GENERATED ALWAYS AS IDENTITY | copy; set sequence to MAX(id)+1 | mechanical (no ruling) |
| title TEXT | title TEXT NOT NULL | copy | mechanical |
| slug TEXT | slug TEXT NOT NULL | copy as-is — **no dedup/rewrite until OQ-001 rules**; if the ruling adds uniqueness, existing collisions need the ruling's dedup policy | **ASK (OQ-001)** |
| priority TEXT CHECK | priority ticket_priority enum (low/med/high) | copy; census probe #13 must be 0 first (historic out-of-range rows → policy needed if found) | ASK pending census |
| status TEXT CHECK | status ticket_status enum (open/closed) | copy; census probe #14 gate | ASK pending census |
| assignee_id INTEGER FK | assignee_id BIGINT REFERENCES users(id) | copy; SQLite never enforced the FK — census probe #12 (orphans) decides repair/quarantine/null-out | **ASK pending census** |
| created_at DATETIME (naive local ISO string) | created_at timestamptz NOT NULL | parse ISO; attach prod server TZ; convert UTC | **ASK (OQ-005)** — TZ unknown |
| closed_at DATETIME nullable | closed_at timestamptz | as above; also repair-or-flag rows violating invariant I4 (closed without closed_at) — census addendum query in reconciliation.sql | **ASK (OQ-005 + census)** |

## users → users

Straight copy (id, email, name); `email` keeps UNIQUE. Census probe #20 (duplicate emails
under SQLite's enforced unique — expected 0) is a sanity check only. Mechanical.

## reset_tokens → **not migrated** (proposed)

Rows are ≤30-minute-lifetime artifacts plus dead expired rows (DNP-003); the modern token
store (PB-002: hashed at rest) cannot represent cleartext MD5 rows anyway. Proposal:
**drop with log** — cutover happens with an empty modern token table; in-flight resets at
cutover minute fail with the standard 403 and users simply re-request.
**Policy status: ASK — ratify at the WO-007 gate** (it is a deliberate, tiny behavior loss
at cutover).

## Order & mechanics

1. `users` (FK target) → 2. `tickets` → 3. sequences. Single transaction; source DB opened
   read-only at a quiesced moment (cutover doc). Loader: WO-007 implements
   `modern/` tooling + `verification/harness/` runs it against seeded fixtures in the
   inner loop (twin-boot makes migration testable without prod).

## Reconciliation (acceptance for WO-007)

`reconciliation.sql` — row counts, per-column checksums, invariant probes. WO-007 passes
only when every reconciliation query returns its expected value against a migrated copy.
