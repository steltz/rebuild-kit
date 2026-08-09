id: WO-009            depends_on: [WO-001]                 milestone: M2
risk: 0.3 (low complexity; but ASK: OQ-004 could make this WO moot -- do-not-port instead)
usage_weight: 0.0 (zero observed hits — LOW CONFIDENCE, see zero-traffic.md)
pain_weight: 0.0
context_budget: ~150 lines (this WO + docs/features/draft/admin-export-csv.md + OQ-004)
gate: false

## What this WO does
Implement `GET /internal/export/csv`, reproducing the current escaping gap as-is. **Check
OQ-004's ruling before starting this WO** — if OQ-004 is ruled "dead," this WO should be
withdrawn from the backlog and `docs/do-not-port.md` DNP-002 promoted from candidate to
confirmed instead of implementing it.

behaviors:
  - statement: "200, text/csv, header row id,title,status, one row per ticket, no escaping/
      quoting of title -- a comma or newline in title corrupts the CSV structure. No auth, no
      params, dumps all tickets unconditionally."
    fidelity: FIXED (the escaping gap is real but not brief-mentioned; not a REPAIR target
      absent a PB entry sanctioning it)
    evidence: [legacy/app/server.py:111-115, docs/features/draft/admin-export-csv.md]

acceptance:
  replay_set: admin-export-csv-*.jsonl (3 traces, captured T2 golden including the
    comma-in-title escaping-gap case, self-check validated)
  tests: verification/characterization/test_against_golden.py
  l1: docs/contracts/openapi.yaml /internal/export/csv
  l3: verification/harness/diff-run.sh admin-export-csv

escalation: legacy/app/server.py:111-115 only. Check docs/open-questions.md OQ-004 first.
