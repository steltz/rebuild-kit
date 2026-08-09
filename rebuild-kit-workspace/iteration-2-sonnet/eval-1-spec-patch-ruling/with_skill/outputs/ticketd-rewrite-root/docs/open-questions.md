# Open Questions — ASK register & PB proposals

<!-- see skill references/templates/open-questions.md -->

## OQ-002 — Are slug collisions acceptable, and if not, what is the target behavior?
- raised_by: generator P4
- kind: ambiguity
- readings:
  - A: collisions are a known-tolerated quirk — evidence: ticketd/app/util.py:4-6 comment
  - B: PB-003 reports them as a defect — evidence: docs/problem-brief.md PB-003
- blocks: [WO-002]
- ruling: Not acceptable — slugs must be unique; on collision with an existing stored slug, append a numeric suffix to the generated base slug (`-2` for the first collision, `-3` for the next, ...); existing stored slugs are not migrated or regenerated, only newly generated slugs are subject to the uniqueness check — ruled_by Dana Ruiz, 2026-08-08; propagated via spec-patch (see commit history)
