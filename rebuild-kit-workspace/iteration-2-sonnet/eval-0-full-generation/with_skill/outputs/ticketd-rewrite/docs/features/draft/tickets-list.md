# Draft spec: GET /api/tickets (list)

usage_weight: 0.6175 (highest-traffic route by far — see `usage-weights.json`)

## Happy path
- `GET /api/tickets`, optional `?status=<value>` query param.
- No auth check of any kind (see OQ-002).
- Query: `SELECT * FROM tickets [WHERE status = ?] ORDER BY created_at DESC`
  (`ticketd/app/server.py:30-36`).
- Response: `200`, JSON array of ticket objects (every column, via `dict(sqlite3.Row)`), all
  matching rows, no pagination.

## Behaviors

- statement: With no `status` param, returns every ticket row, ordered by `created_at`
    descending, as a JSON array. No pagination — the full result set is returned every time.
  fidelity: FIXED
  evidence: [legacy/app/server.py:27-37]
  confidence: cited

- statement: With `?status=<value>`, filters to exact string match on `status`. Any string is
    accepted as the filter value, including values outside the DB's `CHECK` enum (`open`,
    `closed`) — such a filter simply matches zero rows rather than erroring.
  fidelity: FIXED
  evidence: [legacy/app/server.py:29-34]
  confidence: cited

- statement: No pagination exists. The code comment states this is deliberate: "the UI relies
    on getting everything and filtering client-side."
  fidelity: FIXED — explicitly PB-005 territory: adding pagination would change the response
    shape/contract the (unmodified) UI depends on. Not to be "improved" during the rewrite.
  evidence: [legacy/app/server.py:35]
  confidence: cited
  note: NFR-scale question (does this remain viable as ticket count grows) is OIQ-5,
    unresolved, but is an operability question for leadership — not license to change the API
    shape unilaterally.

- statement: Ordering is `created_at DESC` computed from a naive-local-time string column;
    with two tickets created in the same second (naive-time resolution issues), tie-break order
    is whatever SQLite's stable/unstable sort produces for equal keys — not specified by the app.
  fidelity: ASK
  evidence: [legacy/app/server.py:36] conflict: no explicit secondary sort key exists to
    disambiguate ties
  confidence: inferred
  note: mirrors OQ-003 (timestamp handling); low real-world impact given single-process SQLite
    writes are effectively serialized, flagged for completeness only, does not block WO-001.

- statement: Response includes every DB column verbatim, including `assignee_id` (always
    `null` in observed behavior since nothing ever sets it — see docs/domain/user.md) and both
    naive-local-time timestamp fields.
  fidelity: FIXED
  evidence: [legacy/app/server.py:37, legacy/db/schema.sql:1-10]
  confidence: cited

## Error paths
None — this route has no failure mode besides a DB error (uncaught, would 500). No explicit
error handling exists; not a gap the brief asked to close.

## Acceptance
  replay_set: tickets-list-*.jsonl (happy path with/without status filter, empty-result filter,
    empty-table case)
  tests: characterization/tickets/list.spec
