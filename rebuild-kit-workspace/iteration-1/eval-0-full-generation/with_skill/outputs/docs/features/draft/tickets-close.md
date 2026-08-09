# Draft spec — tickets/close  (`POST /api/tickets/<int:tid>/close`)

Usage weight 0.0495. Perf p50 110ms / p95 287ms / p99 352ms (the SMTP tax is visible:
~4x the read endpoints' p50 — cf. `perf-envelopes.json`).

| id | claim | fidelity | confidence | evidence |
|---|---|---|---|---|
| CL-1 | Close = `UPDATE ... SET status='closed', closed_at=now WHERE id=? AND status != 'closed'` — idempotent by WHERE-guard | FIXED | cited+traced | `ticketd/app/server.py:69-72`; traces `tickets-close-001/002` |
| CL-2 | Response is always 200 `{"closed": <bool>}` — true iff a row transitioned; false for already-closed AND for nonexistent IDs (indistinguishable) | FIXED | cited+traced | `ticketd/app/server.py:73,77`; traces `tickets-close-001..003` |
| CL-3 | On actual transition only: one email to hardcoded `watchers@example.internal`, body `closed: <title>` | FIXED (recipient/body) | cited+traced | `ticketd/app/server.py:73-76`; trace `tickets-close-001` state.email |
| CL-4 | The email is sent synchronously in-request via SMTP with 30s timeout; SMTP failure/latency fails or stalls the close request | REPAIR (PB-001) → target: close succeeds and returns independently of SMTP; dispatch decoupled (mechanism FREE, default outbox — OQ-004). Divergence ED-001 | cited+traced | `ticketd/app/server.py:76` (comment names the outage mode), `ticketd/app/notify.py:5-7`; trace `tickets-close-001` |
| CL-5 | No body is read; request body is ignored entirely | FIXED | cited | `ticketd/app/server.py:68-77` (no `request` access) |
| CL-6 | Commit happens **before** the email send — a ticket can close and the mail still fail (mail is best-effort-after-commit already, just blocking) | FIXED ordering fact, folds into CL-4's repair | cited | `ticketd/app/server.py:72-76` |

REPAIR acceptance shape (ED-001): replay state records `email.mode` — legacy `"sync"`,
modern `"queued"`; message content/recipient must still match (CL-3 stays FIXED).
NFR-1: close must pass replay with the mail sink down.
