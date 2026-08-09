# docs/features/WO-006-csv-export.md
id: WO-006            depends_on: [WO-001]                milestone: UNSCHEDULED
risk: n/a — not scheduled to a milestone pending OQ-003
usage_weight: none (degraded)   pain_weight: 0    context_budget: ~150 lines    gate: true
blocked_by_asks: [OQ-003]

behaviors:
  - statement: Port `/internal/export/csv` (unquoted/unescaped CSV dump of all tickets).
    fidelity: ASK — docs/open-questions.md#OQ-003. Legacy's own comment claims "no caller since"
    a 2020 audit; unconfirmed (no access logs available this run). If OQ-003 rules the route
    dead: this WO is CLOSED as `do-not-port` (docs/do-not-port.md#DNP-002 becomes final) and
    deleted from the backlog, not implemented. If ruled live: implement FIXED to the documented
    output shape, and treat the missing CSV quoting/escaping as a PB-proposal candidate (file to
    open-questions.md; do not silently fix a legacy defect without sanction) — REPAIR only if a
    human ruling adds a PB entry for it.
    evidence: [legacy/app/server.py:111-115, docs/do-not-port.md#DNP-002]

acceptance:
  replay_set: N/A until OQ-003 is ruled live (no corpus entries exist for this route — do not
    author them until the ruling justifies the work)
  tests: N/A until ruled
escalation: consult legacy/app/server.py:111-115 only, and only if OQ-003 is ruled live.

## Why this WO exists but is unscheduled

Per schema.md, an OQ with `blocks: []` (flags gate review only) doesn't block other WOs, but a
candidate do-not-port item still deserves a placeholder WO so it isn't silently forgotten or
silently ported. This WO is intentionally NOT assigned to M0/M1/M2 — it sits outside the
milestone sequence until a human rules on OQ-003. If ruled dead, delete this file and mark
docs/do-not-port.md#DNP-002 final; do not leave it lingering as a phantom backlog item.
