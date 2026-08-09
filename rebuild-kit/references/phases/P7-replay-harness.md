# P7 — Replay Harness

Outputs: `verification/replay/` (traces, `diff-rules.yaml`, `expected-divergences.yaml`),
`verification/harness/` (`run-legacy.sh`, `run-modern.sh`, `diff-run.sh`),
`verification/characterization/` (generated tests + golden fixtures).

This is the layer that breaks the self-grading loop: expected values come from **executing
legacy**, not from your analysis. Build it even though modern/ is empty — the harness must
twin-boot on day one of execution.

## Procedure

1. **Twin-boot scripts.** `run-legacy.sh` and `run-modern.sh` boot each tree from the root on
   identical seeded fixtures (same DB seed, same env, distinct ports); `diff-run.sh` drives an
   input set through both and diffs responses **and post-run state** (DB dump, emitted events,
   outbound calls) via `scripts/replay.py diff`. Getting legacy to boot locally is real work —
   dockerize or document every needed service; if legacy cannot boot, that is a **top-severity
   finding**: record it, cap all L3 claims, fall back to characterization-only.
2. **Input sets.** Assemble per input tier (schema.md#input-tiers): T1 from the P2 scrubbed
   corpus if present; T2 scripted sessions covering every P4 spec's happy path + key edges
   (the workhorse); T3 statically derived pairs marked provisional. Record **legacy golden
   outputs** once per input set at the pinned ref and cache them — the inner loop then boots
   only modern.
3. **diff-rules.yaml.** Author normalization: timestamps, generated IDs, ordering-insensitive
   collections, volatile headers. Rule of thumb: normalize what a fresh boot can't reproduce,
   nothing more — every rule is a hole in the net, so keep the file short and justified.
4. **expected-divergences.yaml.** One entry per REPAIR behavior (from P4), mapping trace
   pattern → PB ID → specified new behavior. Human-signed before execution starts.
5. **Characterization tests** (L2): generate fast tests from P4 specs + P5 golden fixtures,
   organized per feature so WOs can reference their slice (`acceptance.tests`).
6. **Assign replay sets per WO** — P8 reads this mapping into each WO's `acceptance.replay_set`.

## Validation

Run the harness against legacy alone (legacy vs its own goldens) — it must pass 100% before it
ships. A harness that can't verify legacy against itself will produce noise, not verification.
Record the run in `ledger.json` as the harness baseline.
