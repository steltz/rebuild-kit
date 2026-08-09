# Draft — Export subsystem (candidate dead code)

<!-- P4 draft, self-verified against legacy/app/server.py line-by-line on 2026-08-09. -->

## Feature: CSV export — `GET /internal/export/csv`

- statement: Dumps every ticket row as CSV with header `id,title,status` and one line per
  ticket, `Content-Type: text/csv`, no auth, no filtering.
  fidelity: FIXED **if** this route is ruled live (see OQ-003); otherwise `do-not-port` per
  `docs/do-not-port.md#DNP-002`. Not decided in this pass.
  evidence: legacy/app/server.py:111-115 (cited)
- statement: CSV fields are built with plain string interpolation
  (`f"{r['id']},{r['title']},{r['status']}"`) — no quoting or escaping. A ticket title containing
  a comma, quote, or newline produces malformed/misaligned CSV.
  fidelity: FIXED (existing, evidenced bug) **if** the route is ruled live. This is a genuine
  defect by inspection, but it is not in the problem brief and the route itself is a do-not-port
  candidate — flagging here rather than silently fixing or silently dropping it. If OQ-003 rules
  the route live, this becomes a PB-proposal candidate for a REPAIR (proper CSV quoting), not an
  automatic fix.
  evidence: legacy/app/server.py:114 (cited)
- statement: In-code comment states "written for the 2020 audit; no caller since" — the author's
  own testimony that this route is unused, though unconfirmed by access logs (unavailable this
  run).
  fidelity: n/a (provenance note, not a behavior claim)
  evidence: legacy/app/server.py:112 (cited)

## Non-feature: `legacy_import.py`

Not a route — a standalone function (`import_spreadsheet`) with zero inbound references
anywhere in the tree (confirmed via `inventory.json` dependency graph). No behavior extraction
performed; see `docs/do-not-port.md#DNP-001` and `docs/open-questions.md#OQ-003`.
