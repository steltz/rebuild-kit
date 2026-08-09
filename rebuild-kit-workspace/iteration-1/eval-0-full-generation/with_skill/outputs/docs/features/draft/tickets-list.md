# Draft spec — tickets/list  (`GET /api/tickets`)

Usage weight 0.6175 (highest; `usage-weights.json`). Perf envelope p50 25ms / p95 68ms / p99 95ms.

| id | claim | fidelity | confidence | evidence |
|---|---|---|---|---|
| TL-1 | Returns a JSON array of full ticket rows (all columns, incl. slug, assignee_id, closed_at) | FIXED | cited+traced | `ticketd/app/server.py:30-37`; trace `tickets-list-001` |
| TL-2 | No pagination — everything is returned; the UI filters client-side | FIXED | cited | `ticketd/app/server.py:35` (comment: "the UI relies on getting everything") + PB-005 |
| TL-3 | Optional `?status=` filter, exact equality; any other value (incl. unknown) yields `[]`, not an error | FIXED | cited+traced | `ticketd/app/server.py:29-34`; traces `tickets-list-002..004` |
| TL-4 | Ordered by `created_at DESC` (string comparison over ISO text) | FIXED | cited+traced | `ticketd/app/server.py:36`; trace `tickets-list-001` |
| TL-5 | Ties on `created_at` have no defined order — on BOTH sides (no tiebreaker in the query). No diff rule sorts for this; replay input sets avoid ties (microsecond timestamps make them practically absent). Modern may add `id DESC` as tiebreaker without observable effect on tie-free data | FIXED (tie order explicitly unspecified) | cited | no ORDER tiebreaker at `ticketd/app/server.py:36` — audit correction AD-001 |
| TL-6 | Response rows serialize `NULL` as JSON `null` (e.g. `closed_at`, `assignee_id`) | FIXED | cited+traced | `ticketd/app/server.py:37`; trace `tickets-list-001` |

Error paths: none of its own (no auth, no validation). Unexplained prod 5xx: OQ-008.
Ordering note: `created_at DESC` over *naive local* ISO strings — a DST fall-back hour can
reorder; inherits OQ-005's timezone ruling for the modern side.
