# Draft spec — notification (shared side-channel, `app/notify.py`)

Not a route; the side-effect contract shared by tickets/close and auth-reset/request.

| id | claim | fidelity | confidence | evidence |
|---|---|---|---|---|
| NT-1 | Transport: SMTP to `smtp.internal:25`, per-call connection, 30s timeout, no retry, no queue | REPAIR (PB-001): transport becomes decoupled dispatch (mechanism FREE — OQ-004 default: transactional outbox + worker). ED-001/ED-003 | cited | `ticketd/app/notify.py:5-7` |
| NT-2 | Sender is `ticketd@example.internal`; payload is the raw body string — **no Subject, no headers, not even a blank line**: `sendmail` is called with a headerless message | FIXED (outcome: same sender/recipient/body text) — flag: many providers render this oddly; changing it would need a PB | cited | `ticketd/app/notify.py:6-7` |
| NT-3 | Failure mode today: any SMTP exception propagates into the request → 500 after commit (close) / after token insert (reset) | REPAIR (PB-001): failures must no longer surface in-request; delivery becomes at-least-once from the outbox | cited | `ticketd/app/notify.py:5-7`, call sites `ticketd/app/server.py:76,94` + PB-001 testimony (June outage) |

Harness note: both trees run against a **mail sink** (capture shim / sink container);
traces record `state.email = {mode, to, body_matches}` — see
`verification/harness/README.md`.
