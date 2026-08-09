# Open Questions — ASK register & PB proposals

<!-- see skill references/templates/open-questions.md -->

## OQ-002 — Are slug collisions acceptable, and if not, what is the target behavior?
- raised_by: generator P4
- kind: ambiguity
- readings:
  - A: collisions are a known-tolerated quirk — evidence: ticketd/app/util.py:4-6 comment
  - B: PB-003 reports them as a defect — evidence: docs/problem-brief.md PB-003
- blocks: [WO-002]
- ruling: Slug collisions are NOT acceptable. Slugs must be unique; on collision, append a numeric suffix (-2, -3, ...) to the generated slug. Existing stored slugs are not migrated — they keep whatever value they already have, including any pre-existing duplicates.
- ruled_by: Dana Ruiz
- ruled_at: 2026-08-09
- divergence: ED-002
