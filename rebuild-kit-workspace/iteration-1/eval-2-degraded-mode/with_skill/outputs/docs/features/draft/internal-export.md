# Draft spec — subsystem: internal-export

## Feature: CSV export — GET /internal/export/csv

- statement: Returns 200 `text/csv`: header line `id,title,status`, then one line per ticket
  (ALL tickets, no filter) with exactly those three fields — despite `SELECT *`. No quoting or
  escaping: a title containing a comma or newline corrupts the row format, and that corrupted
  format is the observed behavior.
  fidelity: ASK — OQ-001 governs whether this route is ported at all; if ported, the format
  above is FIXED (an audit consumer may parse it).   confidence: cited
  evidence: ticketd/app/server.py:111-115
- statement: In-code comment: "written for the 2020 audit; no caller since". Dead-route
  candidate — but degraded mode means NO access logs exist to corroborate zero traffic, so
  this cannot be promoted to do-not-port on static evidence alone (route is reachable and
  unauthenticated).
  fidelity: ASK — OQ-001 (blocks WO-007; owner can likely answer from memory)
  confidence: cited (comment) / unverifiable (liveness)   evidence: ticketd/app/server.py:112
