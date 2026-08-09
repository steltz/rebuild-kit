# Verification Harness

Built and validated during P7 generation (2026-08-09). Everything below was actually run, not just
scaffolded — see "What was validated" at the bottom.

## Layers

- **L1** — contract validation against `docs/contracts/openapi.yaml` + `schemas/*.json`. No
  dedicated script here; any OpenAPI/JSON-Schema validator works (P5 validated the contracts
  themselves this way — see that phase's commit).
- **L2** — `characterization/test_*.py` (pytest + jsonschema). Run standalone against the frozen
  trace corpus (no live server needed): `pytest verification/characterization/`. All 35 assertions
  pass against the real captured legacy traces as of this generation run.
- **L3** — `harness/diff-run.sh <trace-basename>` boots `modern/` (via `run-modern.sh`), drives the
  named trace file's *requests* through it (`drive_trace.py`), and diffs the live responses against
  the trace's captured legacy responses using the skill's `scripts/replay.py diff`, honoring
  `replay/diff-rules.yaml` normalization and `replay/expected-divergences.yaml` sanctioned
  REPAIRs.

## Evidence tiers actually in this workspace

- **T1 (captured production traffic)**: none. `rebuild.json.evidence.trace_capture_t1: inactive`.
- **T2 (scripted sessions against the real legacy app)**: **active, and this is the workhorse
  here** — every trace under `replay/traces/*.jsonl` was captured by actually booting
  `ticketd/app/server.py` locally (via the same procedure now encoded in `harness/run-legacy.sh`)
  and driving real HTTP requests through it, not by reading the source and guessing outputs. This
  is a meaningfully stronger evidence base than the T3 fixtures under `docs/contracts/fixtures/`
  (which remain T3 — statically derived, provisional, L2-only) and should be preferred as the
  reference wherever the two might imply different things (they shouldn't, but if they do, trust
  the trace, and file the fixture as wrong).
- **T3 (statically derived)**: `docs/contracts/fixtures/*.json` — provisional, counts toward L2
  only, per schema.md's input-tier rules.

## Known gap: `side_effects` over HTTP

`drive_trace.py` (used by `diff-run.sh`) can only observe what the live HTTP response contains.
The captured legacy traces carry a `side_effects` block (notification dispatch mode, token
mechanism) that was only observable during capture because the capture script controlled the fake
SMTP stub directly and read its log file — `drive_trace.py` has no equivalent hook into `modern/`
yet. **This means ED-001/ED-001b/ED-002 (the PB-001/PB-002 REPAIR divergences) will not be
meaningfully exercised by `diff-run.sh` until `modern/` exposes some equivalent introspection**
(a test-only hook, or the harness reading modern's own outbox/queue table directly). This is
WO-001/WO-003's job to wire up, not something this generator run could do against code that
doesn't exist yet. Flagged here so it isn't silently assumed to already work.

## Known gap: `run-modern.sh` is a placeholder

`modern/` is an empty tree as of this generation run (by design — see root `CLAUDE.md`, "you
generate, you never rewrite"). `run-modern.sh` fails loudly with instructions rather than silently
no-op-ing; the first work order that makes `modern/` runnable (expected: an M0/WO-000 setup task —
see `backlog.md`) must fill it in.

## What was validated during generation (P7)

- `harness/run-legacy.sh` actually boots the legacy app (confirmed: `GET /api/tickets` → `200`)
  from a scratch copy, never writing into `ticketd/`.
- All 22 captured traces (`replay/traces/*.jsonl`) came from real HTTP calls against that booted
  instance, including a genuinely reproduced legacy defect (SQLite connection leak causing
  intermittent `database is locked` 500s — see PB-004 in `docs/problem-brief.md` and trace
  `tickets-crud-lock-cascade-901`).
- `replay/diff-rules.yaml` and `replay/expected-divergences.yaml` both parse correctly under the
  skill's bundled mini-YAML reader (`scripts/replay.py load_yaml`).
- The harness baseline (`scripts/replay.py diff` with each trace file compared against itself, no
  divergences applied) passes 100% for all three trace files (13/13, 3/3, 6/6) — the required P7
  convergence check ("run the harness against legacy alone").
- A simulated ED-001 divergence (manually flipping `dispatch_mode` from `sync` to `async` in a
  copy of one trace) was correctly recognized as "diverged as specified" rather than a failure,
  confirming the expected-divergences mechanism works end-to-end before any real `modern/` code
  exists to exercise it for real.
- `verification/characterization/test_*.py` — 35/35 pass via `pytest` against the real trace
  corpus (one test assertion bug found and fixed during this validation: `notify.py:7` wraps the
  recipient in a list even for one address — `sendmail(from, [to], body)` — the test originally
  asserted a bare string).

None of this used the project's ambient Python environment (which lacks Flask) — a throwaway venv
was used for validation. `run-legacy.sh` respects a `$PYTHON` override for exactly this reason;
whichever environment actually executes the rewrite needs `flask` (legacy boot), `pytest` +
`jsonschema` (characterization tests) installed somewhere — not vendored into this workspace.
