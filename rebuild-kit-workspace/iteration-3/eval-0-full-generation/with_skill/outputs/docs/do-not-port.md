# Do Not Port

Negative space. Each entry: what, evidence (zero-traffic + zero-references / PB-nnn), provenance.

## `internal/export/csv` — `GET /internal/export/csv`
- what: hand-rolled CSV export of all tickets (`id,title,status`), no auth, no pagination.
- evidence: zero hits in the 2,000-row `ticketd/ops/access.log` sample (`grep -c "export/csv"` →
  0); code comment "written for the 2020 audit; no caller since" (`ticketd/app/server.py:111-115`).
- provenance: PB-009, disposition confirmed do-not-port with caveat OQ-003 (the access-log sample
  is a single synthetic day, not the genuine ~30-day window described in the rewrite request —
  see `docs/open-questions.md#OQ-003` — so treat this as strong-but-not-conclusive evidence and
  have a human confirm before the M0/M1 cutover finalizes).
- if ever needed again: equivalent data is derivable from `GET /api/tickets` client-side, or as a
  trivial future WO — not carried into M0..Mn.

## `app/legacy_import.py` — one-off 2019 spreadsheet importer
- what: `import_spreadsheet(path)` reads a CSV via `csv.DictReader`. Not registered as a route,
  not imported by any other module in the tree.
- evidence: docstring "Nothing imports this module" (`ticketd/app/legacy_import.py:1`);
  `grep -rn "legacy_import\|import_spreadsheet" ticketd/app/` returns no callers outside the file
  itself.
- provenance: PB-009, disposition do-not-port, no caveat (this one is a static fact — zero
  in-tree references — not a traffic-sample inference, so it's not subject to the OQ-003 caveat).
- if ever needed again: the 2019 spreadsheet format itself isn't in evidence either; a future
  one-off migration script would need to be written fresh against whatever source format exists
  then, so nothing here is worth preserving as a template.
