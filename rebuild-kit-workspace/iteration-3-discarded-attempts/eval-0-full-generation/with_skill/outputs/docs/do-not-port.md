# Do Not Port

<!-- Negative space. Each entry: what, evidence (zero-traffic + zero-references / PB-nnn), provenance. -->

Nothing is confirmed dead yet — both candidates below are demoted to OQ status because zero-traffic
evidence is weak (the only access log covers one synthetic hour, see OQ-102) and neither has a
gate-level "no caller anywhere, ever" guarantee. Per design principle 5, these are documented as
candidates, not silently dropped and not silently ported.

## Candidate: `legacy/app/legacy_import.py` — 2019 spreadsheet importer
- what: `import_spreadsheet(path)`, a one-off CSV importer for the 2019 spreadsheet-era migration.
- evidence: zero inbound imports anywhere in the tree (grep confirms nothing references
  `legacy_import` outside the file itself); module docstring self-describes as unused ("Nothing
  imports this module", `legacy/app/legacy_import.py:1`); zero routes reference it.
- provenance: OQ-003. **Ruling required before disposition** (do-not-port vs. "keep as a
  documented one-off ops script, not part of the app").

## Candidate: `/internal/export/csv` route — 2020 audit export
- what: `export_csv()` at `legacy/app/server.py:111-115`, dumps all tickets as CSV.
- evidence: comment states "written for the 2020 audit; no caller since"
  (`legacy/app/server.py:112`); zero hits in the one-hour access-log sample (weak evidence given
  the short window, see OQ-102); zero inbound references from other modules.
- provenance: OQ-002. **Ruling required before disposition** (do-not-port vs. "keep — used
  out-of-band by a human, infrequently, which a short log window wouldn't show").
