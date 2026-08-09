# WO-005 — Admin: CSV export

id: WO-005            depends_on: [WO-002]              milestone: M2
risk: 0.25 (inferred-claim ratio low; complexity trivial; no PB entry touches this area; only
  flag is the "no caller since 2020" comment, which does NOT meet the do-not-port evidence bar —
  see docs/features/draft/admin-export-csv.md)
usage_weight: 0.05 (static proxy — lowest reference count; route comment self-reports as likely
  unused, though that's not proof)
pain_weight: 0.0
context_budget: ~150 lines (this WO + docs/features/draft/admin-export-csv.md)
gate: false

## Behaviors

- statement: `GET /internal/export/csv` — 3-column CSV (`id,title,status`), all tickets, no
  quoting/escaping in legacy.
  fidelity: FIXED (output shape for clean data) — using a real CSV writer (stdlib `csv` module
  or equivalent) instead of legacy's naive f-string join is FREE as long as the header + column
  order + comma-separated shape matches for the clean-data case; this fixes the
  unquoted-comma-in-title bug as a side effect of an idiomatic implementation choice, not as a
  cited REPAIR (no PB entry covers it) — record this FREE choice in ledger notes so it's visible,
  since a stricter reading of "FIXED means match observably" could flag it otherwise.
  evidence: [legacy/app/server.py:111-115]
- statement: this route may be genuinely unused ("no caller since" the 2020 audit) but that's a
  code comment, not zero-traffic evidence — P2 is inactive this run. Port it; don't drop it.
  fidelity: FIXED (evidence bar for removal not met)

## Escalation

`legacy/app/server.py:111-115` only if citations are ambiguous.

## Acceptance

- L1: `/internal/export/csv` validated against openapi.yaml (structural: header + text/csv).
- L2: `verification/characterization/test_tickets.py::test_export_csv_shape` passes.
- L3: `verification/harness/diff-run.sh tickets` — `tickets-018-export-csv` passes.
