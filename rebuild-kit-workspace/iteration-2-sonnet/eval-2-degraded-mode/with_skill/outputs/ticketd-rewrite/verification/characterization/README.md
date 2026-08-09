# Characterization Tests (L2)

Stdlib `unittest`, one file per feature (`test_tickets.py`, `test_auth_reset.py`), each test
citing the draft spec behavior it pins down. Faster and lighter than L3 twin-boot replay
(`verification/harness/`) — response-shape assertions only, no state diffing — meant to run on
every change; L3 remains the ground truth for acceptance.

Verified against a real legacy boot at generation time (13/13 pass) — this is the same
self-consistency discipline as the harness baseline: prove the test suite itself is correct
before trusting it to grade `modern/`.

## Running

```sh
# against legacy (self-check / regression baseline)
verification/harness/run-legacy.sh 5099 /tmp/scratch &
TICKETD_BASE_URL=http://127.0.0.1:5099 TICKETD_DB_PATH=/tmp/scratch/db/ticketd.sqlite3 \
  python3 -m unittest verification.characterization.test_tickets \
                       verification.characterization.test_auth_reset -v

# against modern (once it exists)
TICKETD_BASE_URL=http://127.0.0.1:<modern-port> \
  python3 -m unittest verification.characterization.test_tickets \
                       verification.characterization.test_auth_reset -v
# (TICKETD_DB_PATH is legacy-sqlite-specific plumbing for one test that needs to read an
#  un-exposed token; that test skips gracefully if the var isn't set)
```

## Coverage vs. the draft specs

Covers the load-bearing FIXED behaviors called out across `docs/features/draft/*.md`: the
title-required validation, numeric-priority coercion, the 200-empty-object not-found quirk,
close idempotency, exact-match status filtering, CSV shape, reset always-200, invalid-token
non-disclosure, rate limiting + the undocumented bypass header, and single-use token consumption.

**Not covered here** (see `verification/harness/README.md`'s "what's captured today" section for
the same gaps at the L3 layer): the 30-minute token expiry path, and the invalid-`priority`-value
error path (both flagged as open items in the relevant draft specs, not silently skipped).
