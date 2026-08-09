# Open Questions — ASK register & PB proposals

<!-- see skill references/templates/open-questions.md -->

## OQ-002 — Are slug collisions acceptable, and if not, what is the target behavior?
- raised_by: generator P4
- kind: ambiguity
- readings:
  - A: collisions are a known-tolerated quirk — evidence: ticketd/app/util.py:4-6 comment
  - B: PB-003 reports them as a defect — evidence: docs/problem-brief.md PB-003
- blocks: [WO-002]
- ruling: Reading B — collisions NOT acceptable; slugs must be unique, numeric suffix (-2, -3, ...) on collision; existing stored slugs stay as-is (no migration).
  Detail: PB-003 confirmed as defect; Reading A (tolerated quirk) rejected. Uniqueness is
  enforced at generation time for new slugs only — pre-existing duplicates persist, so a
  DB-level UNIQUE constraint on slug is not implied.
- ruled_by: Dana Ruiz
- ruled_at: 2026-08-08
- consequences: PB-003 dispositioned REPAIR in WO-002; divergence ED-002 added to the
  expected-divergence manifest; WO-002 unblocked in ledger.json
