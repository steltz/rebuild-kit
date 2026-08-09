# Notification (designed-not-built)

`WO-004` builds the async dispatch boundary both `WO-002` (ticket close) and `WO-003` (auth
reset) call into instead of legacy's inline `smtplib.SMTP`. The mechanism (background task,
queue, or outbox) is FREE — `modern/CLAUDE.md` leaves it to the executor — but the delivery
guarantee level (retry-on-failure vs. best-effort) is an open question (`OQ-002`) this work
order cannot close without a ruling on. Whatever's built must make dispatch failures observable
(logged/metriced), since PB-001's original problem was partly that failures were invisible until
they took the request down with them.

No implementation exists yet.
