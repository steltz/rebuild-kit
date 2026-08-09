# Notifications (how it works today)

The smallest file in the app (`legacy/app/notify.py`, 7 lines) and the one with the biggest
consequence. One function, `send_mail(to, body)`, opens a blocking `smtplib.SMTP` connection
with a 30-second timeout and sends synchronously — no queue, no retry, no background thread. The
module's own docstring is refreshingly honest about the cost: "~2s typical, 30s on provider
trouble."

Two call sites, both in `legacy/app/server.py`, both in-request: closing a ticket
(`server.py:76`) and requesting a password reset (`server.py:94`). This is PB-001, the primary
defect that motivated this rewrite. A subtler consequence worth knowing: in the close-ticket
path, the database commit happens BEFORE the email send (`server.py:72` then `76`), with no
exception handling around the send — so if SMTP fails, the ticket IS closed but the client gets
an unhandled 500 and has no way to know that. The rewrite (`WO-003`, `WO-004`) fixes both the
blocking AND this visibility problem, because they share the same root cause: doing network I/O
inside the request/response cycle with no error boundary.

There are no other outbound integrations anywhere in this codebase — no queues, no webhooks, no
cron. This is the entire external-dependency surface of ticketd.
