# Migration Mapping — SQLite → PostgreSQL 16

Drafted from DDL alone (degraded mode — census pending, OQ-INT-2). Every policy marked ASK
requires owner ratification before WO-009 can run. Target DDL lives with the modern app's
Alembic migrations; this file is the authoritative old→new mapping.

## tickets → tickets
| legacy column | legacy type | target | transform | policy |
|---|---|---|---|---|
| id | INTEGER PK | bigint GENERATED ALWAYS AS IDENTITY | carry value; set sequence to MAX(id)+1 | fixed |
| title | TEXT | text NOT NULL | verbatim | fixed |
| slug | TEXT | text NOT NULL | verbatim — do NOT re-derive (legacy rows may predate current slugify; re-deriving would rewrite observed data) | fixed |
| priority | TEXT CHECK | ticket_priority enum ('low','med','high'), NULLable | verbatim; out-of-vocabulary values (census #13) → **ASK: repair-to-med / quarantine / carry-as-null** | ASK |
| status | TEXT CHECK | ticket_status enum ('open','closed') NOT NULL | verbatim; out-of-vocabulary (census #14) → **ASK** | ASK |
| assignee_id | INTEGER, FK declared-not-enforced | bigint NULL REFERENCES users(id) — enforced in target | dangling refs (census #12) → **ASK: null-out-with-log / quarantine row / create placeholder user** | ASK |
| created_at | DATETIME (naive local ISO string) | timestamptz NOT NULL | parse ISO, localize to **ASSUMED source timezone — ASK: which TZ did the server run in since 2019? DST ambiguity policy needed**, convert to UTC | ASK |
| closed_at | DATETIME nullable | timestamptz NULL | same as created_at | ASK |

## users → users
Carried verbatim (id, email, name); email keeps UNIQUE. Table is code-orphaned (OQ-002) but
referenced by assignee_id — **carry unless OQ-002 ruling says drop**. Duplicate emails under
case variance (census #20 probes exact dupes only; case-insensitive dupes worth a follow-up
probe) → ASK.

## reset_tokens → reset_tokens (restructured under PB-002/ED-003)
Target: `id identity PK, email text NOT NULL, token_hash text NOT NULL, created_at
timestamptz NOT NULL, consumed_at timestamptz NULL` + index on token_hash.
- **Live tokens (< 30 min old at cutover): ASK — recommended policy: do NOT migrate**
  (in-flight resets die at cutover; users simply re-request). Migrating them would require
  storing sha256 of the legacy MD5 values and a dual-lookup path — complexity with a
  30-minute payoff window.
- Expired rows (the unbounded backlog, likely the vast majority): **ASK — recommended: drop
  with count logged** (they are unusable by legacy code already, ticketd/app/server.py:103).
- created_ts epoch float → timestamptz: mechanical (`to_timestamp(created_ts)` — epoch is
  TZ-unambiguous, unlike the tickets timestamps).

## Rehearsal & cutover (documented, not scheduled)
1. Rehearsal (gated, M3): full dry run against a production snapshot once access arrives;
   census → ratified policies → transform → reconciliation.sql green.
2. Cutover: stop legacy writes → final delta run → reconciliation green → point clients at
   modern → keep legacy DB read-only for rollback window (**ASK: window length**).
3. Rollback: modern is write-target only after reconciliation passes; rollback = repoint to
   legacy, which remained untouched.
