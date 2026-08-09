# Notifications (designed-not-built)

**Designed, not built.** Both call sites (`WO-003`, `WO-004`) move email dispatch out of the
request/response cycle. The MECHANISM is deliberately left FREE (`modern/CLAUDE.md`) — FastAPI's
built-in `BackgroundTasks` is called out as sufficient for this app's scale, but nothing in the
evidence gathered so far requires it; a table-backed outbox or an external queue are equally
valid choices for whoever implements this. What's NOT free: the outcome. The response must not
wait on SMTP, and — the subtler half of PB-001 caught while writing `WO-004` — a send failure
must never surface as a client-visible error for an operation (like closing a ticket) that
already succeeded in the database.

No instrumentation exists yet to let the replay harness distinguish "sent synchronously" from
"queued" in a captured trace (see `verification/replay/expected-divergences.yaml`'s measurement
notes on ED-001/ED-001b) — building that hook is part of implementing this WO, not a separate
task.
