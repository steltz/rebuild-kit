# Twin-Boot Harness

L3 acceptance oracle: both trees boot from this root on the identical logical seed
(`verification/replay/fixtures/seed.sql`), the same input sets are driven through each, and
responses + post-run state are diffed under `verification/replay/diff-rules.yaml`, with
`expected-divergences.yaml` passing sanctioned changes only when they diverge as specified.

## Commands

```bash
verification/harness/diff-run.sh --capture-legacy [SET...]  # (re)capture legacy goldens at the pin
verification/harness/diff-run.sh --selftest [SET...]        # legacy vs its own goldens (must be 100%)
verification/harness/diff-run.sh [SET...]                   # modern vs cached goldens  (the oracle)
verification/harness/.venv-legacy/bin/python -m pytest verification/characterization  # L2 vs legacy
CHAR_TARGET=modern .../python -m pytest verification/characterization                 # L2 vs modern
```

Sets live in `verification/replay/input-sets/`:
- `t2-core` (32 traces) — every draft-spec happy path + key edges. Goldens cached at the pin
  (`traces/t2-core.legacy.jsonl`): the inner loop boots only modern.
- `t2-edge-ask` (2 traces) — behaviors frozen but awaiting rulings (OQ-003, OQ-007).
  **Excluded from WO acceptance** until ruled.

## Baseline (recorded in ledger.json)

Captured 2026-08-08 at legacy_ref `be1032b`: selftest 32/32 + 2/2 pass; characterization
21/21 pass against the legacy boot. A harness that cannot verify legacy against itself
produces noise — rerun `--selftest` after any harness change.

## How legacy boots without smtp.internal

`legacy_boot.py` substitutes `smtplib.SMTP` with a capture sink writing
`{"from","to","body"}` JSON lines (shape: `docs/contracts/schemas/mail-message.schema.json`)
to `var/legacy-run/outbox.jsonl`. The send remains synchronous in-request — exactly
legacy's dispatch mode; only the network dependency is removed. The legacy tree itself is
never modified.

**Fidelity caveat** (also in `audit/report.md`): prod runs "Flask 1.x era"
(`ticketd/app/server.py:1`); exact prod versions were not provided. The harness pins
`flask==3.1.*` (`requirements-legacy.txt`). All app-level behaviors asserted here are
version-stable; framework-generated error *pages* are not, which is why diff rules compare
non-JSON bodies at status + media-type level only.

## The modern side's contract (WO-001 implements)

- `modern/harness-boot.sh PORT SINK_FILE` — fresh schema from
  `docs/migration/target-schema.sql`, seeded with the logical content of `seed.sql`,
  app on PORT, mail dispatcher delivering to SINK_FILE within 300ms of commit
  (drive.py samples after `--settle-ms 300`).
- `modern/harness-dump.sh` — DB as JSON, same shape as `dump_sqlite.py` output
  (tables → row-object lists ordered by id; legacy-named columns for shared tables).
- `modern/harness-age-token.sh EMAIL SECONDS` — expiry test hook
  (mirrors `age_token_sqlite.py`).
- Harness hooks enabled only under `HARNESS=1`; absent from production builds.

## State recorded per trace

- `state.db_dump` — full DB (diff rules exclude `reset_tokens` + `mail_outbox`; see
  the justification comments in `diff-rules.yaml`).
- `state.email` — `{mode, messages[{to, body_redacted}]}` for requests that emitted mail;
  `mode` is the runner's declared dispatch mode (legacy `sync` by construction of the
  sink; modern `queued` per its runner) — ED-001/ED-003 pivot on it.
- `state.token_store.cleartext` — observable PB-002 predicate: does the token string
  emailed to the user appear verbatim in the DB dump? Legacy `true`; modern must be
  `false` (ED-002).
