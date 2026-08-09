# Draft spec — tickets/get  (`GET /api/tickets/<int:tid>`)

Usage weight 0.092. Perf p50 24ms / p95 56ms / p99 86ms.

| id | claim | fidelity | confidence | evidence |
|---|---|---|---|---|
| TG-1 | Path param is `<int:tid>` — non-integer IDs don't match the route → framework 404 | FIXED | cited+traced | `ticketd/app/server.py:58`; trace `tickets-get-003` |
| TG-2 | Existing ticket → 200 with the full row as JSON object | FIXED | cited+traced | `ticketd/app/server.py:60-64`; trace `tickets-get-001` |
| TG-3 | **Missing ticket → 200 with `{}` — NOT 404.** Historical quirk the legacy UI depends on | FIXED | cited+traced | `ticketd/app/server.py:61-63` (comment: "the legacy UI depends on it") + PB-005; trace `tickets-get-002` |

| TG-4 | Negative IDs don't match the `<int:tid>` converter (unsigned) → framework 404, same as TG-1 (audit coverage-hunt AD-004) | FIXED | cited | Flask int converter semantics; `ticketd/app/server.py:58` |

That's the whole endpoint. The 200-`{}` quirk is the single most Hyrum-sensitive behavior
in the system — do not "fix" it (PB-005).
