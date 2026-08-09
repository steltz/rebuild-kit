# Verification strategy

Three layers, in order of when they run:

1. **Unit/route tests** (`ticketd-api/tests/`) — written as part of each
   phase's plan in `../plans/`, run via `pytest` / `./scripts/check.sh`.
   These are the bulk of correctness verification and are specified
   task-by-task in the plans; this document does not repeat them.
2. **Parity check** (`parity_check.py`, this directory) — runs the same
   sequence of HTTP requests against a running legacy instance and a
   running new instance, and diffs the responses. This is the tool that
   catches "technically passes its own tests but doesn't match legacy"
   bugs, which unit tests alone can't catch because they're written against
   the new system's own idea of correct behavior.
3. **SMTP-outage regression test** (`smtp_outage_test.py`, this directory)
   — the direct test for the incident that started this whole rewrite.
   Points the app at an unreachable SMTP target and confirms
   ticket-closing stays fast and reliable anyway.

## Acceptance criteria (tie back to `../00-CONTEXT-AND-CONSTRAINTS.md`)

| Requirement | How it's verified |
|---|---|
| No UI-visible behavior change except the 3 named fixes | `parity_check.py` against both instances |
| Closing tickets survives an SMTP outage | `smtp_outage_test.py` |
| No MD5/plaintext reset tokens at rest | `ticketd-api/tests/test_tokens.py`, `test_auth_reset.py` (Phase 4) + manual `SELECT * FROM reset_tokens` spot check showing only `token_hash`, never a raw token |
| Two similarly-named tickets get distinct slugs | `ticketd-api/tests/test_slugs.py`, `test_tickets_api.py` (Phase 2) |
| Legacy data migrates with matching ids, no loss | `ticketd-api/tests/test_migrate_from_sqlite.py` (Phase 1) + Task 1/2 of `../plans/06-migration-and-cutover.md` against real data |

## Running the parity check

Requires both a legacy instance and a new instance running against
**equivalent data** (same ticket ids/titles/etc — easiest way to get this is
to run the migration script against a copy of the legacy SQLite file, then
point the new instance at the resulting Postgres, and point the legacy
instance at that same original SQLite file).

```bash
# terminal 1 (from ticketd/)
python -m app.server            # legacy, defaults to :5000

# terminal 2 (from ticketd-api/)
uvicorn app.main:app --port 8000  # new

# terminal 3
python verification/parity_check.py --legacy http://localhost:5000 --new http://localhost:8000
```

Exits non-zero and prints every mismatch if anything differs beyond the
allow-listed intentional differences (see the script's `KNOWN_DIFFERENCES`
list — this is where `../03-OPEN-QUESTIONS.md` resolutions get encoded once
decided, e.g. if timestamp format is approved to change).

## Running the SMTP-outage test

```bash
# from ticketd-api/, with the app + worker running and pointed at
# SMTP_HOST=203.0.113.1 SMTP_PORT=25 (TEST-NET-3, guaranteed unreachable —
# see RFC 5737 -- do NOT point this at a real host you don't control)
python verification/smtp_outage_test.py --base-url http://localhost:8000
```

Fails loudly if any `close` request takes anywhere close to the legacy 30s
SMTP timeout — the whole point is that the new API's request latency must
be completely decoupled from SMTP reachability.

## What this verification does NOT cover (be aware, don't assume otherwise)

- **Real production data.** Everything in `ticketd-api/tests/` runs against
  synthetic fixtures. `../plans/06-migration-and-cutover.md` Task 1-2 is
  where real data first gets exercised, and that's explicitly gated as
  human-supervised.
- **Real 30-day traffic patterns.** `ticketd/ops/access.log` is a
  single-hour synthetic sample (see `../04-TRAFFIC-ANALYSIS.md`) — load
  testing at realistic scale needs a real traffic baseline this workspace
  didn't have access to.
- **Concurrent-load correctness** (e.g. the slug retry-on-conflict path
  under real concurrent writers) beyond what's in
  `ticketd-api/tests/test_slugs.py`'s single-process tests. If real traffic
  volume ever makes concurrent ticket creation with identical titles
  common, add a dedicated concurrency test before relying on the retry
  logic at scale.
