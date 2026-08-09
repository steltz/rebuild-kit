# Do Not Port

<!-- Negative space. Each entry: what, evidence (zero-traffic + zero-references / PB-nnn), provenance. -->

## DNP-001 — `app/legacy_import.py` (`import_spreadsheet`)
- what: one-off CSV importer from the 2019 spreadsheet migration.
- evidence: **static, high confidence.** Zero inbound references anywhere in the legacy tree —
  absent from `inventory.json.dependency_edges` (only edges are `server.py -> notify.py` and
  `server.py -> util.py`), no route or CLI entrypoint wires it up, and its own docstring says
  "Nothing imports this module." (`ticketd/app/legacy_import.py:1`).
  Confirmed via P1 static inventory (`hotspots.md`), 2026-08-08.
- provenance: generator (P1), not brief-sourced — no PB entry needed for confirmed-dead code
  with zero references; only zero-*traffic* candidates need the PB-severity judgment call P2
  describes.
- disposition: do not port. If a one-off CSV import is ever needed again for the new schema,
  it's new work scoped by a future PB/OQ entry, not a resurrection of this module.

## DNP-002 — `GET /internal/export/csv` (candidate, LOW CONFIDENCE — do not act on this alone)
- what: CSV export of all tickets, comment says "written for the 2020 audit; no caller since"
  (`ticketd/app/server.py:112`).
- evidence: **weak.** Zero hits in `ticketd/ops/access.log` (`grep -c "export/csv"` → 0) — but
  that log's real observation window is one synthetic hour, not the ~30 days it was described
  as (see `docs/problem-brief.md` OIQ-3, `usage-weights.json.notes`). Zero traffic over one
  hour is not meaningful evidence for an annual-audit tool by construction — an annual caller
  would show zero hits in *any* one-hour window. The code comment is testimony-adjacent (it's a
  developer's note, not a PB entry) and corroborating but not sufficient alone.
- provenance: P2 zero-traffic report + code comment, both low confidence per the reasoning
  above.
- disposition: **not** promoted to do-not-port. Carried into `docs/open-questions.md` as
  OQ-004 (mirrors brief OIQ-6) — needs a human who knows whether the 2020 audit tooling still
  calls this before it's dropped or ported. Until ruled, treat as in-scope-but-low-priority
  (`FIXED`, last in the backlog) rather than removed.

