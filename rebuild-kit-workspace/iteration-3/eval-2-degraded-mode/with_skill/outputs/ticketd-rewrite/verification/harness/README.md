# Replay Harness

Twin-boot L3 acceptance oracle, built and validated at generation time even though `modern/` is
empty (rebuild-kit design: the harness must twin-boot on day one of execution).

## What's here

- `lib/driver.py` — shared boot/seed/dump/email-capture logic.
- `run_legacy.py` / `run-legacy.sh` — boots `legacy/` (Flask test client, isolated scratch SQLite
  DB per run — see the CWD note below), drives every corpus file, writes the **legacy golden**
  traces to `verification/replay/traces/*.legacy.jsonl`. These are committed — cached per
  schema.md's input-tier design, since the legacy pin never moves without a re-run.
- `run_modern.py` / `run-modern.sh` — boots `modern/` the same way. Until `modern/app/main.py`
  and `modern/app/testing.py` exist, this prints a clear "not bootable yet" status and writes
  empty trace files — expected pre-M0, not a bug. See `run_modern.py`'s docstring for the exact
  contract `modern/` must eventually satisfy (a FastAPI `app` + a `testing.reset_and_seed`/
  `testing.dump_state` pair, mirroring what `lib/driver.py` does for legacy's SQLite).
- `diff-run.sh` — the acceptance oracle root CLAUDE.md's executor loop calls. Boots modern, then
  diffs every feature's modern trace against its cached legacy golden via `replay.py`.
- `replay.py` — vendored verbatim from the rebuild-kit skill (see its own header) so this harness
  runs standalone, with no skill installed, for a later executor session.

## A real legacy quirk this harness works around

`legacy/app/server.py:14` hardcodes `DB_PATH = "db/ticketd.sqlite3"` — a path relative to the
process's current working directory, not to the script location. `run_legacy.py` therefore
`chdir`s into a scratch temp directory (with its own `db/` subfolder) before importing and
booting the app, so the app's hardcoded relative path resolves to scratch space, never to
anything under `legacy/` (which is chmod read-only and must never be written to). This is
legitimate evidence about the legacy app worth carrying into `docs/contracts/integration-notes.md`
(already there) — not something to "fix" in the harness by editing legacy code.

## Validated at generation time

- **Legacy boots successfully** via Flask's test client — confirmed by hand and via the harness
  itself; this is NOT a top-severity finding (contrast with P7's playbook, which treats legacy
  failing to boot at all as top-severity). All 7 routes respond as `docs/features/draft/*.md`
  describes.
- **Harness determinism baseline** (P7 convergence requirement — "run the harness against legacy
  alone; it must pass 100% before it ships"): diffing the legacy golden traces against a verbatim
  copy of themselves, with `diff-rules.yaml` applied and NO `expected-divergences.yaml`, passes
  12/12 (tickets) and 7/7 (auth-reset). This proves the normalization rules and trace format are
  internally consistent, not that modern matches legacy (modern doesn't exist yet).
- **`diff-run.sh` end-to-end**, with `expected-divergences.yaml` applied against the (currently
  empty) modern traces, correctly reports every trace as failing ("missing on modern side") and
  exits 1. This is the expected, honest pre-M0 state — the harness fails loudly rather than
  silently passing on nothing.

## Email interception

Legacy's `send_mail` (via `smtplib.SMTP`) is intercepted in-process by `lib/driver.py`'s
`RecordingSMTP` — no real network connection is attempted, and legacy's own files are never
touched. This is a standard test monkeypatch, not a legacy code change. See
`verification/replay/diff-rules.yaml`'s header for why raw email body/token text is deliberately
excluded from the captured trace.

## Running it

```bash
# One-time (or after a legacy pin move / corpus change): regenerate legacy goldens.
verification/harness/run-legacy.sh

# Inner loop, once modern/ exists: boot modern + diff against cached legacy goldens.
verification/harness/diff-run.sh
```

Requires `flask` (legacy's own framework, for `run-legacy.sh`) and, once `modern/` exists,
whatever `modern/CLAUDE.md` settles on (`fastapi[testclient]` assumed by `run_modern.py`/
characterization tests per this generation pass — FREE if the executor picks differently, update
both driver scripts together).

## Characterization tests (L2)

`verification/characterization/*.py` — pytest, one file per feature, generated from
`docs/features/draft/*.md`. Skip cleanly (not error) until `modern/app/main.py` +
`modern/app/testing.py` exist (16 tests currently, confirmed skipping at generation time).
