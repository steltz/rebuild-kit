# Draft spec: GET /internal/export/csv

usage_weight: 0.0 (zero observed hits — LOW CONFIDENCE, see zero-traffic.md / OQ-004)

## Behaviors

- statement: Returns `200`, `Content-Type: text/csv`, body: header row `id,title,status`
    followed by one line per ticket, fields comma-joined with **no escaping/quoting** of
    `title` — a title containing a comma or newline would corrupt the CSV structure.
  fidelity: FIXED (as-coded) — the escaping gap is real but not brief-mentioned, and this route
    is possibly dead (OQ-004); not worth a REPAIR absent a ruling that it's actually used.
  evidence: [legacy/app/server.py:111-115]
  confidence: cited

- statement: No auth, no query params, dumps every ticket unconditionally regardless of status.
  fidelity: FIXED
  evidence: [legacy/app/server.py:111-115]
  confidence: cited

## Priority note for P8
Lowest-priority WO in the backlog by usage weight (0, low confidence) and by the do-not-port
candidacy in OQ-004/DNP-002. Scope this WO last; if OQ-004 rules "dead," this becomes a
do-not-port entry instead of a WO and the ledger should reflect that rather than silently
dropping it.

## Acceptance
  replay_set: admin-export-csv-*.jsonl (nonempty table, empty table, title-with-comma edge case
    to document the escaping gap even if not fixed)
  tests: characterization/admin/export-csv.spec
