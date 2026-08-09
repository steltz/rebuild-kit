# Verification Harness — twin-boot contract

`diff-run.sh` is the acceptance oracle (L3). It boots both trees from this root on identical
seeds, drives the same input set through each, and diffs responses + post-run state under
`../replay/diff-rules.yaml`, with `../replay/expected-divergences.yaml` passing sanctioned
REPAIRs only when they diverge as specified.

## Status (recorded 2026-08-08, generator)
- Legacy twin-boot: WORKS (Flask 3.x runs the pinned 1.x-era code unmodified).
- Golden traces captured at the pinned ref: `../replay/traces/core.legacy.jsonl` (30 traces).
- Baseline: legacy vs an independent second legacy run = 30/30 pass (normalization is sound).
- Manifest mechanics: simulated-modern run passes 30/30 with the ED entries; an injected
  unsanctioned divergence (404 on missing ticket) fails — the net catches.
- Input tiers: T2 only (scripted sessions). No T1 exists (degraded mode — no production
  traffic was ever available); T2 goldens come from executing the pinned legacy, which is
  ground truth outside the spec-writing loop.

## Pieces
| file | role |
|---|---|
| `run-legacy.sh` | boot pinned legacy: venv (Flask), seeded scratch SQLite, capturing SMTP stub. Emits `LEGACY_*` env lines |
| `legacy_boot.py` | harness shim: cwd→scratch rundir (relative DB path resolves outside the read-only tree), smtplib patched to the local stub. Send semantics stay sync — PB-001 preserved. NOT a legacy modification |
| `smtp_stub.py` | minimal capturing SMTP server → JSONL |
| `seed.py` / `seed.json` | shared seed; token rows use relative ages so 30-min expiry is testable without time travel |
| `drive.py` | drives an input set, records traces (capture rules in its docstring: 5xx bodies→null, no headers, tokens→`<TOKEN:trace-id>` placeholders) |
| `run-modern.sh` | delegates to `modern/harness/boot.sh` (contract below) |
| `diff-run.sh` | orchestrates capture/diff; report → `../replay/report.json` |
| `replay.py` | vendored L3 comparator (rebuild-kit v1.0) — do not hand-edit |

## Modern boot contract (WO-001 builds this)
`modern/harness/boot.sh`, executable. Inputs: `PORT`, `HARNESS=1`, `SEED_JSON`.
Must: serve on PORT against a FRESH database loaded from SEED_JSON; print
`MODERN_BASE_URL=...` and `MODERN_PIDS='...'` on stdout; background children must not hold
stdout open. Under `HARNESS=1` expose:
- `GET /__harness__/state` → `{"tickets": [...], "users": [...], "reset_tokens": [...]}`
  using LEGACY column names/values for tickets & users (reset_tokens uses the modern shape;
  it is excluded from row diffing and asserted via ED-003).
- `GET /__harness__/emails` → JSON list of dispatch events `{"from":..., "to": [...],
  "data": "..."}` in dispatch order. `data` must contain `closed: <title>` /
  `reset token: <token>` so the driver's classifier works on both sides.
- Seeded reset tokens (seed.json literals) must be confirmable — store them under the
  modern scheme (e.g. insert their hashes) with the seeded relative ages.

## Probe isolation (learned the hard way, kept as a rule)
The two 500-probes (`tickets-create-bad*`) sit LAST in `core.jsonl` before read-only steps:
a failed INSERT leaves the legacy per-request SQLite connection unclosed and un-rolled-back,
holding a write lock that stalls subsequent writes ~5s each (observed during golden
capture). Any new input set must keep crash-probes after all write steps. This is also
evidence for the draft-spec claim that legacy leaks connections on error paths.

## Re-capturing goldens
Only when the input set changes (goldens are pinned-ref artifacts — the pin makes the cache
valid indefinitely): `./diff-run.sh --capture-goldens core`, then commit the new goldens
with the input-set change in the same commit.
