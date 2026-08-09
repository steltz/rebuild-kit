# Replay harness — how it actually works

This is not a documented-but-unbuilt plan: legacy genuinely boots and every T2 golden trace
under `verification/replay/traces/legacy/*.jsonl` was captured from a real running instance of
`ticketd/app/server.py`, not hand-written. The harness was validated against itself (P7's
required "run against legacy alone" check) — `capture-legacy-goldens.sh --self-check` boots
legacy twice independently from the same seed and diffs the two runs; last verified run: 7/7
suites, 0 unexpected diffs (see git history for `verification/replay/traces/legacy/`).

## Requirements

- Python 3 with **Flask** installed (`pip install flask` — legacy's only non-stdlib
  dependency; everything else it imports is stdlib: `sqlite3`, `smtplib`, `hashlib`, `time`,
  `datetime`). If your environment is externally-managed (e.g. Homebrew Python on macOS,
  `pip install` refuses with "externally-managed-environment"), create a venv:
  `python3 -m venv .venv && .venv/bin/pip install flask` and run harness scripts with
  `.venv/bin/python3` on `PATH`, or `source .venv/bin/activate` first.
- `curl` (used by `run-legacy.sh`/`run-modern.sh` for the readiness check).
- No network access is required — SMTP is stubbed (see below), and legacy runs entirely
  against a local SQLite file.

## How legacy boots without modifying `legacy/` (i.e. `ticketd/`)

Two problems, both solved in `legacy_wrapper.py` (full rationale in its docstring):

1. `DB_PATH = "db/ticketd.sqlite3"` in `app/server.py` is a relative path resolved against the
   process's cwd — but `ticketd/db/` is read-only (the P0 guard strips write bits on the whole
   legacy tree, correctly). The wrapper `chdir()`s to a scratch run directory that has its own
   writable `db/` subdir and adds the legacy app root to `sys.path`, so `import app.server`
   still resolves the real legacy code while all runtime file I/O lands outside `ticketd/`.
2. `app/notify.py` opens a real SMTP connection to `smtp.internal:25`, which does not exist in
   any environment this harness runs in. The wrapper monkeypatches the **imported module
   object's** `send_mail` attribute at process-runtime (not a file edit) to record `{to, body,
   ts}` into a local JSONL "mail log" instead of touching a socket. Every call site's decision
   to send mail — rate limiting, the `if changed:` close-notification guard, token generation —
   executes as real legacy code; only the actual network syscall is stubbed. This is a
   disclosed substitution, not a silent one: see `docs/problem-brief.md` PB-001 and
   `verification/replay/expected-divergences.yaml`'s notes on why this trace format doesn't
   (yet) carry dispatch-mode as a comparable field.

## Running it

```bash
# Re-capture every T2 golden from a fresh legacy boot per suite (only needed if you change
# verification/replay/inputs/*.jsonl):
verification/harness/capture-legacy-goldens.sh

# Same, plus the required self-validation (legacy boots twice, diffs itself):
verification/harness/capture-legacy-goldens.sh --self-check

# Once modern/ has a real app (WO-001+), run one suite's L3 acceptance check:
verification/harness/diff-run.sh tickets-create
```

## A defect this harness found by actually running the app

While validating `tickets-create`'s golden capture, back-to-back requests where one triggered
legacy's uncaught-500-on-invalid-priority path (`docs/features/draft/tickets-create.md`) caused
the *next* write request to fail with `sqlite3.OperationalError: database is locked` — not the
error its own input should produce. Root cause: `app/server.py`'s `db()` opens a connection
into Flask's `g` per request but the app never registers `@app.teardown_appcontext` to close
it; a request that raises before `.commit()` leaves an open, uncommitted connection pinning a
lock until Python's GC eventually finalizes it. Logged as `docs/open-questions.md` OQ-010 (a PB
proposal, not silently fixed or silently reproduced) — this is exactly the kind of finding
static reading alone would have missed, and exactly why P7 insists on executing legacy for
real rather than trusting the analysis that wrote the specs.

## Known limitations, disclosed

- Traces are **T2** (scripted sessions), not **T1** (captured production traffic) — no real
  production request/response corpus was available (see `docs/problem-brief.md` OIQ-3 on the
  access log's actual 1-hour synthetic window). `rebuild.json.evidence.trace_capture_t1` is
  marked `degraded` for this reason, not `active`.
- `run-modern.sh` is a contract stub until WO-001 (Milestone 0, the walking skeleton) exists —
  see its own header comment. `diff-run.sh` will fail loudly, not silently, until then.
- The chained auth-reset-confirm traces regenerate a fresh token per boot (real MD5-of-time
  today, a CSPRNG value post-WO-003) — `verification/replay/diff-rules.yaml` explicitly drops
  `$.request.body.token` from comparison with a documented rationale; this was discovered via
  the harness's own self-check failing before the rule was added, not decided speculatively.
