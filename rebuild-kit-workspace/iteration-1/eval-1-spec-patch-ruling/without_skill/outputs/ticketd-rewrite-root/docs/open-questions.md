# Open Questions — ASK register & PB proposals

<!-- see skill references/templates/open-questions.md -->

## OQ-002 — Are slug collisions acceptable, and if not, what is the target behavior?
- raised_by: generator P4
- kind: ambiguity
- readings:
  - A: collisions are a known-tolerated quirk — evidence: ticketd/app/util.py:4-6 comment
  - B: PB-003 reports them as a defect — evidence: docs/problem-brief.md PB-003
- blocks: [WO-002] — cleared by ruling
- ruling: RULED 2026-08-08 by Dana Ruiz — reading B. Collisions are NOT acceptable.
  - target behavior: slugs must be unique; on collision append a numeric suffix (-2, -3, ...)
  - scope: new slug generation only — existing stored slugs stay exactly as they are (no migration of old data)
  - disposition: PB-003 becomes REPAIR in WO-002; divergence recorded as ED-002
