# SQLite -> Postgres data migration plan

Status: **script ready, execution blocked** — we have no production DB yet, and one
required input is unknown. Do not dry-run against anything but a synthetic SQLite file
until then.

## Blockers (must resolve before a real run)

1. **Legacy server timezone** (`[U]`, ADR-004, intake D3/C4). Legacy `created_at` /
   `closed_at` are naive local ISO strings; the script reinterprets them in
   `--legacy-tz` to produce timestamptz. Wrong tz = every historical timestamp off by
   hours. The script REFUSES to run without an explicit `--legacy-tz`.
2. **Data reconnaissance** (intake C1–C7): out-of-range priority/status values,
   timestamp format drift in 2019-era rows, invariant violations, users/assignee_id
   rows. The script logs and quarantines rows it can't map rather than guessing.

## What the script does (`migrate_sqlite_to_postgres.py`)

- Copies `users`, `tickets` **preserving legacy ids** (`OVERRIDING SYSTEM VALUE`),
  then resets identity sequences.
- Parses naive ISO timestamps in `--legacy-tz` → UTC timestamptz.
- `reset_tokens`: **dropped by default** (`--skip-reset-tokens`, on). Legacy rows hold
  plaintext MD5 tokens with a 30-min lifetime; they are dead weight and a leak
  hazard, and the new table stores hashes (ADR-002). Freeze reset requests for the
  cutover window instead.
- Rows that fail constraints or parsing go to `migration_quarantine.jsonl` with a
  reason; the run fails at the end if the quarantine is non-empty unless
  `--allow-quarantine` is passed.
- Idempotent-ish: expects EMPTY target tables and aborts otherwise (rerun = wipe and
  redo; no partial resume).

## Cutover sketch (to be firmed up once evidence exists)

1. Freeze legacy writes (stop process or block at proxy). Small tool, short window.
2. Copy `db/ticketd.sqlite3`; run the script against the copy.
3. Run `tests/test_parity.py` read-only checks against both, plus row-count and
   spot-check diffs.
4. Flip traffic. Keep legacy + SQLite file untouched for rollback.
5. Watch outbox worker delivery and 5xx rates; rollback = point traffic back.

Open question that changes this plan: if intake C3 finds an external direct-to-SQLite
writer (Q2), it must be migrated or shimmed FIRST — cutover as sketched would
silently orphan it.
