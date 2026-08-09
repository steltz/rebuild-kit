# Workflows — orchestration record for this rewrite

## Generation run (2026-08-08)
Target is ~170 lines of legacy code, so the pipeline ran **serially** in one generator
session (proportionality rule: workflows exist for when scale, not judgment, is the
constraint). No fan-out scripts were needed; coverage was enumerated by walking
`inventory.json` (5 files, 7 routes — every file appears in a P3 subsystem, every route in
P4 drafts and the OpenAPI contract).

Audit (P9) ran with a fresh-context subagent attacking the specs against the pinned source
— see audit/discrepancy-report.md for findings and dispositions.

## Rerunnable pieces
| task | command (from root) |
|---|---|
| re-inventory after re-pin | `python3 <skill>/scripts/inventory.py --root .` |
| capture goldens (input set changed) | `verification/harness/diff-run.sh --capture-goldens <set>` |
| harness self-check | boot legacy twice, `verification/harness/replay.py diff` runs 30/30 |
| L3 acceptance (executor inner loop) | `verification/harness/diff-run.sh core` |
| census (when DB access arrives) | run `docs/migration/census-queries.sql` read-only; then spec-patch |
| spec-patch (rulings/evidence arrive) | open a session with the rebuild-kit skill at this root — `rebuild.json` routes it to resume mode |

## Executor parallelism
Permitted between control points per root CLAUDE.md, but this target is small enough that
serial WO execution is the sensible default. Gates (M0, WO-004 design, M2, M3 ×2) and open
ASKs are hard boundaries either way.
