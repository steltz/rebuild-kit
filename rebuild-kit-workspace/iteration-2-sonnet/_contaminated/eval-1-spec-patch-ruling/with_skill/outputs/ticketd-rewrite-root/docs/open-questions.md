# Open Questions — ASK register & PB proposals

<!-- see skill references/templates/open-questions.md -->

## OQ-002 — Are slug collisions acceptable, and if not, what is the target behavior?
- raised_by: generator P4
- kind: ambiguity
- readings:
  - A: collisions are a known-tolerated quirk — evidence: ticketd/app/util.py:4-6 comment
  - B: PB-003 reports them as a defect — evidence: docs/problem-brief.md PB-003
- blocks: [WO-002]
- ruling: Slug collisions are NOT acceptable (reading B). Target: slugs must be unique; on collision, append a numeric suffix (-2, -3, ...) until unique. Existing stored slugs are NOT migrated (no backfill/dedup of already-persisted rows). — ruled_by Dana Ruiz, 2026-08-08; propagated via spec-patch (see ED-002)
