# notifications (how it works today)

Seven lines (`ticketd/app/notify.py`): open a blocking SMTP connection to a hardcoded
`smtp.internal:25` with a 30-second timeout, and push the raw body string as the entire
message — **no Subject, no headers at all**. Its own docstring is the best incident report
we have: "Blocks the request thread; ~2s typical, 30s on provider trouble."

Two callers, total: ticket close (`server.py:76`, to the watchers mailbox) and reset request
(`server.py:94`, carrying the token). No other event notifies anyone. In both callers the DB
commit happens first, so an SMTP failure produces a 500 *after* the side effect — the close
happened, the token is live, and the caller was told it failed.

This module is PB-001's root cause and does not survive the rewrite in any form: dispatch
becomes queued (ED-001/ED-002/ED-002b via WO-004's seam), messages become real MIME, the
host becomes config (DNP-003). What is preserved: the trigger set (exactly those two
events), the recipients, and the content markers `closed: <title>` / `reset token: <token>`
— all trace-pinned.
