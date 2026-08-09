# Open Questions — ASK register & PB proposals

<!-- see skill references/templates/open-questions.md -->

## OQ-002 — Are slug collisions acceptable, and if not, what is the target behavior?
- raised_by: generator P4
- kind: ambiguity
- readings:
  - A: collisions are a known-tolerated quirk — evidence: ticketd/app/util.py:4-6 comment
  - B: PB-003 reports them as a defect — evidence: docs/problem-brief.md PB-003
- blocks: [WO-002]
- ruling: Not acceptable (Reading B) — slugs must be unique; on collision append a numeric suffix (-2, -3, ...); existing stored slugs are not migrated. — ruled_by Dana Ruiz, 2026-08-09; propagated via spec-patch (OQ-002 slug uniqueness)
