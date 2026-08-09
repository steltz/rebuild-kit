# Draft spec — Admin: CSV export

<!-- Cross-reference (P9 audit finding I-2): this route is also unauthenticated -- see
     docs/open-questions.md#OQ-004. Notably the one route where "no auth" is most surprising,
     since it's under /internal/ and exports every ticket. -->

## GET /internal/export/csv

- statement: Dumps every ticket row as CSV with a fixed 3-column header `id,title,status`
  (columns other than these three — `slug`, `priority`, `assignee_id`, `created_at`,
  `closed_at` — are read from the DB but not emitted).
  fidelity: FIXED
  evidence: [legacy/app/server.py:112-115] confidence: cited
- statement: No quoting/escaping of `title` — a title containing a comma or newline would
  produce malformed CSV. Not reported by the human; code-observed.
  fidelity: FIXED (ported as-is; no PB entry sanctions a fix) — flagged as a coverage-hunt
  finding for P9, not promoted to an OQ on its own since it's a strict subset of "use a real CSV
  writer" which is an obviously-safe FREE implementation choice as long as the 3-column,
  header-included, comma-separated *output shape* for clean data matches today's output exactly.
  evidence: [legacy/app/server.py:114] confidence: cited
- statement: Route comment says "written for the 2020 audit; no caller since" — this is a code
  comment, not zero-traffic evidence (P2 inactive, no logs to confirm). Does NOT meet the
  do-not-port evidence bar (it IS a registered route, so "zero route references" fails) — stays
  FIXED/ported, flagged for a human to decide whether it's still wanted.
  fidelity: FIXED (evidence bar not met for removal)
  evidence: [legacy/app/server.py:112] confidence: cited
