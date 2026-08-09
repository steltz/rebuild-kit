# Replay Harness

<!-- P7. rebuild.json.evidence.trace_capture_t1 = inactive (no captured production traffic). This
     harness runs entirely on T2 (scripted sessions against a REALLY-BOOTED legacy instance) and
     T3 (statically derived, provisional) input. See docs/problem-brief.md and
     rebuild.json.evidence.notes for the full degraded-mode picture. -->

## Legacy actually boots — this is the good news in an otherwise evidence-poor run

legacy/ is a self-contained Flask 1.x app on SQLite with one external dependency (SMTP). It boots
locally with nothing more exotic than `pip install flask`. That means, despite having no
production traffic, no logs, and no DB access, this workspace is NOT limited to characterization-
only verification (the fallback the skill calls for when legacy can't boot at all) — L3 twin-boot
replay is live for the legacy side today, real captured golden traces exist
(`verification/replay/traces/*-legacy.jsonl`), and the harness has been baseline-verified against
itself (`verification/replay/baselines/*-self-diff.json`, 28/28 traces pass — see P7's
convergence rule: "run the harness against legacy alone... must pass 100% before it ships").

What's still missing is the OTHER half of twin-boot: `modern/` doesn't exist yet (expected — this
workspace was generated before any implementation), so no real legacy-vs-modern diff has run.
`run-modern.sh` exits 2 with an explanatory message until M0 lands.

## How legacy is booted without touching legacy/

`legacy/app/server.py` hardcodes `DB_PATH = "db/ticketd.sqlite3"`, a path relative to the
process's CWD, not to the script location. `run_legacy_server.py` exploits this: it puts
`legacy/` on `PYTHONPATH` (so `from app.server import app` resolves to the real, unmodified
source) but sets the process CWD to a scratch directory OUTSIDE `legacy/` before running. The
SQLite file therefore lives in scratch, `legacy/` never gets written to, and the read-only guard
(pre-commit hook + stripped file permissions) stays untested-by-necessity rather than worked
around.

SMTP is stubbed (`smtp_stub.py`) by replacing `smtplib.SMTP` with an in-memory recorder BEFORE
any request handler runs — `smtplib.SMTP` is looked up as a module attribute at call time inside
`notify.py`, not bound at import time, so this works without editing `legacy/app/notify.py`.
`smtp.internal` doesn't exist in any sandbox this would plausibly run in; without the stub,
`close_ticket`/`request_reset` would hang for the full 30s timeout and then throw. The stub logs
every send to `sent_mail.jsonl` in the scratch dir — useful for eyeballing PB-001 in action.

## Files

| File | Purpose |
|---|---|
| `seed.sql` | Fixed seed rows (tickets 100 open, 101 closed) for deterministic trace IDs |
| `smtp_stub.py` | In-memory SMTP replacement, installed before legacy boots |
| `run_legacy_server.py` | Twin-boot launcher: seeds scratch DB, installs SMTP stub, boots legacy |
| `run-legacy.sh` | Thin CLI wrapper around the above |
| `run-modern.sh` | Placeholder — exits 2 with instructions until M0 implements modern/ |
| `capture_traces.py` | Drives a JSON-scripted session against a running instance, records JSONL traces (request/response/state) in the format `scripts/replay.py` expects |
| `diff-run.sh` | The actual L3 acceptance oracle a WO calls: caches legacy goldens, boots modern, diffs |

## Running it yourself

```sh
# 1. one-off: boot legacy, poke it manually
verification/harness/run-legacy.sh 5056 /tmp/scratch &
curl localhost:5056/api/tickets

# 2. capture a fresh set of legacy goldens for a script (already done once; traces are committed)
python3 verification/harness/capture_traces.py \
  --base-url http://127.0.0.1:5056 --db /tmp/scratch/db/ticketd.sqlite3 \
  --script verification/replay/scripts/tickets.json \
  --out verification/replay/traces/tickets-legacy.jsonl

# 3. self-consistency check (proves the normalize+diff plumbing works before trusting it)
python3 scripts/replay.py diff --rules verification/replay/diff-rules.yaml \
  --legacy verification/replay/traces/tickets-legacy.jsonl \
  --modern verification/replay/traces/tickets-legacy.jsonl
# => N/N traces pass

# 4. once modern/ exists: the real thing
verification/harness/diff-run.sh tickets
```

## What's captured today (input tier T2 unless noted)

- `verification/replay/traces/tickets-legacy.jsonl` — 18 traces: list, create (numeric + string
  + default priority, missing title, blank title), get (found/not-found), close (real
  transition, already-closed no-op, nonexistent, idempotent recheck), filtered list (open/
  closed/unknown status), CSV export.
- `verification/replay/traces/auth-reset-legacy.jsonl` — 10 traces: request, confirm (valid,
  reused-after-consume, bogus token), missing email, 4x rate-limit sequence (3 pass, 4th
  blocked), bypass-header request.
- **Not captured (T3/provisional territory, not attempted live):** the *expired* (30-minute)
  token-403 case — waiting 30 minutes inside a capture run isn't practical; if this WO needs that
  path covered, derive a T3 fixture instead (statically construct a `reset_tokens` row with an
  old `created_ts` and confirm against it) and mark it provisional per schema.md's input tiers.
  Also not exercised live: the invalid-`priority`-value 500 path noted as an ASK in
  `docs/features/draft/tickets-list-create-get.md` (a real trace would need to insert something
  that already violates the CHECK constraint's expectations, which is exactly the untested/
  unknown edge the spec flags — capturing it would tell us the ACTUAL current behavior, which
  would be worth doing once someone revisits this workspace).

## Known instrumentation gap (see `verification/replay/expected-divergences.yaml`)

Both REPAIR divergences (PB-001 async dispatch, PB-002 CSPRNG tokens) are defined against
harness-instrumentation fields (`$.meta.email_dispatch_mode`, `$.meta.token_mechanism`) that
don't exist in captured traces yet — the ED file documents the intended classification logic in
comments but nobody has wired it into `capture_traces.py` (there was no modern/ to capture from
this run to build it against). Whoever implements WO-003/WO-004 needs to either add that
instrumentation or get a different observable signal ruled instead. `expected-divergences.yaml`
is also UNSIGNED (`ruled_by: null` on every entry) — a human must sign it before either WO's L3
result can be trusted, which is why both are `gate: true` in `ledger.json`.
