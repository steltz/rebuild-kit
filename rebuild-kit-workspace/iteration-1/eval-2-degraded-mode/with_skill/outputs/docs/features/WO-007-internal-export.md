# WO-007 — Internal CSV export (BLOCKED: existence question)

id: WO-007            depends_on: [WO-001]    milestone: M2
risk: 0.30 (tiny, but port-or-kill is undecided)          gate: false
status_note: blocked_by_asks: [OQ-001] — do not start until ruled
usage_weight: 0.01 (static-proxy; in-code comment claims dead since 2020)   pain_weight: 0.0
context_budget: ~120 lines (this WO + draft/internal-export.md + OQ-001)

behaviors:
  - statement: IF RULED LIVE — GET /internal/export/csv → 200 text/csv, header line
      `id,title,status`, one line per ticket (all tickets), exactly those 3 fields, NO
      quoting/escaping (commas in titles corrupt rows — observed, and therefore contract
      for whatever still parses this). Row order [audit A-06]: the SELECT has no ORDER BY;
      observed order is rowid (insertion) order and the golden trace pins that; modern
      orders by id ASC to match.
    fidelity: FIXED (conditional on OQ-001 = live)
    evidence: [ticketd/app/server.py:111-115, trace: export-csv-001]
  - statement: IF RULED DEAD — route is not ported; DNP-002 activates; trace export-csv-001
      moves to an expected-divergence entry (404) or is retired from the core set with the
      goldens re-captured.
    fidelity: — (ruling outcome)
    evidence: [ticketd/app/server.py:112 (comment: "no caller since" 2020), OQ-001]

acceptance:
  replay_set: core.jsonl → trace export-csv-001 (under whichever ruling applies)
  tests: characterization TestExportCsv (currently skipped, unskip if live)
escalation: ticketd/app/server.py:111-115
