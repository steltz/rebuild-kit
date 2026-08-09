# Do Not Port

<!-- Negative space. Each entry: what, evidence (zero-traffic + zero-references / PB-nnn), provenance. -->

## DNP-001 — `app/legacy_import.py` (spreadsheet CSV importer)
- what: `import_spreadsheet(path)` — reads a CSV via `csv.DictReader` and returns rows. No caller.
- evidence: zero inbound imports in `inventory.json.dependency_edges`; zero route references;
  module docstring itself states "Nothing imports this module."; not referenced by
  `ticketd-nohistory/README.md`'s run instructions. Zero-traffic corroboration is unavailable
  (no runtime evidence exists — `rebuild.json.evidence.runtime_ingestion: inactive`), so this
  entry rests on static evidence alone (dependency graph + docstring), not the usual
  static-plus-zero-traffic pair the skill recommends. Flagged at lower confidence for that reason.
- provenance: P1 static inventory, `hotspots.md` orphan-module disposition.
- caveat: if the human knows of an out-of-band invocation not visible in this tree (a cron job, a
  manual one-off run still exercised today), that overrides this entry — raise it as a PB entry
  or ruling rather than silently restoring the module.

## DNP-002 — `/internal/export/csv` route
- what: `GET /internal/export/csv` in `ticketd-nohistory/app/server.py:111` — dumps all tickets
  as CSV. Its own code comment: "written for the 2020 audit; no caller since."
- evidence: source comment is direct testimony from the code itself about intent/history; no
  runtime evidence exists to independently confirm zero traffic (evidence inactive, same caveat
  as DNP-001). This is weaker evidence than a corroborated zero-traffic report — flagged as a
  **candidate**, not a settled disposition; the code comment is a claim about a specific one-time
  audit, not proof no one else discovered and uses the endpoint since.
- provenance: P1 static inventory / direct source reading.
- disposition: NOT auto-excluded from the rewrite. Filed to `docs/open-questions.md` (OQ-004) —
  a human should confirm before this endpoint is dropped. Until ruled, WO-006 ports it as FIXED
  (cheap to keep, expensive to be wrong about silently dropping an endpoint someone depends on).
