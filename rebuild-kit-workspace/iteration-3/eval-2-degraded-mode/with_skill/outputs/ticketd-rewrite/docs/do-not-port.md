# Do Not Port

<!-- Negative space. Each entry: what, evidence (zero-traffic + zero-references / PB-nnn), provenance. -->

## DNP-001 (candidate) — `legacy_import.py` one-off spreadsheet importer
- what: `import_spreadsheet()` in `legacy/app/legacy_import.py:5-7`, a one-off CSV importer for
  the "2019 spreadsheet era".
- evidence: Module docstring states "Nothing imports this module" (legacy/app/legacy_import.py:1).
  No route, script, or other module in the legacy tree references it (verified by inventory,
  see `inventory.json`). No runtime/access-log evidence exists to confirm zero-traffic in
  production, since none is available this run.
- status: **candidate, not final** — pending ruling on `docs/open-questions.md#OQ-003`. Do not
  port unless the ruling says otherwise; do not build a "one-off import" feature into `modern/`
  speculatively either, since FREE grants mechanism freedom, not feature freedom.

## DNP-002 (candidate) — `/internal/export/csv` route
- what: `export_csv()` in `legacy/app/server.py:111-115`.
- evidence: In-code comment: "written for the 2020 audit; no caller since"
  (legacy/app/server.py:112). No other route or module references it. No access-log evidence
  available this run to confirm zero real traffic.
- status: **candidate, not final** — pending ruling on `docs/open-questions.md#OQ-003`. If ruled
  dead, this becomes a firm DNP entry with disposition `do-not-port` on any linked PB. If ruled
  live (an external consumer exists), it graduates to a normal WO with FIXED fidelity on its
  current output shape (`id,title,status` header, no quoting/escaping of embedded commas in
  titles — legacy/app/server.py:114 is unescaped CSV, a latent bug if any title contains a comma).
